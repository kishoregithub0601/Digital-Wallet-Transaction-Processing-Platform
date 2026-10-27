
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from secrets import token_urlsafe

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import (
    DepositStatus,
    TransactionType,
    TransferStatus,
    WalletStatus,
    WithdrawalStatus,
)

from app.services.transaction_limits_service import (
    validate_maximum_amount,
    validate_daily_transfer_limit,
    validate_daily_withdrawal_limit,
    validate_daily_transaction_count,
)

from app.models.financial_transactions import Deposit, Transfer, Withdrawal
from app.models.transaction_ledger import TransactionLedger
from app.models.wallet import Wallet
from app.repositories.wallet_repository import get_wallet

from app.models.enums import NotificationType
from app.services.audit_service import record_audit
from app.services.notification_service import create_notification


class TransactionDomainError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def _validate_amount(amount: Decimal) -> None:
    if not amount.is_finite() or amount <= Decimal("0"):
        raise TransactionDomainError(
            "INVALID_AMOUNT", "Amount must be greater than zero."
        )

    if amount.as_tuple().exponent < -2:
        raise TransactionDomainError(
            "INVALID_AMOUNT",
            "Amount must have at most two decimal places.",
        )


def _validate_active(wallet: Wallet) -> None:
    if wallet.status == WalletStatus.FROZEN:
        raise TransactionDomainError("WALLET_FROZEN", "Wallet is frozen.", 409)

    if wallet.status != WalletStatus.ACTIVE:
        raise TransactionDomainError(
            "WALLET_NOT_ACTIVE",
            "Wallet is not active.",
            409,
        )


def _ledger(
    db: Session,
    wallet: Wallet,
    transaction_type: TransactionType,
    amount: Decimal,
    before: Decimal,
    reference_type: str,
    reference_id: uuid.UUID,
    user_id: uuid.UUID,
    description: str,
) -> None:
    db.add(
        TransactionLedger(
            wallet_id=wallet.id,
            transaction_type=transaction_type,
            amount=amount,
            balance_before=before,
            balance_after=wallet.available_balance,
            reference_type=reference_type,
            reference_id=reference_id,
            created_by=user_id,
            description=description,
        )
    )


def _lock_wallets(
    db: Session,
    wallet_ids: list[uuid.UUID],
) -> dict[uuid.UUID, Wallet]:
    result = {}

    for wallet_id in sorted(set(wallet_ids), key=str):
        wallet = db.scalar(
            select(Wallet)
            .where(Wallet.id == wallet_id)
            .with_for_update()
        )

        if wallet is None:
            raise TransactionDomainError(
                "WALLET_NOT_FOUND", "Wallet not found.", 404
            )

        result[wallet.id] = wallet

    return result


def create_deposit(
    db: Session,
    wallet_id: uuid.UUID,
    amount: Decimal,
    user_id: uuid.UUID,
) -> Deposit:
    _validate_amount(amount)
    wallet = _lock_wallets(db, [wallet_id])[wallet_id]
    _validate_active(wallet)
    validate_maximum_amount(db, wallet.currency, amount)

    deposit = Deposit(
        wallet_id=wallet.id,
        amount=amount,
        currency=wallet.currency,
        status=DepositStatus.COMPLETED,
        reference_number=f"DEP-{uuid.uuid4().hex}",
        completed_at=datetime.now(timezone.utc),
    )
    db.add(deposit)
    db.flush()

    before = wallet.available_balance
    wallet.available_balance += amount

    _ledger(
        db, wallet, TransactionType.DEPOSIT, amount, before,
        "deposit", deposit.id, user_id, "Simulated wallet deposit",
    )
    create_notification(
    db,
    wallet.user_id,
    NotificationType.DEPOSIT_COMPLETED,
    "Deposit completed",
    f"Your deposit of {amount} {wallet.currency} was completed.",
    )

    record_audit(
    db,
    action="DEPOSIT_COMPLETED",
    entity="Deposit",
    entity_id=str(deposit.id),
    user_id=user_id,
    metadata={"amount": str(amount), "currency": wallet.currency},
)
    db.flush()
    return deposit


def create_withdrawal(
    db: Session,
    wallet_id: uuid.UUID,
    amount: Decimal,
    user_id: uuid.UUID,
) -> Withdrawal:
    _validate_amount(amount)
    wallet = _lock_wallets(db, [wallet_id])[wallet_id]
    _validate_active(wallet)
    limit = validate_maximum_amount(db, wallet.currency, amount)

    validate_daily_withdrawal_limit(db, wallet, amount, limit)
    validate_daily_transaction_count(db, wallet.id, limit)

    if wallet.available_balance < amount:
        raise TransactionDomainError(
            "INSUFFICIENT_BALANCE",
            "Insufficient wallet balance.",
            409,
        )

    withdrawal = Withdrawal(
        wallet_id=wallet.id,
        amount=amount,
        currency=wallet.currency,
        status=WithdrawalStatus.COMPLETED,
        reference_number=f"WDR-{uuid.uuid4().hex}",
        completed_at=datetime.now(timezone.utc),
    )
    db.add(withdrawal)
    db.flush()

    before = wallet.available_balance
    wallet.available_balance -= amount

    _ledger(
        db, wallet, TransactionType.WITHDRAWAL, amount, before,
        "withdrawal", withdrawal.id, user_id, "Wallet withdrawal",
    )
    create_notification(
    db,
    wallet.user_id,
    NotificationType.WITHDRAWAL_COMPLETED,
    "Withdrawal completed",
    f"Your withdrawal of {amount} {wallet.currency} was completed.",
)

    record_audit(
    db,
    action="WITHDRAWAL_COMPLETED",
    entity="Withdrawal",
    entity_id=str(withdrawal.id),
    user_id=user_id,
    metadata={"amount": str(amount), "currency": wallet.currency},
)
    db.flush()
    return withdrawal


def create_transfer(
    db: Session,
    sender_wallet_id: uuid.UUID,
    receiver_wallet_id: uuid.UUID,
    amount: Decimal,
    user_id: uuid.UUID,
) -> Transfer:
    _validate_amount(amount)

    if sender_wallet_id == receiver_wallet_id:
        raise TransactionDomainError(
            "INVALID_TRANSFER",
            "Sender and receiver must be different wallets.",
        )

    wallets = _lock_wallets(
        db, [sender_wallet_id, receiver_wallet_id]
    )
    sender = wallets[sender_wallet_id]
    receiver = wallets[receiver_wallet_id]

    _validate_active(sender)
    _validate_active(receiver)

    if sender.user_id == receiver.user_id:
        raise TransactionDomainError(
            "INVALID_TRANSFER",
            "Transfers between your own wallets are not allowed.",
        )

    if sender.currency != receiver.currency:
        raise TransactionDomainError(
            "CURRENCY_MISMATCH",
            "Sender and receiver currencies must match.",
        )

    if sender.available_balance < amount:
        raise TransactionDomainError(
            "INSUFFICIENT_BALANCE",
            "Insufficient wallet balance.",
            409,
        )

    transfer = Transfer(
        sender_wallet_id=sender.id,
        receiver_wallet_id=receiver.id,
        amount=amount,
        currency=sender.currency,
        status=TransferStatus.COMPLETED,
        reference_number=f"TRF-{uuid.uuid4().hex}",
        completed_at=datetime.now(timezone.utc),
    )
    db.add(transfer)
    create_notification(
    db,
    sender.user_id,
    NotificationType.TRANSFER_COMPLETED,
    "Transfer completed",
    f"You transferred {amount} {sender.currency}.",
)

    create_notification(
    db,
    receiver.user_id,
    NotificationType.TRANSFER_RECEIVED,
    "Money received",
    f"You received {amount} {receiver.currency}.",
)

    record_audit(
    db,
    action="TRANSFER_COMPLETED",
    entity="Transfer",
    entity_id=str(transfer.id),
    user_id=user_id,
    metadata={
        "amount": str(amount),
        "currency": sender.currency,
        "sender_wallet_id": str(sender.id),
        "receiver_wallet_id": str(receiver.id),
    },
)
    db.flush()

    sender_before = sender.available_balance
    receiver_before = receiver.available_balance

    sender.available_balance -= amount
    receiver.available_balance += amount

    _ledger(
        db, sender, TransactionType.TRANSFER_DEBIT, amount,
        sender_before, "transfer", transfer.id, user_id,
        "Transfer sent",
    )
    _ledger(
        db, receiver, TransactionType.TRANSFER_CREDIT, amount,
        receiver_before, "transfer", transfer.id, user_id,
        "Transfer received",
    )

    db.flush()
    return transfer
