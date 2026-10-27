
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import select, or_
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.models.enums import TransactionType, WalletStatus
from app.models.financial_transactions import Deposit, Transfer, Withdrawal
from app.models.transaction_ledger import TransactionLedger
from app.models.user import User
from app.models.wallet import Wallet
from app.repositories.wallet_repository import get_wallet
from app.schemas.transactions import (
    DepositCreate,
    TransferCreate,
    WithdrawalCreate,
)
from app.services.transaction_service import (
    create_deposit,
    create_transfer,
    create_withdrawal,
)
from app.services.wallet_service import WalletDomainError
from app.services.idempotency_service import (
    begin_idempotent_operation,
    complete_idempotent_operation,
)

router = APIRouter(tags=["Transactions"])


def require_owned_wallet(
    db: Session,
    user: User,
    wallet_id: uuid.UUID,
) -> Wallet:
    wallet = get_wallet(db, wallet_id)

    if wallet is None:
        raise HTTPException(status_code=404, detail="Wallet not found.")

    if wallet.user_id != user.id:
        raise HTTPException(status_code=403, detail="Wallet access denied.")

    return wallet


@router.post("/api/wallets/{wallet_id}/deposits", status_code=201)
def deposit(
    wallet_id: uuid.UUID,
    data: DepositCreate,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_owned_wallet(db, user, wallet_id)

    try:
        item = create_deposit(db, wallet_id, data.amount, user.id)
        db.commit()
        db.refresh(item)
        return item
    except Exception:
        db.rollback()
        raise


@router.post("/api/wallets/{wallet_id}/withdrawals", status_code=201)
def withdrawal(
    wallet_id: uuid.UUID,
    data: WithdrawalCreate,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_owned_wallet(db, user, wallet_id)

    try:
        item = create_withdrawal(db, wallet_id, data.amount, user.id)
        db.commit()
        db.refresh(item)
        return item
    except Exception:
        db.rollback()
        raise


@router.post("/api/transfers", status_code=201)
def transfer(
    data: TransferCreate,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_owned_wallet(db, user, data.sender_wallet_id)
    
    try:
        item = create_transfer(
            db,
            data.sender_wallet_id,
            data.receiver_wallet_id,
            data.amount,
            user.id,
        )
        db.commit()
        db.refresh(item)
        return item
    except Exception:
        db.rollback()
        raise


@router.get("/api/deposits")
def list_deposits(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = (
        select(Deposit)
        .join(Wallet, Deposit.wallet_id == Wallet.id)
        .where(Wallet.user_id == user.id)
        .order_by(Deposit.created_at.desc())
    )
    return list(
        db.scalars(
            query.offset((page - 1) * page_size).limit(page_size)
        ).all()
    )


@router.get("/api/deposits/{deposit_id}")
def get_deposit(
    deposit_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = db.get(Deposit, deposit_id)

    if item is None:
        raise HTTPException(status_code=404, detail="Deposit not found.")

    require_owned_wallet(db, user, item.wallet_id)
    return item


@router.get("/api/withdrawals")
def list_withdrawals(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = (
        select(Withdrawal)
        .join(Wallet, Withdrawal.wallet_id == Wallet.id)
        .where(Wallet.user_id == user.id)
        .order_by(Withdrawal.created_at.desc())
    )
    return list(
        db.scalars(
            query.offset((page - 1) * page_size).limit(page_size)
        ).all()
    )


@router.get("/api/withdrawals/{withdrawal_id}")
def get_withdrawal(
    withdrawal_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = db.get(Withdrawal, withdrawal_id)

    if item is None:
        raise HTTPException(status_code=404, detail="Withdrawal not found.")

    require_owned_wallet(db, user, item.wallet_id)
    return item


@router.get("/api/transfers")
def list_transfers(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    wallet_ids = select(Wallet.id).where(Wallet.user_id == user.id)

    query = (
        select(Transfer)
        .where(
            or_(
                Transfer.sender_wallet_id.in_(wallet_ids),
                Transfer.receiver_wallet_id.in_(wallet_ids),
            )
        )
        .order_by(Transfer.created_at.desc())
    )

    return list(
        db.scalars(
            query.offset((page - 1) * page_size).limit(page_size)
        ).all()
    )


@router.get("/api/transfers/{transfer_id}")
def get_transfer(
    transfer_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = db.get(Transfer, transfer_id)

    if item is None:
        raise HTTPException(status_code=404, detail="Transfer not found.")

    sender = db.get(Wallet, item.sender_wallet_id)
    receiver = db.get(Wallet, item.receiver_wallet_id)

    if user.id not in {sender.user_id, receiver.user_id}:
        raise HTTPException(status_code=403, detail="Transfer access denied.")

    return item


@router.get("/api/transactions")
def transaction_history(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    transaction_type: TransactionType | None = Query(default=None, alias="type"),
    min_amount: Decimal | None = Query(default=None, ge=0),
    max_amount: Decimal | None = Query(default=None, ge=0),
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if min_amount is not None and max_amount is not None and min_amount > max_amount:
        raise HTTPException(status_code=422, detail="min_amount exceeds max_amount")

    if from_date and to_date and from_date > to_date:
        raise HTTPException(status_code=422, detail="from_date exceeds to_date")

    query = (
        select(TransactionLedger)
        .join(Wallet, TransactionLedger.wallet_id == Wallet.id)
        .where(Wallet.user_id == user.id)
    )

    if transaction_type is not None:
        query = query.where(
            TransactionLedger.transaction_type == transaction_type
        )
    if min_amount is not None:
        query = query.where(TransactionLedger.amount >= min_amount)
    if max_amount is not None:
        query = query.where(TransactionLedger.amount <= max_amount)
    if from_date is not None:
        query = query.where(TransactionLedger.created_at >= from_date)
    if to_date is not None:
        query = query.where(TransactionLedger.created_at <= to_date)

    query = query.order_by(TransactionLedger.created_at.desc())

    return list(
        db.scalars(
            query.offset((page - 1) * page_size).limit(page_size)
        ).all()
    )
@router.post("/transfers/{transfer_id}/cancel")
def cancel_transfer(
    transfer_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    transfer = db.query(Transfer).filter(
        Transfer.id == transfer_id
    ).with_for_update().first()

    if not transfer:
        raise HTTPException(
            status_code=404,
            detail="Transfer not found",
        )

    sender_wallet = db.query(Wallet).filter(
        Wallet.id == transfer.sender_wallet_id
    ).first()

    if not sender_wallet or sender_wallet.user_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="You cannot cancel this transfer",
        )

    if transfer.status != TransferStatus.PENDING:
        raise HTTPException(
            status_code=409,
            detail="Only pending transfers can be cancelled",
        )

    transfer.status = TransferStatus.CANCELLED
    db.commit()

    return {
        "message": "Transfer cancelled successfully",
        "transfer_id": str(transfer.id),
        "status": transfer.status.value,
    }
@router.post("/withdrawals/{withdrawal_id}/cancel")
def cancel_withdrawal(
    withdrawal_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    withdrawal = db.query(Withdrawal).filter(
        Withdrawal.id == withdrawal_id
    ).with_for_update().first()

    if not withdrawal:
        raise HTTPException(
            status_code=404,
            detail="Withdrawal not found",
        )

    wallet = db.query(Wallet).filter(
        Wallet.id == withdrawal.wallet_id
    ).first()

    if not wallet or wallet.user_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="You cannot cancel this withdrawal",
        )

    if withdrawal.status != WithdrawalStatus.PENDING:
        raise HTTPException(
            status_code=409,
            detail="Only pending withdrawals can be cancelled",
        )

    withdrawal.status = WithdrawalStatus.CANCELLED
    db.commit()

    return {
        "message": "Withdrawal cancelled successfully",
        "withdrawal_id": str(withdrawal.id),
        "status": withdrawal.status.value,
    }