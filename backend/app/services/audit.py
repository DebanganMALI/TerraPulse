from fastapi import Request
from sqlalchemy.orm import Session

from app.db.models import AuditLog


def record(
    db: Session,
    request: Request,
    action: str,
    username: str | None = None,
    target: str | None = None,
) -> None:
    db.add(
        AuditLog(
            username=username,
            action=action,
            target=target,
            request_id=getattr(request.state, "request_id", None),
            ip=request.client.host if request.client else None,
        )
    )
    db.commit()
