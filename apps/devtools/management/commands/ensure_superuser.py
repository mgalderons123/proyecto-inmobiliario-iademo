import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Asegura la existencia de un superusuario, solicitando credenciales si no existen o no están en el entorno."

    def handle(self, *args, **options):
        User = get_user_model()
        username = os.environ.get("DJANGO_SUPERUSER_USERNAME")
        email = os.environ.get("DJANGO_SUPERUSER_EMAIL")
        password = os.environ.get("DJANGO_SUPERUSER_PASSWORD")

        if not username:
            username = input("Nombre de usuario (superuser): ")
        if not email:
            email = input("Email (superuser): ")
        if not password:
            while True:
                password = input("Contraseña (superuser): ")
                password_confirm = input("Confirmar contraseña: ")
                if password == password_confirm:
                    break
                else:
                    self.stderr.write(self.style.ERROR("Las contraseñas no coinciden."))

        if not User.objects.filter(username=username).exists():
            User.objects.create_superuser(username=username, email=email, password=password)
            self.stdout.write(self.style.SUCCESS(f"Superusuario '{username}' creado exitosamente."))
        else:
            self.stdout.write(f"Superusuario '{username}' ya existe.")
