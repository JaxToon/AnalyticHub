"""Session, CSRF, security headers and safe error handling (FR-001, FR-014, NFR 11.1)."""
import secrets
import uuid

from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware

from .db import utcnow

IDLE_TIMEOUT_MIN = 30

CSP = ("default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; "
       "frame-ancestors 'none'; form-action 'self'; base-uri 'self'; object-src 'none'")


class SecurityHeaders(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request.state.correlation_id = uuid.uuid4().hex[:12]
        response = await call_next(request)
        response.headers.setdefault("Content-Security-Policy", CSP)  # a page may set a stricter/extended one
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Correlation-ID"] = request.state.correlation_id
        return response


def csrf_token(request: Request) -> str:
    token = request.session.get("csrf")
    if not token:
        token = secrets.token_urlsafe(24)
        request.session["csrf"] = token
    return token


async def verify_csrf(request: Request):
    if request.method != "POST":
        return
    form = await request.form()
    sent = form.get("csrf_token")
    if not sent or not secrets.compare_digest(str(sent), request.session.get("csrf", "")):
        raise HTTPException(status_code=403, detail="csrf")


def session_alive(request: Request) -> bool:
    last = request.session.get("last_seen")
    now = int(utcnow().timestamp())
    if last and now - last > IDLE_TIMEOUT_MIN * 60:
        request.session.clear()
        return False
    request.session["last_seen"] = now
    return True


def flash(request: Request, message: str, tone: str = "good"):
    request.session.setdefault("flash", []).append([message, tone])


def pop_flashes(request: Request):
    return request.session.pop("flash", [])
