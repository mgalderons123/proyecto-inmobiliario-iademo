"""
runserver_dev: runserver opt-in que auto-aplica migraciones y crea
un superusuario por defecto al arrancar.

Pensado exclusivamente para el entorno de desarrollo local.
NO usar en producción.

Variables de entorno (todas opcionales):
    DJANGO_SUPERUSER_USERNAME  -> prompt si no se define
    DJANGO_SUPERUSER_EMAIL     -> prompt si no se define
    DJANGO_SUPERUSER_PASSWORD  -> prompt si no se define
"""
import os

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.commands.runserver import Command as RunserverCommand


class Command(RunserverCommand):
    help = (
        "Runserver que aplica migraciones y crea un superusuario por "
        "defecto antes de levantar el server. Solo para desarrollo local."
    )

    def handle(self, *args, **options):
        call_command("migrate", interactive=False, verbosity=0)

        call_command("ensure_superuser")
        super().handle(*args, **options)
