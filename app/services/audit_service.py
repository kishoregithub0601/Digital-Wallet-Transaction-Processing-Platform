
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models.operations import AuditLog


def record_audit(
    db: Session,
    action: str,
    entity: str,
    entity_id: str | None = None,
    user_id: uuid.UUID | None = None,
    ip_address: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> AuditLog:
    entry = AuditLog(
        user_id=user_id,
        action=action,
        entity=entity,
        entity_id=entity_id,
        ip_address=ip_address,
        metadata_json=metadata,
    )
    db.add(entry)
    db.flush()
    return entry
