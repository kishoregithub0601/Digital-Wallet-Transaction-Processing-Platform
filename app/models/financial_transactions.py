
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
from app.models.enums import (
    DepositStatus,
    RefundStatus,
    TransferStatus,
    WithdrawalStatus,
)


class Deposit(Base):
    __tablename__ = "deposits"

    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_deposit_amount_positive"),
        Index("ix_deposit_wallet_created", "wallet_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    wallet_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("wallets.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False
    )
    currency: Mapped[str] = mapped_column(
        String(3), nullable=False
    )
    status: Mapped[DepositStatus] = mapped_column(
        Enum(DepositStatus, name="deposit_status"),
        default=DepositStatus.PENDING,
        nullable=False,
    )
    reference_number: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class Withdrawal(Base):
    __tablename__ = "withdrawals"

    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_withdrawal_amount_positive"),
        Index("ix_withdrawal_wallet_created", "wallet_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    wallet_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("wallets.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False
    )
    currency: Mapped[str] = mapped_column(
        String(3), nullable=False
    )
    status: Mapped[WithdrawalStatus] = mapped_column(
        Enum(WithdrawalStatus, name="withdrawal_status"),
        default=WithdrawalStatus.PENDING,
        nullable=False,
    )
    reference_number: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class Transfer(Base):
    __tablename__ = "transfers"

    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_transfer_amount_positive"),
        CheckConstraint(
            "sender_wallet_id != receiver_wallet_id",
            name="ck_transfer_different_wallets",
        ),
        Index("ix_transfer_sender_created", "sender_wallet_id", "created_at"),
        Index("ix_transfer_receiver_created", "receiver_wallet_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    sender_wallet_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("wallets.id", ondelete="RESTRICT"),
        nullable=False,
    )
    receiver_wallet_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("wallets.id", ondelete="RESTRICT"),
        nullable=False,
    )
    amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False
    )
    currency: Mapped[str] = mapped_column(
        String(3), nullable=False
    )
    status: Mapped[TransferStatus] = mapped_column(
        Enum(TransferStatus, name="transfer_status"),
        default=TransferStatus.PENDING,
        nullable=False,
    )
    reference_number: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class Refund(Base):
    __tablename__ = "refunds"

    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_refund_amount_positive"),
        Index("ix_refund_status_created", "status", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    
    original_transaction_type: Mapped[str] = mapped_column(
    String(50),
    nullable=False,
    )

    original_transaction_id: Mapped[uuid.UUID] = mapped_column(
    UUID(as_uuid=True),
    nullable=False,
    index=True,
    )

    wallet_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("wallets.id", ondelete="RESTRICT"),
        nullable=False,
    )
    amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False
    )
    status: Mapped[RefundStatus] = mapped_column(
        Enum(RefundStatus, name="refund_status"),
        default=RefundStatus.REQUESTED,
        nullable=False,
    )
    reason: Mapped[str | None] = mapped_column(
        String(500), nullable=True
    )
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
    )
    reference_number: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
