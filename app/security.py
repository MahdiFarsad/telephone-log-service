import hmac

from app.config import settings


def is_valid_token(provided_token: str | None) -> bool:
    """
    Constant-time comparison against the configured Simotel token.
    Never log or echo the provided or expected token anywhere near
    this check (see roadmap Phase 5).
    """
    if not provided_token or not settings.SIMOTEL_API_TOKEN:
        return False
    return hmac.compare_digest(provided_token, settings.SIMOTEL_API_TOKEN)
