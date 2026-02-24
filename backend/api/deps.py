from __future__ import annotations

from fastapi import HTTPException, Query, Security, status
from fastapi.security.api_key import APIKeyHeader

from config.settings import settings


api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_api_key_value(value: str | None) -> bool:
    if not settings.api_key:
        return True
    return value == settings.api_key


def require_api_key(
    header_key: str | None = Security(api_key_header),
    query_key: str | None = Query(default=None, alias="api_key"),
) -> str:
    api_key = header_key or query_key
    if not verify_api_key_value(api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )
    return api_key or ""
