import unicodedata

from django.db import migrations


def _normalize(value):
    normalized = unicodedata.normalize("NFKD", value or "")
    return "".join(
        char for char in normalized if not unicodedata.combining(char)
    ).lower()


def migrate_tenants_and_assign_plans(apps, schema_editor):
    Cuenta = apps.get_model("users", "Cuenta")
    Contrato = apps.get_model("inmuebles", "Contrato")
    Inquilino = apps.get_model("inmuebles", "Inquilino")

    contracts = Contrato.objects.filter(
        tipo="alquiler",
        inquilino_registrado__isnull=True,
    ).select_related("inmueble")

    for contract in contracts.iterator():
        account_id = contract.inmueble.cuenta_id
        tenant = None
        if contract.inquilino_id:
            tenant = Inquilino.objects.filter(
                cuenta_id=account_id,
                user_id=contract.inquilino_id,
            ).first()

        email = contract.inquilino_email or ""
        user_name = ""
        if contract.inquilino_id:
            user_name = " ".join(filter(None, (
                contract.inquilino.first_name,
                contract.inquilino.last_name,
            ))) or contract.inquilino.username
        name = contract.inquilino_nombre or user_name or "Inquilino migrado"
        if tenant is None:
            for candidate in Inquilino.objects.filter(cuenta_id=account_id):
                if email and candidate.email.lower() == email.lower():
                    tenant = candidate
                    break
                if not email and _normalize(candidate.nombre) == _normalize(name):
                    tenant = candidate
                    break

        if tenant is None:
            tenant = Inquilino.objects.create(
                cuenta_id=account_id,
                user_id=contract.inquilino_id,
                nombre=name,
                nombre_busqueda=_normalize(name),
                email=email,
                telefono=contract.inquilino_telefono or "",
                creado_por_id=contract.creado_por_id,
            )

        contract.inquilino_registrado_id = tenant.pk
        contract.inquilino_nombre = ""
        contract.inquilino_email = ""
        contract.inquilino_telefono = ""
        contract.save(update_fields=[
            "inquilino_registrado",
            "inquilino_nombre",
            "inquilino_email",
            "inquilino_telefono",
        ])

    for account in Cuenta.objects.all():
        count = Inquilino.objects.filter(cuenta_id=account.pk).count()
        if count <= 1:
            account.plan = "trial"
            account.limite_inquilinos_personalizado = None
        elif count <= 3:
            account.plan = "essential"
            account.limite_inquilinos_personalizado = None
        elif count <= 10:
            account.plan = "professional"
            account.limite_inquilinos_personalizado = None
        else:
            account.plan = "custom"
            account.limite_inquilinos_personalizado = count
        account.save(update_fields=["plan", "limite_inquilinos_personalizado"])


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0011_account_plans"),
        ("inmuebles", "0020_alter_inmueble_cuenta_alter_inquilino_cuenta_and_more"),
    ]

    operations = [
        migrations.RunPython(
            migrate_tenants_and_assign_plans,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
