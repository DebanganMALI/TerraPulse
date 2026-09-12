import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import User
from app.schemas.common import Role
from app.security.passwords import hash_password

log = logging.getLogger("terrapulse")


def seed_users(db: Session) -> None:
    s = settings()
    wanted = [
        ("viewer", Role.viewer, "Field Viewer", s.seed_viewer_password),
        ("analyst", Role.analyst, "GIS Analyst", s.seed_analyst_password),
        ("officer", Role.authority, "DDMA Officer", s.seed_authority_password),
    ]
    created = []
    for username, role, display, password in wanted:
        if db.scalar(select(User).where(User.username == username)):
            continue
        db.add(
            User(
                username=username,
                password_hash=hash_password(password),
                role=role.value,
                display_name=display,
            )
        )
        created.append(username)

    if created:
        db.commit()
        log.info("seeded users: %s", ", ".join(created))
