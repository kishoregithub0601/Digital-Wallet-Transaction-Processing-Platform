
import uuid

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.enums import WalletStatus


class Wallet(Base):
    __tablename__ = "wallets"

    __table_args__ = (
        CheckConstraint(
            "available_balance >= 0",
            name="ck_wallet_available_nonnegative",
        ),
        CheckConstraint(
            "pending_balance >= 0",
            name="ck_wallet_pending_nonnegative",
        ),
        CheckConstraint(
            "char_length(currency) = 3",
            name="ck_wallet_currency_length",
        ),
        Index("ix_wallet_user_status", "user_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="INR",
    )

    available_balance: Mapped[Decimal] = mapped_column(
        Numeric(18, 2),
        nullable=False,
        default=Decimal("0.00"),
        server_default="0.00",
    )

    pending_balance: Mapped[Decimal] = mapped_column(
        Numeric(18, 2),
        nullable=False,
        default=Decimal("0.00"),
        server_default="0.00",
    )

    status: Mapped[WalletStatus] = mapped_column(
        Enum(WalletStatus, name="wallet_status"),
        nullable=False,
        default=WalletStatus.ACTIVE,
        server_default="ACTIVE",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
