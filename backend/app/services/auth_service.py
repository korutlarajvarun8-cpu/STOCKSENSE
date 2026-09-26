"""
Authentication service — signup, login, OTP, password management.
"""
import uuid
import json
from datetime import datetime, timedelta, timezone
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from fastapi import HTTPException, status

from app.models.user import User, UserRole
from app.core.security import (
    verify_password, get_password_hash, create_access_token,
    create_refresh_token, decode_token, generate_otp,
)
from app.core.config import settings
from app.models.system import AuditLog


class AuthService:
    def __init__(self, db: AsyncSession, redis=None):
        self.db = db
        self.redis = redis

    async def signup(
        self,
        full_name: str,
        email: str,
        password: str,
        role: UserRole = UserRole.VIEWER,
    ) -> User:
        """Register a new user."""
        # Check email uniqueness
        result = await self.db.execute(select(User).where(User.email == email.lower()))
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="An account with this email already exists.",
            )

        user = User(
            full_name=full_name,
            email=email.lower(),
            hashed_password=get_password_hash(password),
            role=role,
            is_active=True,
            is_email_verified=True,  # Skip email verification for dev
        )
        self.db.add(user)
        await self.db.flush()
        await self.db.refresh(user)

        # Audit log
        self.db.add(AuditLog(
            user_id=user.id,
            action="USER_SIGNUP",
            resource_type="user",
            resource_id=str(user.id),
            after_state={"email": email, "role": role},
        ))

        return user

    async def login(self, email: str, password: str) -> tuple[User, str, str]:
        """Authenticate user and return tokens."""
        result = await self.db.execute(select(User).where(User.email == email.lower()))
        user = result.scalar_one_or_none()

        if not user or not verify_password(password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password.",
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your account has been deactivated.",
            )

        # Update last login
        await self.db.execute(
            update(User).where(User.id == user.id).values(
                last_login=datetime.now(timezone.utc)
            )
        )
        await self.db.flush()

        access_token = create_access_token(
            data={"sub": str(user.id), "role": user.role, "email": user.email}
        )
        refresh_token = create_refresh_token(
            data={"sub": str(user.id)}
        )

        # Store refresh token in Redis
        if self.redis:
            await self.redis.setex(
                f"refresh:{user.id}",
                settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
                refresh_token,
            )

        self.db.add(AuditLog(
            user_id=user.id,
            action="USER_LOGIN",
            resource_type="user",
            resource_id=str(user.id),
        ))

        return user, access_token, refresh_token

    async def request_password_reset(self, email: str) -> str:
        """Send OTP for password reset."""
        result = await self.db.execute(select(User).where(User.email == email.lower()))
        user = result.scalar_one_or_none()

        # Always return success to prevent user enumeration
        if not user:
            return "If this email exists, you will receive an OTP."

        otp = generate_otp()
        otp_key = f"otp:{email.lower()}"

        if self.redis:
            otp_data = json.dumps({
                "otp": otp,
                "attempts": 0,
                "user_id": str(user.id),
            })
            await self.redis.setex(otp_key, settings.OTP_EXPIRE_MINUTES * 60, otp_data)

        # In production, send via email. For dev, log it.
        print(f"[DEV] OTP for {email}: {otp}")
        return otp  # Return for dev/test purposes

    async def verify_otp_and_reset(
        self, email: str, otp: str, new_password: str
    ) -> bool:
        """Verify OTP and reset password."""
        if not self.redis:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="OTP service unavailable.",
            )

        otp_key = f"otp:{email.lower()}"
        raw = await self.redis.get(otp_key)

        if not raw:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="OTP expired or not found. Please request a new one.",
            )

        otp_data = json.loads(raw)

        if otp_data["attempts"] >= settings.OTP_MAX_ATTEMPTS:
            await self.redis.delete(otp_key)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many invalid attempts. Please request a new OTP.",
            )

        if otp_data["otp"] != otp:
            otp_data["attempts"] += 1
            await self.redis.set(otp_key, json.dumps(otp_data))
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid OTP. {settings.OTP_MAX_ATTEMPTS - otp_data['attempts']} attempts remaining.",
            )

        # OTP valid — reset password
        user_id = otp_data["user_id"]
        await self.db.execute(
            update(User)
            .where(User.id == uuid.UUID(user_id))
            .values(hashed_password=get_password_hash(new_password))
        )
        await self.redis.delete(otp_key)
        await self.db.flush()
        return True

    async def refresh_access_token(self, refresh_token: str) -> str:
        """Issue new access token from refresh token."""
        payload = decode_token(refresh_token)
        if not payload or payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token.",
            )

        user_id = payload.get("sub")
        if self.redis:
            stored = await self.redis.get(f"refresh:{user_id}")
            if stored != refresh_token:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Refresh token has been invalidated.",
                )

        result = await self.db.execute(select(User).where(User.id == uuid.UUID(user_id)))
        user = result.scalar_one_or_none()
        if not user or not user.is_active:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found.")

        return create_access_token(
            data={"sub": str(user.id), "role": user.role, "email": user.email}
        )

    async def logout(self, user_id: uuid.UUID):
        """Invalidate refresh token."""
        if self.redis:
            await self.redis.delete(f"refresh:{user_id}")
