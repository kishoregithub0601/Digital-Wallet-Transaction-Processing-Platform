
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.wallet import Wallet


def get_wallet(
    db: Session,
    wallet_id: uuid.UUID,
    *,
    for_update: bool = False,
) -> Wallet | None:
    query = select(Wallet).where(Wallet.id == wallet_id)

    if for_update:
        query = query.with_for_update()

    return db.scalar(query)


def get_user_wallets(
    db: Session,
    user_id: uuid.UUID,
) -> list[Wallet]:
    return list(
        db.scalars(
            select(Wallet)
            .where(Wallet.user_id == user_id)
            .order_by(Wallet.created_at.desc())
        ).all()
    )
