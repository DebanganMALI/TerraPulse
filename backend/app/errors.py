import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import settings
from app.schemas.common import ErrorCode

log = logging.getLogger("terrapulse")


class AppError(Exception):
    def __init__(self, status: int, code: ErrorCode, detail: str):
        self.status = status
        self.code = code
        self.detail = detail
        super().__init__(detail)


def _body(detail: str, code: ErrorCode, request: Request) -> dict:
    return {
        "detail": detail,
        "code": code.value,
        "request_id": getattr(request.state, "request_id", None),
    }


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError):
        return JSONResponse(_body(exc.detail, exc.code, request), status_code=exc.status)

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError):
        first = exc.errors()[0] if exc.errors() else {}
        loc = ".".join(str(p) for p in first.get("loc", [])[1:])
        msg = f"{loc}: {first.get('msg', 'invalid input')}" if loc else "invalid input"
        return JSONResponse(_body(msg, ErrorCode.validation_error, request), status_code=422)

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException):
        code = {
            401: ErrorCode.invalid_credentials,
            403: ErrorCode.forbidden_role,
            404: ErrorCode.aoi_not_found,
            409: ErrorCode.job_already_running,
            429: ErrorCode.rate_limited,
        }.get(exc.status_code, ErrorCode.internal_error)
        return JSONResponse(_body(str(exc.detail), code, request), status_code=exc.status_code)

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        log.exception("unhandled error", extra={"path": request.url.path})
        detail = repr(exc) if settings().debug else "internal server error"
        return JSONResponse(_body(detail, ErrorCode.internal_error, request), status_code=500)
