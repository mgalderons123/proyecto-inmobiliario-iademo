"""ASGI config for PRY_INMOB project."""
import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "PRY_INMOB.settings")

application = get_asgi_application()
