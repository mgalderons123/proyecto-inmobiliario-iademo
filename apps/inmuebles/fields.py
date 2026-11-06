import base64
import hashlib
import unicodedata

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.db import models


_fernet_instance = None


def _make_fernet():
    global _fernet_instance
    if _fernet_instance is None:
        encryption_secret = getattr(settings, "PII_ENCRYPTION_KEY", settings.SECRET_KEY)
        key = base64.urlsafe_b64encode(
            hashlib.sha256(encryption_secret.encode()).digest()
        )
        _fernet_instance = Fernet(key)
    return _fernet_instance


class EncryptedField(models.TextField):
    description = "Almacena texto cifrado con Fernet (AES-128-CBC)"

    def get_db_prep_save(self, value, connection):
        if value is None or value == "":
            return ""
        return _make_fernet().encrypt(str(value).encode()).decode()

    def from_db_value(self, value, expression, connection):
        if value is None or value == "":
            return ""
        try:
            return _make_fernet().decrypt(value.encode()).decode()
        except InvalidToken:
            return value

    def to_python(self, value):
        if isinstance(value, str) and value and value.startswith("gAAAAAB"):
            try:
                return _make_fernet().decrypt(value.encode()).decode()
            except InvalidToken:
                pass
        return value


def normalizar_nombre(nombre):
    if not nombre:
        return ""
    nfkd = unicodedata.normalize("NFKD", nombre)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower()
