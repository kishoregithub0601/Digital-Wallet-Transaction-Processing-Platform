
import uuid
from datetime import datetime, time, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.enums import (
    TransferStatus,
    WithdrawalStatus,
)
from app.models.financial_transactions import Transfer, Withdrawal
from app.models.operations import TransactionLimit
from app.models.wallet import Wallet



def get_transaction_limit(
    db: Session,
    currency: str,
) -> TransactionLimit:
    limit = db.scalar(
        select(TransactionLimit).where(
            TransactionLimit.currency == currency
        )
    )

    if limit is None:
        limit = TransactionLimit(currency=currency)
        db.add(limit)
        db.flush()

    return limit


def validate_maximum_amount(
    db: Session,
    currency: str,
    amount: Decimal,
) -> TransactionLimit:
    limit = get_transaction_limit(db, currency)

    if amount > limit.max_transaction_amount:
        raise TransactionDomainError(
            "TRANSACTION_LIMIT_EXCEEDED",
            "Transaction exceeds the maximum permitted amount.",
            409,
        )

    return limit


def validate_daily_transfer_limit(
    db: Session,
    sender_wallet: Wallet,
    amount: Decimal,
    limit: TransactionLimit,
) -> None:
    now = datetime.now(timezone.utc)
    start = datetime.combine(now.date(), time.min, tzinfo=timezone.utc)

    total = db.scalar(
        select(func.coalesce(func.sum(Transfer.amount), 0)).where(
            Transfer.sender_wallet_id == sender_wallet.id,
            Transfer.status == TransferStatus.COMPLETED,
            Transfer.created_at >= start,
            Transfer.created_at <= now,
        )
    ) or Decimal("0")

    if Decimal(str(total)) + amount > limit.daily_transfer_limit:
        raise TransactionDomainError(
            "TRANSACTION_LIMIT_EXCEEDED",
            "Daily transfer limit exceeded.",
            409,
        )


def validate_daily_withdrawal_limit(
    db: Session,
    wallet: Wallet,
    amount: Decimal,
    limit: TransactionLimit,
) -> None:
    now = datetime.now(timezone.utc)
    start = datetime.combine(now.date(), time.min, tzinfo=timezone.utc)

    total = db.scalar(
        select(func.coalesce(func.sum(Withdrawal.amount), 0)).where(
            Withdrawal.wallet_id == wallet.id,
            Withdrawal.status == WithdrawalStatus.COMPLETED,
            Withdrawal.created_at >= start,
            Withdrawal.created_at <= now,
        )
    ) or Decimal("0")

    if Decimal(str(total)) + amount > limit.daily_withdrawal_limit:
        raise TransactionDomainError(
            "TRANSACTION_LIMIT_EXCEEDED",
            "Daily withdrawal limit exceeded.",
            409,
        )


def validate_daily_transaction_count(
    db: Session,
    wallet_id: uuid.UUID,
    limit: TransactionLimit,
) -> None:
    now = datetime.now(timezone.utc)
    start = datetime.combine(now.date(), time.min, tzinfo=timezone.utc)

    transfers_count = db.scalar(
        select(func.count(Transfer.id)).where(
            Transfer.sender_wallet_id == wallet_id,
            Transfer.status == TransferStatus.COMPLETED,
            Transfer.created_at >= start,
            Transfer.created_at <= now,
        )
    ) or 0

    withdrawals_count = db.scalar(
        select(func.count(Withdrawal.id)).where(
            Withdrawal.wallet_id == wallet_id,
            Withdrawal.status == WithdrawalStatus.COMPLETED,
            Withdrawal.created_at >= start,
            Withdrawal.created_at <= now,
        )
    ) or 0

    if transfers_count + withdrawals_count >= limit.max_transactions_per_day:
        raise TransactionDomainError(
            "TRANSACTION_LIMIT_EXCEEDED",
            "Maximum daily transaction count exceeded.",
            409,
        )
