import base64
import hashlib

from cryptography.fernet import Fernet
from django.conf import settings
from django.db import migrations


def _make_fernet():
    key = base64.urlsafe_b64encode(
        hashlib.sha256(settings.SECRET_KEY.encode()).digest()
    )
    return Fernet(key)


def encrypt_existing_data(apps, schema_editor):
    fernet = _make_fernet()

    models_config = [
        ("Inquilino", ["nombre", "email", "telefono", "documento", "direccion"]),
        ("Propietario", ["nombre", "email", "telefono", "documento", "direccion"]),
        ("Contrato", ["inquilino_nombre", "inquilino_email", "inquilino_telefono"]),
    ]

    for model_name, fields in models_config:
        Model = apps.get_model("inmuebles", model_name)
        for obj in Model.objects.iterator():
            needs_save = False
            for field in fields:
                raw = getattr(obj, field)
                if raw and not raw.startswith("gAAAAA"):
                    encrypted = fernet.encrypt(raw.encode()).decode()
                    setattr(obj, field, encrypted)
                    needs_save = True
            if needs_save:
                obj.save(update_fields=fields)


class Migration(migrations.Migration):

    dependencies = [
        ("inmuebles", "0011_alter_inquilino_options_alter_propietario_options_and_more"),
    ]

    operations = [
        migrations.RunPython(encrypt_existing_data, reverse_code=migrations.RunPython.noop),
    ]
