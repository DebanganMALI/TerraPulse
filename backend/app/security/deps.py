from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import User
from app.db.session import get_db
from app.errors import AppError
from app.schemas.common import ROLE_ORDER, ErrorCode, Role
from app.security.tokens import JWTError, decode_token

bearer = HTTPBearer(auto_error=False)

DbDep = Annotated[Session, Depends(get_db)]


def current_user(
    request: Request,
    db: DbDep,
    cred: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)] = None,
) -> User:
    if cred is None:
        raise AppError(401, ErrorCode.invalid_credentials, "missing bearer token")
    try:
        payload = decode_token(cred.credentials)
    except JWTError as exc:
        code = (
            ErrorCode.token_expired
            if "expired" in str(exc).lower()
            else ErrorCode.invalid_credentials
        )
        raise AppError(401, code, "invalid or expired token") from exc

    user = db.scalar(select(User).where(User.username == payload.get("sub")))
    if user is None:
        raise AppError(401, ErrorCode.invalid_credentials, "unknown subject")
    request.state.username = user.username
    return user


CurrentUser = Annotated[User, Depends(current_user)]


def require_role(minimum: Role):
    def dep(user: CurrentUser) -> User:
        if ROLE_ORDER[Role(user.role)] < ROLE_ORDER[minimum]:
            raise AppError(403, ErrorCode.forbidden_role, f"requires {minimum} role or higher")
        return user

    return dep


AnalystUser = Annotated[User, Depends(require_role(Role.analyst))]
AuthorityUser = Annotated[User, Depends(require_role(Role.authority))]
