"""Password hashing with per-password salt and a versioned, self-contained format."""
import hashlib
import hmac
import secrets

ITERATIONS = 600_000


def validate_password(password: str):
    if not 12 <= len(password) <= 128:
        raise ValueError("Use a password with 12–128 characters.")
    if not password.strip():
        raise ValueError("A password cannot consist only of spaces.")


def hash_password(password: str) -> str:
    validate_password(password)
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), ITERATIONS)
    return f"pbkdf2_sha256${ITERATIONS}${salt}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    if len(password) > 128:
        return False
    try:
        algorithm, iterations, salt, expected = encoded.split("$")
        if algorithm != "pbkdf2_sha256" or not 100_000 <= int(iterations) <= 2_000_000:
            return False
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(iterations))
        return hmac.compare_digest(digest.hex(), expected)
    except (ValueError, TypeError):
        return False
