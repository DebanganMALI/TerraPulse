from fastapi import APIRouter, Request
from sqlalchemy import select

from app.db.models import User
from app.errors import AppError
from app.schemas.auth import LoginRequest, TokenResponse, UserOut
from app.schemas.common import ErrorCode
from app.security.deps import CurrentUser, DbDep
from app.security.limiter import limiter
from app.security.passwords import verify_password
from app.security.tokens import create_access_token
from app.services import audit

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute")
def login(request: Request, body: LoginRequest, db: DbDep) -> TokenResponse:
    user = db.scalar(select(User).where(User.username == body.username))
    if not verify_password(body.password, user.password_hash if user else None):
        audit.record(db, request, "login_failed", username=body.username)
        raise AppError(401, ErrorCode.invalid_credentials, "incorrect username or password")

    token, ttl = create_access_token(user.username, user.role)
    audit.record(db, request, "login", username=user.username)
    return TokenResponse(
        access_token=token,
        expires_in=ttl,
        user=UserOut(
            username=user.username, role=user.role, display_name=user.display_name
        ),
    )


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser) -> UserOut:
    return UserOut(username=user.username, role=user.role, display_name=user.display_name)
