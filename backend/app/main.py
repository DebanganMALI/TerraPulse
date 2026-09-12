import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api.router import api_router
from app.config import settings
from app.db import models  # noqa: F401  - registers tables on Base
from app.db.seed import seed_users
from app.db.session import Base, SessionLocal, engine
from app.errors import register_error_handlers
from app.security.limiter import limiter, rate_limit_handler
from app.security.middleware import BodySizeLimit, RequestContext

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger("terrapulse")

STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = settings()
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed_users(db)
    log.info("starting %s v%s (pipeline=%s)", s.app_name, s.version, s.pipeline_mode)
    yield


def create_app() -> FastAPI:
    s = settings()
    app = FastAPI(
        title=s.app_name,
        version=s.version,
        description="AI satellite change detection, risk prediction and early warning.",
        lifespan=lifespan,
    )

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_handler)

    app.add_middleware(SlowAPIMiddleware)
    app.add_middleware(BodySizeLimit)
    app.add_middleware(RequestContext)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=s.origins,
        allow_credentials=False,  # bearer tokens, not cookies: no CSRF surface
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type"],
    )

    register_error_handlers(app)
    app.include_router(api_router)

    STATIC_DIR.mkdir(parents=True, exist_ok=True)
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    return app


app = create_app()
