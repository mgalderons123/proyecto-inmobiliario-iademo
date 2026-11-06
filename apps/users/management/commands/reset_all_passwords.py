import secrets
import string

from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.users.models import UserSecurityState


class Command(BaseCommand):
    help = "Restablece todas las contraseñas y exige cambiarlas en el próximo ingreso."

    def add_arguments(self, parser):
        parser.add_argument("--password")
        parser.add_argument("--confirm", action="store_true")
        parser.add_argument("--check-only", action="store_true")

    def handle(self, *args, **options):
        password = options.get("password") or self._generate_password()
        if len(password) < 16:
            raise CommandError("La contraseña temporal debe tener al menos 16 caracteres.")

        User = get_user_model()
        users = list(User.objects.order_by("username"))
        if options["check_only"]:
            self.stdout.write(f"Validación correcta para {len(users)} usuarios.")
            return
        if not options["confirm"]:
            raise CommandError("Use --confirm para ejecutar el reseteo.")

        with transaction.atomic():
            for user in users:
                user.set_password(password)
                user.save(update_fields=["password"])
                UserSecurityState.objects.update_or_create(
                    user=user, defaults={"must_change_password": True}  # nosec B105
                )
            Session.objects.all().delete()

        self.stdout.write(self.style.SUCCESS(f"Contraseñas actualizadas: {len(users)}"))
        for user in users:
            self.stdout.write(user.username)
        self.stdout.write(f"Contraseña temporal: {password}")

    @staticmethod
    def _generate_password(length=24):
        alphabet = string.ascii_letters + string.digits + "!@#$%_-"
        return "".join(secrets.choice(alphabet) for _ in range(length))
