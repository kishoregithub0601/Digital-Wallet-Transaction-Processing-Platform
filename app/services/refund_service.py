
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.models.enums import (
    RefundStatus,
    TransactionType,
    TransferStatus,
    WalletStatus,
)
from app.models.financial_transactions import Refund, Transfer
from app.models.transaction_ledger import TransactionLedger
from app.models.wallet import Wallet
from app.services.transaction_service import (
    TransactionDomainError,
    _ledger,
    _lock_wallets,
    _validate_amount,
)


def request_transfer_refund(
    db: Session,
    transfer_id: uuid.UUID,
    amount: Decimal,
    requester_user_id: uuid.UUID,
    reason: str | None = None,
) -> Refund:
    _validate_amount(amount)

    transfer = db.scalar(
        select(Transfer)
        .where(Transfer.id == transfer_id)
        .with_for_update()
    )

    if transfer is None or transfer.status != TransferStatus.COMPLETED:
        raise TransactionDomainError(
            "INVALID_REFUND",
            "Original completed transfer not found.",
            409,
        )

    wallets = _lock_wallets(
        db,
        [transfer.sender_wallet_id, transfer.receiver_wallet_id],
    )
    sender = wallets[transfer.sender_wallet_id]
    receiver = wallets[transfer.receiver_wallet_id]

    if sender.user_id != requester_user_id:
        raise TransactionDomainError(
            "FORBIDDEN",
            "Only the original sender can request this refund.",
            403,
        )

    refunded = db.scalar(
        select(func.coalesce(func.sum(Refund.amount), 0)).where(
            Refund.original_transaction_id == transfer.id,
            Refund.status.in_(
                [
                    RefundStatus.REQUESTED,
                    RefundStatus.UNDER_REVIEW,
                    RefundStatus.APPROVED,
                    RefundStatus.COMPLETED,
                ]
            ),
        )
    )

    if Decimal(str(refunded)) + amount > transfer.amount:
        raise TransactionDomainError(
            "INVALID_REFUND",
            "Refund amount exceeds the original transaction amount.",
            409,
        )

    refund = Refund(
        original_transaction_type="TRANSFER",
        original_transaction_id=transfer.id,
        wallet_id=receiver.id,
        amount=amount,
        reason=reason,
        status=RefundStatus.REQUESTED,
        reference_number=f"REF-{uuid.uuid4().hex}",
    )

    db.add(refund)
    db.flush()
    return refund


def review_transfer_refund(
    db: Session,
    refund_id: uuid.UUID,
    reviewer_user_id: uuid.UUID,
    approve: bool,
) -> Refund:
    refund = db.scalar(
        select(Refund)
        .where(Refund.id == refund_id)
        .with_for_update()
    )

    if refund is None:
        raise TransactionDomainError(
            "REFUND_NOT_FOUND", "Refund not found.", 404
        )

    if refund.status != RefundStatus.REQUESTED:
        raise TransactionDomainError(
            "INVALID_REFUND_STATE",
            "Only requested refunds can be reviewed.",
            409,
        )

    if not approve:
        refund.status = RefundStatus.REJECTED
        refund.reviewed_by = reviewer_user_id
        db.flush()
        return refund

    transfer = db.scalar(
        select(Transfer)
        .where(Transfer.id == refund.original_transaction_id)
        .with_for_update()
    )

    if transfer is None or transfer.status != TransferStatus.COMPLETED:
        raise TransactionDomainError(
            "INVALID_REFUND",
            "Original transfer is no longer eligible for refund.",
            409,
        )

    wallets = _lock_wallets(
        db,
        [transfer.sender_wallet_id, transfer.receiver_wallet_id],
    )
    sender = wallets[transfer.sender_wallet_id]
    receiver = wallets[transfer.receiver_wallet_id]

    if sender.status in {WalletStatus.CLOSED, WalletStatus.SUSPENDED}:
        raise TransactionDomainError(
            "WALLET_CLOSED",
            "Original sender wallet cannot receive a refund.",
            409,
        )

    if receiver.status != WalletStatus.ACTIVE:
        raise TransactionDomainError(
            "WALLET_NOT_ACTIVE",
            "Receiver wallet must be active to process a refund.",
            409,
        )

    refunded = db.scalar(
        select(func.coalesce(func.sum(Refund.amount), 0)).where(
            Refund.original_transaction_id == transfer.id,
            Refund.status == RefundStatus.COMPLETED,
        )
    )

    if Decimal(str(refunded)) + refund.amount > transfer.amount:
        raise TransactionDomainError(
            "INVALID_REFUND",
            "Refund exceeds the remaining refundable amount.",
            409,
        )

    if receiver.available_balance < refund.amount:
        raise TransactionDomainError(
            "INSUFFICIENT_BALANCE",
            "Receiver wallet has insufficient balance for this refund.",
            409,
        )

    receiver_before = receiver.available_balance
    sender_before = sender.available_balance

    receiver.available_balance -= refund.amount
    sender.available_balance += refund.amount

    refund.status = RefundStatus.COMPLETED
    refund.reviewed_by = reviewer_user_id
    refund.completed_at = datetime.now(timezone.utc)

    _ledger(
        db, receiver, TransactionType.REFUND, refund.amount,
        receiver_before, "refund", refund.id, reviewer_user_id,
        "Transfer refund debited from receiver",
    )
    _ledger(
        db, sender, TransactionType.REFUND, refund.amount,
        sender_before, "refund", refund.id, reviewer_user_id,
        "Transfer refund credited to original sender",
    )

    db.flush()
    return refund
