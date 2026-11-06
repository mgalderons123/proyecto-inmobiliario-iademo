"""Settings used by the automated suite inside the QA stack."""

from .settings_qa import *  # noqa: F403


PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
RATELIMIT_ENABLE = False

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "casarent-tests",
    }
}
RATELIMIT_USE_CACHE = "default"

MEDIA_ROOT = BASE_DIR / ".test-media"  # noqa: F405
PRIVATE_MEDIA_ROOT = BASE_DIR / ".test-private-media"  # noqa: F405

STORAGES = {  # noqa: F405
    **STORAGES,
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

DATABASES["default"]["TEST"] = {"NAME": "test_casarent_qa"}  # noqa: F405

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "WARNING"},
}
