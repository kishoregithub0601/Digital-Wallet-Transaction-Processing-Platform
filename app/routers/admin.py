
import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.models.enums import SuspiciousStatus
from app.models.operations import SuspiciousTransaction, TransactionLimit
from app.models.user import User, UserRole


router = APIRouter(prefix="/api/admin", tags=["Administration"])


def require_admin(user: User) -> None:
    if user.role not in {UserRole.ADMIN, UserRole.SUPER_ADMIN}:
        raise HTTPException(status_code=403, detail="Administrator access required.")


class TransactionLimitUpdate(BaseModel):
    currency: str = Field(default="INR", pattern=r"^[A-Z]{3}$")
    max_transaction_amount: Decimal = Field(gt=0)
    daily_transfer_limit: Decimal = Field(gt=0)
    daily_withdrawal_limit: Decimal = Field(gt=0)
    max_transactions_per_day: int = Field(gt=0, le=10000)
    suspicious_amount_threshold: Decimal = Field(gt=0)


class SuspiciousReview(BaseModel):
    status: SuspiciousStatus


@router.get("/transaction-limits")
def get_limits(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(user)
    return list(db.scalars(select(TransactionLimit)).all())


@router.patch("/transaction-limits")
def update_limits(
    data: TransactionLimitUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(user)

    limit = db.scalar(
        select(TransactionLimit)
        .where(TransactionLimit.currency == data.currency)
        .with_for_update()
    )

    if limit is None:
        limit = TransactionLimit(currency=data.currency)
        db.add(limit)

    limit.max_transaction_amount = data.max_transaction_amount
    limit.daily_transfer_limit = data.daily_transfer_limit
    limit.daily_withdrawal_limit = data.daily_withdrawal_limit
    limit.max_transactions_per_day = data.max_transactions_per_day
    limit.suspicious_amount_threshold = data.suspicious_amount_threshold
    limit.updated_by = user.id

    db.commit()
    db.refresh(limit)
    return limit


@router.get("/suspicious-transactions")
def list_suspicious(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(user)

    return list(
        db.scalars(
            select(SuspiciousTransaction)
            .where(
                SuspiciousTransaction.status
                != SuspiciousStatus.NORMAL
            )
            .order_by(SuspiciousTransaction.created_at.desc())
        ).all()
    )


@router.patch("/suspicious-transactions/{item_id}")
def review_suspicious(
    item_id: uuid.UUID,
    data: SuspiciousReview,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(user)

    item = db.get(SuspiciousTransaction, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Transaction not found.")

    item.status = data.status
    item.reviewed_by = user.id

    from datetime import datetime, timezone
    item.reviewed_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(item)
    return item
