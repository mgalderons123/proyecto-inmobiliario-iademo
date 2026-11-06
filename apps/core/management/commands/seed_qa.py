import os
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.inmuebles.models import Contrato, Cuota, Inmueble, Inquilino, Pago, Propietario, Recibo
from apps.users.models import Cuenta, MembresiaCuenta


class Command(BaseCommand):
    help = "Crea datos sintéticos idempotentes para el ambiente QA."

    def _credential(self, name):
        value = os.environ.get(name, "")
        if not value or value == "GENERATE_ME":
            raise CommandError(f"Defina {name} en .env.qa antes de ejecutar seed_qa.")
        return value

    def _upsert_user(self, *, username, email, password, is_staff=False, is_superuser=False):
        User = get_user_model()
        user, created = User.objects.get_or_create(username=username, defaults={"email": email})
        user.email = email
        user.is_active = True
        user.is_staff = is_staff or is_superuser
        user.is_superuser = is_superuser
        fields = ["email", "is_active", "is_staff", "is_superuser"]
        if created:
            user.set_password(password)
            fields.append("password")
        user.save(update_fields=fields)
        return user

    @transaction.atomic
    def handle(self, *args, **options):
        superadmin = self._upsert_user(
            username="qa-superadmin",
            email="superadmin@example.test",
            password=self._credential("QA_SUPERADMIN_PASSWORD"),
            is_superuser=True,
        )
        admin_a = self._upsert_user(
            username="qa-admin-a",
            email="admin-a@example.test",
            password=self._credential("QA_ADMIN_A_PASSWORD"),
            is_staff=True,
        )
        admin_b = self._upsert_user(
            username="qa-admin-b",
            email="admin-b@example.test",
            password=self._credential("QA_ADMIN_B_PASSWORD"),
            is_staff=True,
        )
        tenant_a = self._upsert_user(
            username="qa-inquilino-a",
            email="inquilino-a@example.test",
            password=self._credential("QA_TENANT_A_PASSWORD"),
        )
        tenant_b = self._upsert_user(
            username="qa-inquilino-b",
            email="inquilino-b@example.test",
            password=self._credential("QA_TENANT_B_PASSWORD"),
        )

        inquilino_group, _ = Group.objects.get_or_create(name="Inquilino")
        tenant_a.groups.add(inquilino_group)
        tenant_b.groups.add(inquilino_group)

        account_a, _ = Cuenta.objects.update_or_create(
            nombre="Casarent QA Cuenta A",
            defaults={"moneda_predeterminada": "USD", "activa": True},
        )
        account_b, _ = Cuenta.objects.update_or_create(
            nombre="Casarent QA Cuenta B",
            defaults={"moneda_predeterminada": "BRL", "locale": "pt-BR", "activa": True},
        )
        for account, user, role in (
            (account_a, admin_a, MembresiaCuenta.Roles.PROPIETARIO),
            (account_a, superadmin, MembresiaCuenta.Roles.ADMIN),
            (account_a, tenant_a, MembresiaCuenta.Roles.INQUILINO),
            (account_b, admin_b, MembresiaCuenta.Roles.PROPIETARIO),
            (account_b, tenant_b, MembresiaCuenta.Roles.INQUILINO),
        ):
            MembresiaCuenta.objects.update_or_create(
                cuenta=account,
                user=user,
                defaults={"rol": role, "activa": True},
            )

        for suffix, account, currency, admin, tenant in (
            ("A", account_a, "USD", admin_a, tenant_a),
            ("B", account_b, "BRL", admin_b, tenant_b),
        ):
            inquilino, _ = Inquilino.objects.get_or_create(
                cuenta=account,
                user=tenant,
                defaults={
                    "nombre": f"Inquilino QA {suffix}",
                    "email": tenant.email,
                    "telefono": f"+54000000000{suffix}",
                    "documento": f"QA-INQ-{suffix}",
                    "creado_por": admin,
                },
            )
            if inquilino.creado_por_id != admin.id:
                inquilino.creado_por = admin
                inquilino.save(update_fields=["creado_por"])

            propietario, _ = Propietario.objects.get_or_create(
                cuenta=account,
                nombre_busqueda=f"propietario qa {suffix.lower()}",
                defaults={
                    "nombre": f"Propietario QA {suffix}",
                    "email": f"propietario-{suffix.lower()}@example.test",
                    "telefono": f"+54111111111{suffix}",
                    "documento": f"QA-PROP-{suffix}",
                    "creado_por": admin,
                },
            )

            inmueble, _ = Inmueble.objects.get_or_create(
                cuenta=account,
                titulo=f"Inmueble QA Cuenta {suffix}",
                defaults={
                    "direccion": f"Calle QA {suffix} 100",
                    "direccion_normalizada": f"Calle QA {suffix} 100",
                    "descripcion": "Registro sintético para pruebas de aislamiento.",
                    "precio": Decimal("100000.00"),
                    "moneda": currency,
                    "tipo": Inmueble.Tipo.DEPARTAMENTO,
                    "estado": Inmueble.Estado.ALQUILADO,
                    "propietario": propietario,
                    "superficie": Decimal("60.00"),
                    "habitaciones": 2,
                    "banos": 1,
                    "latitud": Decimal("-34.603700"),
                    "longitud": Decimal("-58.381600"),
                    "creado_por": admin,
                },
            )

            contrato, _ = Contrato.objects.get_or_create(
                inmueble=inmueble,
                inquilino_registrado=inquilino,
                estado=Contrato.Estado.ACTIVO,
                defaults={
                    "tipo": Contrato.Tipo.ALQUILER,
                    "inquilino": tenant,
                    "frecuencia_pago": Contrato.FrecuenciaPago.MENSUAL,
                    "fecha_inicio": date.today() - timedelta(days=30),
                    "fecha_fin": date.today() + timedelta(days=335),
                    "monto": Decimal("500.00"),
                    "moneda": currency,
                    "garantia": Decimal("500.00"),
                    "creado_por": admin,
                },
            )

            cuota, _ = Cuota.objects.get_or_create(
                contrato=contrato,
                numero=1,
                defaults={
                    "descripcion": f"Cuota QA {suffix}",
                    "fecha_vencimiento": date.today() + timedelta(days=5),
                    "monto": Decimal("500.00"),
                },
            )
            pago_aprobado, _ = Pago.objects.get_or_create(
                cuota=cuota,
                comprobante=f"QA-APROBADO-{suffix}",
                defaults={
                    "monto": Decimal("200.00"),
                    "fecha_pago": date.today(),
                    "metodo_pago": Pago.Metodo.TRANSFERENCIA,
                    "estado": Pago.Estado.APROBADO,
                    "fecha_aprobacion": date.today(),
                    "creado_por": tenant,
                },
            )
            Recibo.objects.get_or_create(
                pago=pago_aprobado,
                defaults={"codigo": f"QA-REC-{suffix}"},
            )
            Pago.objects.get_or_create(
                cuota=cuota,
                comprobante=f"QA-PENDIENTE-{suffix}",
                defaults={
                    "monto": Decimal("100.00"),
                    "fecha_pago": date.today(),
                    "metodo_pago": Pago.Metodo.TRANSFERENCIA,
                    "estado": Pago.Estado.PENDIENTE,
                    "creado_por": tenant,
                },
            )

        self.stdout.write(self.style.SUCCESS("Datos QA creados o actualizados."))
        self.stdout.write("Usuarios: qa-superadmin, qa-admin-a, qa-admin-b, qa-inquilino-a, qa-inquilino-b")
