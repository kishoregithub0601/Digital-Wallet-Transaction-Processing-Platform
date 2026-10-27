
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User, UserRole
from app.models.wallet import Wallet
from app.schemas.wallet import WalletCreate, WalletResponse
from app.services.wallet_service import (
    change_wallet_status,
    create_wallet,
    get_wallet_for_user,
    list_wallets,
)


router = APIRouter(prefix="/api/wallets", tags=["Wallets"])


@router.post("", response_model=WalletResponse, status_code=201)
def create_wallet_endpoint(
    data: WalletCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        wallet = create_wallet(db, user, data.currency)
        db.commit()
        db.refresh(wallet)
        return wallet
    except Exception:
        db.rollback()
        raise


@router.get("", response_model=list[WalletResponse])
def get_wallets(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return list_wallets(db, user)


@router.get("/{wallet_id}", response_model=WalletResponse)
def get_wallet(
    wallet_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_wallet_for_user(db, user, wallet_id)


@router.patch("/{wallet_id}", response_model=WalletResponse)
def update_wallet(
    wallet_id: uuid.UUID,
    data: WalletCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    wallet = get_wallet_for_user(db, user, wallet_id)

    if wallet.status.value != "ACTIVE":
        raise HTTPException(
            status_code=409,
            detail="Only active wallets can be updated.",
        )

    if wallet.available_balance != 0 or wallet.pending_balance != 0:
        raise HTTPException(
            status_code=409,
            detail="Currency cannot be changed after wallet activity.",
        )

    wallet.currency = data.currency

    try:
        db.commit()
        db.refresh(wallet)
        return wallet
    except Exception:
        db.rollback()
        raise


@router.post("/{wallet_id}/freeze", response_model=WalletResponse)
def freeze_wallet(
    wallet_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    wallet = get_wallet_for_user(db, user, wallet_id)

    if (
        wallet.user_id != user.id
        and user.role not in {UserRole.ADMIN, UserRole.SUPER_ADMIN}
    ):
        raise HTTPException(status_code=403, detail="Forbidden")

    try:
        wallet = change_wallet_status(db, wallet, "freeze")
        db.commit()
        db.refresh(wallet)
        return wallet
    except Exception:
        db.rollback()
        raise


@router.post("/{wallet_id}/unfreeze", response_model=WalletResponse)
def unfreeze_wallet(
    wallet_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if user.role not in {UserRole.ADMIN, UserRole.SUPER_ADMIN}:
        raise HTTPException(
            status_code=403,
            detail="Only administrators can unfreeze wallets.",
        )

    wallet = get_wallet_for_user(db, user, wallet_id)

    try:
        wallet = change_wallet_status(db, wallet, "unfreeze")
        db.commit()
        db.refresh(wallet)
        return wallet
    except Exception:
        db.rollback()
        raise
