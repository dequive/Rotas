import base64
import hmac
import secrets
import struct
import time
from hashlib import sha1
from urllib.parse import quote


def generate_totp_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")


def _decode_secret(secret: str) -> bytes:
    padding = "=" * ((8 - len(secret) % 8) % 8)
    return base64.b32decode((secret + padding).upper())


def generate_totp_code(secret: str, *, for_time: int | None = None, interval: int = 30) -> str:
    counter = int((for_time if for_time is not None else time.time()) // interval)
    digest = hmac.new(_decode_secret(secret), struct.pack(">Q", counter), sha1).digest()
    offset = digest[-1] & 0x0F
    code_int = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return f"{code_int % 1_000_000:06d}"


def verify_totp_code(secret: str, code: str, *, window: int = 1, interval: int = 30) -> bool:
    cleaned = code.strip().replace(" ", "")
    if len(cleaned) != 6 or not cleaned.isdigit():
        return False
    now = int(time.time())
    return any(
        hmac.compare_digest(
            generate_totp_code(secret, for_time=now + (offset * interval), interval=interval),
            cleaned,
        )
        for offset in range(-window, window + 1)
    )


def build_otpauth_uri(*, secret: str, account_name: str, issuer: str = "ROTAS") -> str:
    label = f"{issuer}:{account_name}"
    return (
        f"otpauth://totp/{quote(label)}"
        f"?secret={quote(secret)}&issuer={quote(issuer)}&algorithm=SHA1&digits=6&period=30"
    )
