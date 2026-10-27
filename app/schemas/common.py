
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.models.enums import NotificationType


class NotificationResponse(BaseModel):
    id: uuid.UUID
    notification_type: NotificationType
    title: str
    message: str
    is_read: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TransactionHistoryItem(BaseModel):
    id: uuid.UUID
    transaction_type: str
    amount: Any
    balance_before: Any
    balance_after: Any
    reference_type: str
    reference_id: uuid.UUID
    description: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
