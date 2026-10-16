import secrets

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

from app.config import get_settings

# auto_error=False so a missing header reaches require_api_key and gets the
# same 401 as a wrong key, instead of FastAPI's own 403.
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def require_api_key(key: str | None = Security(api_key_header)) -> None:
    """Reject the request unless X-API-Key matches the configured API_KEY.

    Fails closed: if API_KEY is unset or empty, every request is rejected.
    """
    expected = get_settings().api_key
    if not key or not expected or not secrets.compare_digest(key, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )
