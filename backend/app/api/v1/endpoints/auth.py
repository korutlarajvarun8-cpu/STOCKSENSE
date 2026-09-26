from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.redis import get_redis
from app.services.auth_service import AuthService
from app.schemas.auth import (
    SignupRequest, LoginRequest, TokenResponse, ForgotPasswordRequest,
    VerifyOTPRequest, ChangePasswordRequest, RefreshRequest, UserResponse
)
from app.models.user import User
from app.core.security import get_password_hash, verify_password

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/signup", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def signup(
    request: SignupRequest,
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
):
    service = AuthService(db, redis)
    user = await service.signup(
        full_name=request.full_name,
        email=request.email,
        password=request.password,
    )
    await db.commit()
    return user


@router.post("/login", response_model=TokenResponse)
async def login(
    request: LoginRequest,
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
):
    service = AuthService(db, redis)
    user, access_token, refresh_token = await service.login(request.email, request.password)
    await db.commit()
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=UserResponse.model_validate(user),
    )


@router.post("/refresh")
async def refresh_token(
    request: RefreshRequest,
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
):
    service = AuthService(db, redis)
    access_token = await service.refresh_access_token(request.refresh_token)
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/logout")
async def logout(
    current_user: User = Depends(get_current_user),
    redis=Depends(get_redis),
):
    service = AuthService(None, redis)
    await service.logout(current_user.id)
    return {"message": "Successfully logged out."}


@router.post("/forgot-password")
async def forgot_password(
    request: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
):
    service = AuthService(db, redis)
    otp = await service.request_password_reset(request.email)
    # In production, send email. In dev, include in response for testing.
    return {"message": "If this email exists, an OTP has been sent.", "dev_otp": otp}


@router.post("/verify-otp")
async def verify_otp(
    request: VerifyOTPRequest,
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
):
    service = AuthService(db, redis)
    success = await service.verify_otp_and_reset(request.email, request.otp, request.new_password)
    await db.commit()
    if success:
        return {"message": "Password reset successfully. You can now log in."}


@router.post("/change-password")
async def change_password(
    request: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not verify_password(request.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect.")

    await db.execute(
        update(User)
        .where(User.id == current_user.id)
        .values(hashed_password=get_password_hash(request.new_password))
    )
    await db.commit()
    return {"message": "Password changed successfully."}


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user
