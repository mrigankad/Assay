"""JWT auth backed by the users table."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select

from src.core.access import column_to_groups, groups_to_column
from src.core.config import settings
from src.core.dependency_injection import AdminUser, CurrentUser, DbSession
from src.core.logger import get_logger
from src.core.security import TokenPair, create_token_pair, hash_password, verify_password, verify_refresh_token
from src.infrastructure.database import User

router = APIRouter()
logger = get_logger(__name__)


class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=6)


class RefreshRequest(BaseModel):
    refresh_token: str


class UserResponse(BaseModel):
    user_id: str
    username: str
    email: Optional[str] = None
    role: str = "user"
    tenant_id: Optional[str] = None
    groups: list[str] = []
    issuer: str = "local"


class UserUpdateRequest(BaseModel):
    role: Optional[str] = Field(default=None, pattern="^(user|admin)$")
    groups: Optional[list[str]] = None
    tenant_id: Optional[str] = None
    is_active: Optional[bool] = None


def _tokens_for(user: User) -> TokenPair:
    return create_token_pair(
        user_id=str(user.id), username=user.username, email=user.email,
        tenant_id=user.tenant_id or settings.default_tenant_id, role=user.role or "user",
        groups=column_to_groups(user.groups),
    )


@router.post("/login", response_model=TokenPair)
async def login(request: LoginRequest, db: DbSession):
    ident = request.username.strip()
    user = await db.scalar(select(User).where((User.username == ident) | (User.email == ident.lower())))
    if user is None or not user.is_active or not verify_password(request.password, user.password_hash):
        logger.warning("Failed login attempt", username=request.username)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid username or password")
    logger.info("User logged in", user_id=str(user.id))
    return _tokens_for(user)


async def _user_count(db) -> int:
    from sqlalchemy import func
    return int(await db.scalar(select(func.count()).select_from(User)) or 0)


def _signup_open() -> bool:
    import os
    return os.getenv("ALLOW_SIGNUP", "false").lower() in {"1", "true", "yes"}


@router.get("/methods")
async def sign_in_methods(db: DbSession):
    """What the sign-in page should offer, and whether this is a fresh install."""
    import os
    first_run = await _user_count(db) == 0
    entra = settings.auth_mode in ("entra", "both") and bool(settings.entra_tenant_id and settings.entra_client_id)
    return {
        "password": settings.auth_mode in ("local", "both"),
        "entra": {"enabled": entra, "tenant_id": settings.entra_tenant_id or None,
                  "client_id": settings.entra_client_id or None} if entra else {"enabled": False},
        "oidc": {"enabled": bool(os.getenv("OIDC_ISSUER")), "issuer": os.getenv("OIDC_ISSUER") or None,
                 "client_id": os.getenv("OIDC_CLIENT_ID") or None, "label": os.getenv("OIDC_LABEL", "SSO")},
        "signup_open": first_run or _signup_open(),
        "first_run": first_run,
    }


@router.post("/register", response_model=TokenPair, status_code=status.HTTP_201_CREATED)
async def register(request: RegisterRequest, db: DbSession):
    """First account on a fresh install becomes the admin. After that, sign-up is
    closed unless ALLOW_SIGNUP=true (admins invite people instead)."""
    first = await _user_count(db) == 0
    if not first and not _signup_open():
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Sign-up is closed. Ask an admin for an invite.")
    exists = await db.scalar(select(User).where((User.username == request.username) | (User.email == request.email)))
    if exists is not None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Username or email already exists")
    user = User(username=request.username, email=request.email.lower(), password_hash=hash_password(request.password),
                tenant_id=settings.default_tenant_id, role="admin" if first else "user", groups="")
    db.add(user)
    await db.flush()
    logger.info("User registered", user_id=str(user.id))
    return _tokens_for(user)


@router.post("/refresh", response_model=TokenPair)
async def refresh(request: RefreshRequest, db: DbSession):
    data = verify_refresh_token(request.refresh_token)
    if data is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired refresh token")
    user = await db.scalar(select(User).where(User.username == data.username))
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found")
    return _tokens_for(user)


@router.get("/me", response_model=UserResponse)
async def me(user: CurrentUser):
    return UserResponse(user_id=user.user_id, username=user.username, email=user.email, role=user.role,
                        tenant_id=user.tenant_id, groups=user.groups, issuer=user.issuer)


@router.get("/users", response_model=list[UserResponse])
async def list_users(admin: AdminUser, db: DbSession):
    rows = (await db.execute(select(User).order_by(User.username))).scalars().all()
    return [UserResponse(user_id=str(u.id), username=u.username, email=u.email, role=u.role or "user",
                         tenant_id=u.tenant_id, groups=column_to_groups(u.groups)) for u in rows]


@router.put("/users/{username}", response_model=UserResponse)
async def update_user(username: str, request: UserUpdateRequest, admin: AdminUser, db: DbSession):
    """Admin: set role, groups, tenant or active flag. Takes effect on the user's next login/refresh."""
    user = await db.scalar(select(User).where(User.username == username))
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    if request.role is not None:
        user.role = request.role
    if request.groups is not None:
        user.groups = groups_to_column(request.groups)
    if request.tenant_id is not None:
        user.tenant_id = request.tenant_id
    if request.is_active is not None:
        user.is_active = request.is_active
    await db.flush()
    logger.info("User updated by admin", username=username, admin=admin.username)
    return UserResponse(user_id=str(user.id), username=user.username, email=user.email, role=user.role or "user",
                        tenant_id=user.tenant_id, groups=column_to_groups(user.groups))
