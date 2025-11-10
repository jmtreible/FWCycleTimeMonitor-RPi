"""Authentication utilities for the remote supervisor API."""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader

from .settings import get_settings

API_KEY_HEADER_NAME = "X-API-Key"
_api_key_header = APIKeyHeader(name=API_KEY_HEADER_NAME, auto_error=False)


async def require_api_key(api_key: str | None = Depends(_api_key_header)) -> str | None:
    """Validate the provided API key when authentication is enabled."""

    settings = get_settings()
    if not settings.require_auth:
        return None
    if api_key and api_key in settings.api_keys:
        return api_key
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Missing or invalid API key",
    )
