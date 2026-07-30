"""Anonymous signed-session middleware for the hackathon MVP."""

import base64
import hashlib
import hmac
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from backend.app.config import BackendSettings


def _signature(value: str, secret: str) -> str:
    digest = hmac.new(secret.encode(), value.encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip("=")


def _encode_session(owner_id: str, secret: str) -> str:
    return f"{owner_id}.{_signature(owner_id, secret)}"


def _decode_session(token: str | None, secret: str) -> str | None:
    if not token or "." not in token:
        return None
    owner_id, signature = token.rsplit(".", 1)
    if not owner_id or not hmac.compare_digest(signature, _signature(owner_id, secret)):
        return None
    return owner_id


class AnonymousSessionMiddleware(BaseHTTPMiddleware):
    """Assign an opaque, signed owner ID without exposing backend state IDs."""

    def __init__(self, app, settings: BackendSettings):
        super().__init__(app)
        self.settings = settings

    async def dispatch(self, request: Request, call_next):
        token = request.cookies.get(self.settings.session_cookie_name)
        owner_id = _decode_session(token, self.settings.anonymous_session_secret)
        is_new = owner_id is None
        if owner_id is None:
            owner_id = f"anon_{uuid.uuid4().hex}"
        request.state.owner_id = owner_id

        response = await call_next(request)
        if is_new:
            response.set_cookie(
                self.settings.session_cookie_name,
                _encode_session(owner_id, self.settings.anonymous_session_secret),
                httponly=True,
                secure=self.settings.session_cookie_secure,
                samesite="lax",
                path="/",
            )
        return response
