
import uuid
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import WalletStatus


class WalletCreate(BaseModel):
    currency: str = Field(default="INR", pattern=r"^[A-Z]{3}$")


class WalletUpdate(BaseModel):
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")


class WalletResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    currency: str
    available_balance: Decimal
    pending_balance: Decimal
    status: WalletStatus

    model_config = ConfigDict(from_attributes=True)
