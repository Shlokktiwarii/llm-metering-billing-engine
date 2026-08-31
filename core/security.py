import hashlib
import secrets


def generate_api_key() -> str:
    """Generate a cryptographically secure API key."""
    return "sk_" + secrets.token_urlsafe(32)


def hash_api_key(api_key: str) -> str:
    """Hash an API key before storing or looking it up."""
    return hashlib.sha256(
        api_key.encode("utf-8")
    ).hexdigest()