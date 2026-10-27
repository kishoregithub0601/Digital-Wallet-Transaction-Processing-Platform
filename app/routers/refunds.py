
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.models.enums import RefundStatus
from app.models.financial_transactions import Refund
from app.models.user import User, UserRole
from app.models.wallet import Wallet
from app.schemas.transactions import RefundCreate
from app.services.refund_service import (
    request_transfer_refund,
    review_transfer_refund,
)


router = APIRouter(prefix="/api/refunds", tags=["Refunds"])


@router.post("", status_code=201)
def create_refund(
    data: RefundCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if data.original_transaction_type != "TRANSFER":
        raise HTTPException(
            status_code=422,
            detail="This initial refund workflow supports transfers only.",
        )

    try:
        refund = request_transfer_refund(
            db,
            data.original_transaction_id,
            data.amount,
            user.id,
            data.reason,
        )
        db.commit()
        db.refresh(refund)
        return refund
    except Exception:
        db.rollback()
        raise


@router.get("")
def list_refunds(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = select(Refund).order_by(Refund.created_at.desc())

    if user.role == UserRole.CUSTOMER:
        owned_wallet_ids = select(Wallet.id).where(
            Wallet.user_id == user.id
        )
        query = query.where(Refund.wallet_id.in_(owned_wallet_ids))

    return list(db.scalars(query).all())


@router.get("/{refund_id}")
def get_refund(
    refund_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    refund = db.get(Refund, refund_id)

    if refund is None:
        raise HTTPException(status_code=404, detail="Refund not found.")

    wallet = db.get(Wallet, refund.wallet_id)

    if (
        user.role == UserRole.CUSTOMER
        and (wallet is None or wallet.user_id != user.id)
    ):
        raise HTTPException(status_code=403, detail="Refund access denied.")

    return refund


def review_refund(
    refund_id: uuid.UUID,
    approve: bool,
    user: User,
    db: Session,
):
    if user.role not in {UserRole.ADMIN, UserRole.SUPER_ADMIN}:
        raise HTTPException(
            status_code=403,
            detail="Only administrators can review refunds.",
        )

    try:
        refund = review_transfer_refund(
            db, refund_id, user.id, approve
        )
        db.commit()
        db.refresh(refund)
        return refund
    except Exception:
        db.rollback()
        raise


@router.post("/{refund_id}/approve")
def approve_refund(
    refund_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return review_refund(refund_id, True, user, db)


@router.post("/{refund_id}/reject")
def reject_refund(
    refund_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return review_refund(refund_id, False, user, db)
