"""WSGI config for PRY_INMOB project."""
import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "PRY_INMOB.settings")

application = get_wsgi_application()
