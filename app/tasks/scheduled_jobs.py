
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.enums import (
    DepositStatus,
    TransferStatus,
    WithdrawalStatus,
)
from app.models.financial_transactions import Deposit, Transfer, Withdrawal
from app.models.wallet import Wallet


def cleanup_stale_pending_transactions(
    older_than_minutes: int = 60,
) -> dict:
    cutoff = datetime.now(timezone.utc) - timedelta(
        minutes=older_than_minutes
    )

    counts = {
        "deposits": 0,
        "withdrawals": 0,
        "transfers": 0,
    }

    with SessionLocal() as db:
        try:
            deposits = db.scalars(
                select(Deposit)
                .where(
                    Deposit.status == DepositStatus.PENDING,
                    Deposit.created_at < cutoff,
                )
                .with_for_update(skip_locked=True)
            ).all()

            for item in deposits:
                item.status = DepositStatus.CANCELLED
                counts["deposits"] += 1

            withdrawals = db.scalars(
                select(Withdrawal)
                .where(
                    Withdrawal.status == WithdrawalStatus.PENDING,
                    Withdrawal.created_at < cutoff,
                )
                .with_for_update(skip_locked=True)
            ).all()

            for item in withdrawals:
                item.status = WithdrawalStatus.CANCELLED
                counts["withdrawals"] += 1

            transfers = db.scalars(
                select(Transfer)
                .where(
                    Transfer.status == TransferStatus.PENDING,
                    Transfer.created_at < cutoff,
                )
                .with_for_update(skip_locked=True)
            ).all()

            for item in transfers:
                item.status = TransferStatus.CANCELLED
                counts["transfers"] += 1

            db.commit()

        except Exception:
            db.rollback()
            raise

    return counts


def daily_wallet_summary() -> dict:
    with SessionLocal() as db:
        wallets = db.scalars(select(Wallet)).all()

        summary = {}

        for wallet in wallets:
            currency = wallet.currency
            if currency not in summary:
                summary[currency] = {
                    "wallet_count": 0,
                    "available_balance": 0,
                    "pending_balance": 0,
                }

            summary[currency]["wallet_count"] += 1
            summary[currency]["available_balance"] += (
                wallet.available_balance
            )
            summary[currency]["pending_balance"] += (
                wallet.pending_balance
            )

        return {
            currency: {
                key: str(value)
                for key, value in values.items()
            }
            for currency, values in summary.items()
        }
