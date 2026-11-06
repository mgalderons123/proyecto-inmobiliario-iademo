"""Load production settings with synthetic secrets without starting services."""
import os
import subprocess
import sys

import pytest


def production_environment():
    return {
        **os.environ,
        "DJANGO_SETTINGS_MODULE": "PRY_INMOB.settings_production",
        "SECRET_KEY": "synthetic-django-key-for-tests-only",
        "DEBUG": "True",
        "ALLOWED_HOSTS": "example.test",
        "POSTGRES_DB": "synthetic",
        "POSTGRES_USER": "synthetic",
        "POSTGRES_PASSWORD": "synthetic",
        "POSTGRES_HOST": "db.example.test",
        "REDIS_URL": "redis://redis.example.test/0",
        "PII_ENCRYPTION_KEY": "synthetic-pii-key-for-tests-only",
        "JWT_SIGNING_KEY": "synthetic-jwt-key-for-tests-only",
    }


def test_production_configuration_isolated_from_debug_defaults():
    result = subprocess.run(
        [sys.executable, "-c", """
from django.conf import settings
assert settings.DEBUG is False
assert 'apps.devtools' not in settings.INSTALLED_APPS
assert settings.SERVE_PUBLIC_MEDIA is False
assert settings.SESSION_COOKIE_SECURE
assert settings.CSRF_COOKIE_SECURE
assert settings.DATABASES['default']['OPTIONS']['sslmode'] == 'verify-full'
assert settings.PII_ENCRYPTION_KEY == 'synthetic-pii-key-for-tests-only'
assert settings.SIMPLE_JWT['SIGNING_KEY'] == 'synthetic-jwt-key-for-tests-only'
assert 'whitenoise.middleware.WhiteNoiseMiddleware' in settings.MIDDLEWARE
"""], env=production_environment(), capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize('key', ['PII_ENCRYPTION_KEY', 'JWT_SIGNING_KEY'])
def test_production_requires_explicit_encryption_and_signing_keys(key):
    env = production_environment()
    env[key] = ''
    result = subprocess.run(
        [sys.executable, '-c', 'from django.conf import settings; settings.DEBUG'],
        env=env, capture_output=True, text=True, timeout=15,
    )
    assert result.returncode != 0
    assert f'{key} is required in production.' in result.stderr
