
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.models.enums import (
    DepositStatus,
    RefundStatus,
    TransferStatus,
    WithdrawalStatus,
    WalletStatus,
)
from app.models.financial_transactions import Deposit, Refund, Transfer, Withdrawal
from app.models.operations import SuspiciousTransaction
from app.models.user import User, UserRole
from app.models.wallet import Wallet


router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


@router.get("")
def dashboard(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    today = datetime.now(timezone.utc).date()

    if user.role in {UserRole.ADMIN, UserRole.SUPER_ADMIN}:
        total_users = db.scalar(select(func.count(User.id))) or 0

        active_wallets = db.scalar(
            select(func.count(Wallet.id)).where(
                Wallet.status == WalletStatus.ACTIVE
            )
        ) or 0

        total_balance = db.scalar(
            select(func.coalesce(func.sum(Wallet.available_balance), 0))
        ) or 0

        today_transfers = db.scalar(
            select(func.count(Transfer.id)).where(
                func.date(Transfer.created_at) == today
            )
        ) or 0

        today_volume = db.scalar(
            select(func.coalesce(func.sum(Transfer.amount), 0)).where(
                func.date(Transfer.created_at) == today,
                Transfer.status == TransferStatus.COMPLETED,
            )
        ) or 0

        failed_transfers = db.scalar(
            select(func.count(Transfer.id)).where(
                Transfer.status == TransferStatus.FAILED
            )
        ) or 0

        suspicious_count = db.scalar(
            select(func.count(SuspiciousTransaction.id)).where(
                SuspiciousTransaction.status != "NORMAL"
            )
        ) or 0

        return {
            "total_users": total_users,
            "active_wallets": active_wallets,
            "total_wallet_balance": str(total_balance),
            "todays_transactions": today_transfers,
            "todays_transaction_volume": str(today_volume),
            "failed_transfers": failed_transfers,
            "suspicious_transactions": suspicious_count,
        }

    if user.role == UserRole.SUPPORT_AGENT:
        pending_reviews = db.scalar(
            select(func.count(SuspiciousTransaction.id)).where(
                SuspiciousTransaction.status == "REVIEW_REQUIRED"
            )
        ) or 0

        suspicious_count = db.scalar(
            select(func.count(SuspiciousTransaction.id)).where(
                SuspiciousTransaction.status != "NORMAL"
            )
        ) or 0

        frozen_wallets = db.scalar(
            select(func.count(Wallet.id)).where(
                Wallet.status == WalletStatus.FROZEN
            )
        ) or 0

        refund_requests = db.scalar(
            select(func.count(Refund.id)).where(
                Refund.status.in_([
                    RefundStatus.REQUESTED,
                    RefundStatus.UNDER_REVIEW,
                ])
            )
        ) or 0

        failed_transfers = db.scalar(
            select(func.count(Transfer.id)).where(
                Transfer.status == TransferStatus.FAILED
            )
        ) or 0

        return {
            "pending_reviews": pending_reviews,
            "suspicious_transactions": suspicious_count,
            "failed_transactions": failed_transfers,
            "refund_requests": refund_requests,
            "frozen_wallets": frozen_wallets,
        }

    wallet_ids = select(Wallet.id).where(Wallet.user_id == user.id)

    wallets = list(
        db.scalars(
            select(Wallet).where(Wallet.user_id == user.id)
        ).all()
    )

    deposits = db.scalar(
        select(func.coalesce(func.sum(Deposit.amount), 0))
        .where(
            Deposit.wallet_id.in_(wallet_ids),
            Deposit.status == DepositStatus.COMPLETED,
        )
    ) or 0

    transfers = db.scalar(
        select(func.count(Transfer.id)).where(
            Transfer.sender_wallet_id.in_(wallet_ids),
            Transfer.status == TransferStatus.COMPLETED,
        )
    ) or 0

    withdrawals = db.scalar(
        select(func.count(Withdrawal.id)).where(
            Withdrawal.wallet_id.in_(wallet_ids),
            Withdrawal.status == WithdrawalStatus.COMPLETED,
        )
    ) or 0

    pending_deposits = db.scalar(
        select(func.count(Deposit.id)).where(
            Deposit.wallet_id.in_(wallet_ids),
            Deposit.status.in_([
                DepositStatus.PENDING,
                DepositStatus.PROCESSING,
            ]),
        )
    ) or 0

    recent = list(
        db.scalars(
            select(Transfer)
            .where(
                (Transfer.sender_wallet_id.in_(wallet_ids))
                | (Transfer.receiver_wallet_id.in_(wallet_ids))
            )
            .order_by(Transfer.created_at.desc())
            .limit(5)
        ).all()
    )

    return {
        "wallet_balance": {
            wallet.currency: str(wallet.available_balance)
            for wallet in wallets
        },
        "recent_transfers": [
            {
                "id": str(item.id),
                "amount": str(item.amount),
                "status": item.status.value,
                "created_at": item.created_at.isoformat(),
            }
            for item in recent
        ],
        "total_deposits": str(deposits),
        "total_transfers": transfers,
        "total_withdrawals": withdrawals,
        "pending_transactions": pending_deposits,
    }
