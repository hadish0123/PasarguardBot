from __future__ import annotations

import os

from cryptography.fernet import Fernet, InvalidToken


class SecretBox:
    def __init__(self, key: str):
        if not key:
            raise RuntimeError("SECRET_KEY is required for encrypted registration secrets")
        try:
            self._fernet = Fernet(key.encode())
        except Exception as exc:
            raise RuntimeError("SECRET_KEY must be a valid Fernet key") from exc

    def encrypt(self, value: str) -> str:
        return self._fernet.encrypt(value.encode()).decode()

    def decrypt(self, value: str) -> str:
        try:
            return self._fernet.decrypt(value.encode()).decode()
        except InvalidToken as exc:
            raise RuntimeError("Encrypted secret cannot be decrypted") from exc


_box: SecretBox | None = None


def get_secret_box() -> SecretBox:
    global _box
    if _box is None:
        _box = SecretBox(os.getenv("SECRET_KEY", ""))
    return _box
