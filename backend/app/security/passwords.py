from passlib.context import CryptContext

_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)

# compared against when the username does not exist, so a missing user costs the
# same time as a wrong password and login timing cannot enumerate accounts
DUMMY_HASH = _ctx.hash("no-such-user")


def hash_password(raw: str) -> str:
    return _ctx.hash(raw)


def verify_password(raw: str, hashed: str | None) -> bool:
    return _ctx.verify(raw, hashed or DUMMY_HASH) and hashed is not None
