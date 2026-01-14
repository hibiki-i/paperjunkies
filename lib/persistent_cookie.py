from __future__ import annotations

import base64

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

# A stable, app-specific salt. Rotating this will invalidate all existing cookies.
_SALT = b"paperjunkies/persistent-cookie/v1"
_ITERATIONS = 390_000


def _fernet_from_password(password: str) -> Fernet:
    clean = (password or "").strip()
    if not clean:
        raise ValueError("COOKIES_PASSWORD is required to encrypt persistent auth cookies.")

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=_SALT,
        iterations=_ITERATIONS,
    )
    key = base64.urlsafe_b64encode(kdf.derive(clean.encode("utf-8")))
    return Fernet(key)


def encrypt_value(*, password: str, value: str) -> str:
    f = _fernet_from_password(password)
    token = f.encrypt((value or "").encode("utf-8"))
    return token.decode("utf-8")


def decrypt_value(*, password: str, token: str) -> str | None:
    clean = (token or "").strip()
    if not clean:
        return None

    try:
        f = _fernet_from_password(password)
        raw = f.decrypt(clean.encode("utf-8"))
        out = raw.decode("utf-8").strip()
        return out or None
    except (InvalidToken, ValueError):
        return None
