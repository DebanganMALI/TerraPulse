import secrets

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings

# Swagger loads its bundle from a CDN, so the API's strict CSP would blank it out.
CSP_EXEMPT = ("/docs", "/redoc", "/openapi.json")

HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "Cache-Control": "no-store",
}


class RequestContext(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request.state.request_id = secrets.token_hex(4)
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers.update(HEADERS)
        if not request.url.path.startswith(CSP_EXEMPT):
            response.headers["Content-Security-Policy"] = (
                "default-src 'none'; frame-ancestors 'none'"
            )
        return response


class BodySizeLimit(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        declared = request.headers.get("content-length")
        limit = settings().max_body_bytes
        if declared and declared.isdigit() and int(declared) > limit:
            return JSONResponse(
                {
                    "detail": f"request body exceeds {limit} bytes",
                    "code": "VALIDATION_ERROR",
                    "request_id": getattr(request.state, "request_id", None),
                },
                status_code=413,
            )
        return await call_next(request)
