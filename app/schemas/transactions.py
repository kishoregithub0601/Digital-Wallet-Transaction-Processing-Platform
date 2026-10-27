
import uuid
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class AmountRequest(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)


class DepositCreate(AmountRequest):
    pass


class WithdrawalCreate(AmountRequest):
    pass


class TransferCreate(AmountRequest):
    sender_wallet_id: uuid.UUID
    receiver_wallet_id: uuid.UUID


class RefundCreate(AmountRequest):
    original_transaction_type: str = Field(
        pattern=r"^(TRANSFER|DEPOSIT|WITHDRAWAL)$"
    )
    original_transaction_id: uuid.UUID
    reason: str | None = Field(default=None, max_length=500)


class TransactionResponse(BaseModel):
    id: uuid.UUID
    amount: Decimal
    currency: str
    status: str
    reference_number: str

    model_config = ConfigDict(from_attributes=True)
