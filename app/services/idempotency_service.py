
import hashlib
import json
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models.enums import IdempotencyStatus
from app.models.operations import IdempotencyKey


def request_fingerprint(payload: dict) -> str:
    """Create a stable hash for the request body."""
    canonical_payload = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()


def begin_idempotent_operation(
    db: Session,
    user_id: UUID,
    operation: str,
    idempotency_key: str,
    payload: dict,
):
    """
    Reserve an idempotency key or return the previous completed response.

    Returns:
        (record, cached_response)
        cached_response is None when a new operation may proceed.
    """
    if not idempotency_key or not idempotency_key.strip():
        raise HTTPException(
            status_code=400,
            detail="Idempotency-Key header cannot be empty",
        )

    request_hash = request_fingerprint(payload)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=24)

    statement = (
        insert(IdempotencyKey)
        .values(
            user_id=user_id,
            operation=operation,
            key=idempotency_key,
            request_hash=request_hash,
            status=IdempotencyStatus.PROCESSING,
            created_at=datetime.now(timezone.utc),
            expires_at=expires_at,
        )
        .on_conflict_do_nothing(
            index_elements=["user_id", "operation", "key"]
        )
    )

    result = db.execute(statement)
    db.flush()

    record = db.execute(
        select(IdempotencyKey)
        .where(
            IdempotencyKey.user_id == user_id,
            IdempotencyKey.operation == operation,
            IdempotencyKey.key == idempotency_key,
        )
        .with_for_update()
    ).scalar_one()

    if result.rowcount == 1:
        return record, None

    if record.request_hash != request_hash:
        raise HTTPException(
            status_code=409,
            detail=(
                "This Idempotency-Key was already used with "
                "a different request"
            ),
        )

    if record.status == IdempotencyStatus.COMPLETED:
        return record, record.response_data

    raise HTTPException(
        status_code=409,
        detail="This operation is already being processed or needs review",
    )


def complete_idempotent_operation(
    db: Session,
    record: IdempotencyKey,
    response_data: dict,
    resource_id: UUID | None = None,
) -> None:
    """Save the response so a retry can return the same result."""
    record.status = IdempotencyStatus.COMPLETED
    record.response_data = response_data
    record.resource_id = resource_id
    db.add(record)
    db.commit()
    db.refresh(record)
