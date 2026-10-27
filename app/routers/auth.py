
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session
import uuid
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
)
from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User, UserRole
from app.schemas.auth import (
    ChangePasswordRequest,
    TokenResponse,
    UserLogin,
    UserRegister,
    UserResponse,
)

from datetime import datetime, timedelta, timezone
import jwt

from app.core.config import settings
from app.core.security import decode_token
from app.models.refresh_token import RefreshToken
from app.schemas.auth import RefreshRequest


router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(
    data: UserRegister,
    db: Session = Depends(get_db),
):
    email = str(data.email).lower()

    existing_user = db.scalar(
        select(User).where(User.email == email)
    )

    if existing_user:
        raise HTTPException(
            status_code=409,
            detail="Email is already registered.",
        )

    user = User(
        full_name=data.full_name,
        email=email,
        password_hash=hash_password(data.password),
        role=UserRole.CUSTOMER,
    )

    db.add(user)

    try:
        db.commit()
        db.refresh(user)
    except Exception:
        db.rollback()
        raise

    return user



@router.post("/login", response_model=TokenResponse)
def login(
    data: UserLogin,
    db: Session = Depends(get_db),
):
    email = str(data.email).lower()
    user = db.scalar(select(User).where(User.email == email))

    if (
        user is None
        or not verify_password(data.password, user.password_hash)
        or not user.is_active
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password.",
        )

    access_token = create_access_token(str(user.id))
    refresh_token = create_refresh_token(str(user.id))

    try:
        save_refresh_token(db, refresh_token, user.id)
        db.commit()
    except Exception:
        db.rollback()
        raise

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
    )


@router.get("/me", response_model=UserResponse)
def get_me(
    current_user: User = Depends(get_current_user),
):
    return current_user


@router.post("/change-password")
def change_password(
    data: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(
        data.current_password,
        current_user.password_hash,
    ):
        raise HTTPException(
            status_code=400,
            detail="Current password is incorrect.",
        )

    if data.current_password == data.new_password:
        raise HTTPException(
            status_code=400,
            detail="New password must differ from current password.",
        )

    current_user.password_hash = hash_password(data.new_password)
    db.commit()

    return {"message": "Password changed successfully."}

def save_refresh_token(db: Session, token: str, user_id) -> None:
    payload = decode_token(token)

    db.add(
        RefreshToken(
            user_id=user_id,
            jti=payload["jti"],
            expires_at=datetime.fromtimestamp(
                payload["exp"], tz=timezone.utc
            ),
        )
    )

@router.post("/refresh", response_model=TokenResponse)
def refresh(
    data: RefreshRequest,
    db: Session = Depends(get_db),
):
    try:
        payload = decode_token(data.refresh_token)
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=401,
                detail="Invalid refresh token.",
            )

        user_id = uuid.UUID(payload["sub"])
        token_id = payload["jti"]

    except (jwt.InvalidTokenError, ValueError, KeyError, TypeError):
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired refresh token.",
        )

    stored = db.scalar(
        select(RefreshToken)
        .where(RefreshToken.jti == token_id)
        .with_for_update()
    )

    now = datetime.now(timezone.utc)

    if (
        stored is None
        or stored.revoked_at is not None
        or stored.expires_at <= now
    ):
        raise HTTPException(
            status_code=401,
            detail="Refresh token has expired or been revoked.",
        )

    user = db.get(User, user_id)

    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="Inactive user.")

    try:
        stored.revoked_at = now

        access_token = create_access_token(str(user.id))
        new_refresh = create_refresh_token(str(user.id))

        save_refresh_token(db, new_refresh, user.id)
        db.commit()

    except Exception:
        db.rollback()
        raise

    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh,
    )


@router.post("/logout")
def logout(
    data: RefreshRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        payload = decode_token(data.refresh_token)

        if (
            payload.get("type") != "refresh"
            or payload.get("sub") != str(current_user.id)
        ):
            raise HTTPException(
                status_code=401,
                detail="Invalid refresh token.",
            )

    except (jwt.InvalidTokenError, ValueError, KeyError, TypeError):
        raise HTTPException(
            status_code=401,
            detail="Invalid refresh token.",
        )

    stored = db.scalar(
        select(RefreshToken)
        .where(RefreshToken.jti == payload["jti"])
        .with_for_update()
    )

    if stored is None or stored.revoked_at is not None:
        raise HTTPException(
            status_code=401,
            detail="Refresh token is already revoked or invalid.",
        )

    stored.revoked_at = datetime.now(timezone.utc)
    db.commit()

    return {"message": "Logged out successfully."}
