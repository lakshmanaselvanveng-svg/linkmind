import ipaddress
import socket
from urllib.parse import urlsplit, urlunsplit

import requests
from fastapi import HTTPException, Request
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

from app.config import settings


async def verify_chat_request(request: Request) -> None:
    """Verify Google Chat's OIDC token in production.

    For local curl tests only, CHAT_AUTH_MODE=disabled skips verification.
    On Cloud Run, also restrict invocation to chat@system.gserviceaccount.com.
    """
    if settings.chat_auth_mode.lower() == "disabled":
        return

    if settings.chat_auth_mode.lower() != "id_token":
        raise HTTPException(status_code=500, detail="Unsupported CHAT_AUTH_MODE")
    if not settings.chat_auth_audience:
        raise HTTPException(status_code=500, detail="CHAT_AUTH_AUDIENCE is not configured")

    authorization = request.headers.get("authorization", "")
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")

    token = authorization.removeprefix("Bearer ").strip()
    try:
        claims = id_token.verify_oauth2_token(
            token, google_requests.Request(), settings.chat_auth_audience
        )
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid Google Chat token") from exc

    if claims.get("email") != "chat@system.gserviceaccount.com" or not claims.get("email_verified"):
        raise HTTPException(status_code=401, detail="Request did not originate from Google Chat")


def validate_public_http_url(raw_url: str) -> str:
    """Allow only public HTTP(S) URLs and reject private/reserved IP destinations."""
    try:
        parts = urlsplit(raw_url.strip())
        if parts.scheme not in {"http", "https"} or not parts.hostname:
            raise ValueError("Only HTTP and HTTPS URLs are supported")
        if parts.username or parts.password:
            raise ValueError("URLs containing credentials are not allowed")
        if parts.port not in (None, 80, 443):
            raise ValueError("Non-standard ports are not allowed")

        host = parts.hostname.rstrip(".").encode("idna").decode("ascii").lower()
        if host in {"localhost", "localhost.localdomain"} or host.endswith(".localhost"):
            raise ValueError("Localhost URLs are not allowed")

        try:
            ip = ipaddress.ip_address(host.strip("[]"))
            if not ip.is_global:
                raise ValueError("Non-public IP addresses are not allowed")
        except ValueError as exc:
            # A valid IP that is not global must be rejected. A non-IP hostname is resolved below.
            if "not allowed" in str(exc):
                raise
            try:
                answers = socket.getaddrinfo(host, parts.port or (443 if parts.scheme == "https" else 80))
            except socket.gaierror as dns_exc:
                raise ValueError("Unable to resolve URL host") from dns_exc
            addresses = {item[4][0] for item in answers}
            if not addresses:
                raise ValueError("Unable to resolve URL host")
            for address in addresses:
                if not ipaddress.ip_address(address).is_global:
                    raise ValueError("URL resolves to a non-public IP address")

        # Strip fragments; preserve query string because it may be part of the article URL.
        return urlunsplit((parts.scheme, parts.netloc, parts.path or "/", parts.query, ""))
    except Exception as exc:
        raise ValueError(str(exc)) from exc
