
import uuid

from sqlalchemy.orm import Session

from app.models.enums import WalletStatus
from app.models.user import User
from app.models.wallet import Wallet
from app.repositories.wallet_repository import get_wallet, get_user_wallets


class WalletDomainError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def create_wallet(
    db: Session,
    user: User,
    currency: str = "INR",
) -> Wallet:
    currency = currency.upper()

    if len(currency) != 3 or not currency.isalpha():
        raise WalletDomainError("INVALID_CURRENCY", "Invalid currency.")

    wallet = Wallet(
        user_id=user.id,
        currency=currency,
        available_balance=0,
        pending_balance=0,
        status=WalletStatus.ACTIVE,
    )

    db.add(wallet)
    db.flush()
    return wallet



def list_wallets(
    db: Session,
    user: User,
) -> list[Wallet]:
    from app.models.user import UserRole

    if user.role in {UserRole.ADMIN, UserRole.SUPER_ADMIN}:
        return list(
            db.query(Wallet)
            .order_by(Wallet.created_at.desc())
            .all()
        )

    return get_user_wallets(db, user.id)



def get_wallet_for_user(
    db: Session,
    user: User,
    wallet_id: uuid.UUID,
) -> Wallet:
    wallet = get_wallet(db, wallet_id)

    if wallet is None:
        raise WalletDomainError("WALLET_NOT_FOUND", "Wallet not found.", 404)

    if (
        wallet.user_id != user.id
        and user.role not in {user.role.ADMIN, user.role.SUPER_ADMIN}
    ):
        raise WalletDomainError(
            "FORBIDDEN",
            "You cannot access this wallet.",
            403,
        )

    return wallet


def change_wallet_status(
    db: Session,
    wallet: Wallet,
    action: str,
) -> Wallet:
    if action == "freeze":
        if wallet.status != WalletStatus.ACTIVE:
            raise WalletDomainError(
                "INVALID_WALLET_STATE",
                "Only active wallets can be frozen.",
                409,
            )
        wallet.status = WalletStatus.FROZEN

    elif action == "unfreeze":
        if wallet.status != WalletStatus.FROZEN:
            raise WalletDomainError(
                "INVALID_WALLET_STATE",
                "Only frozen wallets can be unfrozen.",
                409,
            )
        wallet.status = WalletStatus.ACTIVE

    else:
        raise WalletDomainError("INVALID_ACTION", "Unsupported wallet action.")

    db.flush()
    return wallet
