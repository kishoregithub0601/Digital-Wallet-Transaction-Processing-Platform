
import uuid
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.enums import SuspiciousStatus
from app.models.operations import SuspiciousTransaction, TransactionLimit
from app.models.wallet import Wallet


def flag_suspicious_transaction(
    db: Session,
    wallet: Wallet,
    transaction_type: str,
    transaction_id: uuid.UUID,
    amount: Decimal,
    limit: TransactionLimit,
    reason: str | None = None,
) -> SuspiciousTransaction | None:
    reasons = []

    if amount >= limit.suspicious_amount_threshold:
        reasons.append("Transaction amount exceeds monitoring threshold.")

    if wallet.status.value == "FROZEN":
        reasons.append("Wallet is frozen.")

    if reason:
        reasons.append(reason)

    if not reasons:
        return None

    item = SuspiciousTransaction(
        transaction_type=transaction_type,
        transaction_id=transaction_id,
        wallet_id=wallet.id,
        reason=" ".join(reasons),
        status=SuspiciousStatus.REVIEW_REQUIRED,
    )

    db.add(item)
    db.flush()

    return item
