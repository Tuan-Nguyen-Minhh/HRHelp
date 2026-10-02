"""Strip secrets before a tool payload is written to the ledger."""

_SECRET_KEYS = {
    "authorization",
    "api_key",
    "apikey",
    "password",
    "password_hash",
    "token",
    "access_token",
    "refresh_token",
    "jwt",
    "secret",
    "mistral_api_key",
    "openai_api_key",
}


def redact(value: object) -> object:
    """Return a copy with credential-shaped fields replaced."""
    if isinstance(value, dict):
        cleaned = {}
        for key, item in value.items():
            folded = str(key).casefold()
            if folded in _SECRET_KEYS or "secret" in folded or folded.endswith("_key"):
                cleaned[key] = "[REDACTED]"
            else:
                cleaned[key] = redact(item)
        return cleaned
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, str) and value.lower().startswith("bearer "):
        return "[REDACTED]"
    return value
