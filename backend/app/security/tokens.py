import secrets
from datetime import UTC, datetime, timedelta

from jose import JWTError, jwt

from app.config import settings


def create_access_token(username: str, role: str) -> tuple[str, int]:
    s = settings()
    ttl = s.access_token_minutes * 60
    now = datetime.now(UTC)
    payload = {
        "sub": username,
        "role": role,
        "iat": now,
        "exp": now + timedelta(seconds=ttl),
        "jti": secrets.token_hex(8),
    }
    return jwt.encode(payload, s.jwt_secret, algorithm=s.jwt_algorithm), ttl


def decode_token(token: str) -> dict:
    s = settings()
    return jwt.decode(token, s.jwt_secret, algorithms=[s.jwt_algorithm])


__all__ = ["JWTError", "create_access_token", "decode_token"]
