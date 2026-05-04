from fastapi import APIRouter, Depends, HTTPException, status
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from .database import get_db
from .dependencies import get_current_user
from .models import User
from .schemas import (
    AccessToken,
    RefreshRequest,
    TokenPair,
    UserOut,
    UserLogin,
    UserRegister,
)
from .security import create_access_token, create_refresh_token, get_user_id_from_token
from .service import authenticate_user, create_user, get_user_by_email, get_user_by_id

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(body: UserRegister, db: AsyncSession = Depends(get_db)) -> User:
    existing = await get_user_by_email(db, body.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this email already exists",
        )
    return await create_user(db, email=body.email, password=body.password)


@router.post("/login", response_model=TokenPair)
async def login(body: UserLogin, db: AsyncSession = Depends(get_db)) -> TokenPair:
    user = await authenticate_user(db, body.email, body.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    return TokenPair(
        access_token=create_access_token(user.id, user.email),
        refresh_token=create_refresh_token(user.id),
    )


@router.post("/refresh", response_model=AccessToken)
async def refresh(
    body: RefreshRequest, db: AsyncSession = Depends(get_db)
) -> AccessToken:
    try:
        user_id = get_user_id_from_token(body.refresh_token, expected_type="refresh")
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )
    user = await get_user_by_id(db, user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found"
        )
    return AccessToken(access_token=create_access_token(user.id, user.email))


@router.get("/me", response_model=UserOut)
async def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user
