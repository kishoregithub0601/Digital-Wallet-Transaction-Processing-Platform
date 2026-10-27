
import uuid

from sqlalchemy.orm import Session

from app.models.enums import NotificationType
from app.models.operations import Notification


def create_notification(
    db: Session,
    user_id: uuid.UUID,
    notification_type: NotificationType,
    title: str,
    message: str,
) -> Notification:
    notification = Notification(
        user_id=user_id,
        notification_type=notification_type,
        title=title,
        message=message,
    )
    db.add(notification)
    db.flush()
    return notification
