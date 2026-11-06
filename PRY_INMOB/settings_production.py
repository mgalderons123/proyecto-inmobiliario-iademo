"""Production settings with PostgreSQL and transport security enforced."""

from django.core.exceptions import ImproperlyConfigured

from .settings import *  # noqa: F403


DEBUG = False
SECURE = True

for setting_name in (
    "POSTGRES_DB",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "POSTGRES_HOST",
    "REDIS_URL",
    "PII_ENCRYPTION_KEY",
    "JWT_SIGNING_KEY",
):
    if not config(setting_name, default=None):  # noqa: F405
        raise ImproperlyConfigured(f"{setting_name} is required in production.")

DATABASES["default"].update(  # noqa: F405
    {
        "NAME": config("POSTGRES_DB"),  # noqa: F405
        "USER": config("POSTGRES_USER"),  # noqa: F405
        "PASSWORD": config("POSTGRES_PASSWORD"),  # noqa: F405
        "HOST": config("POSTGRES_HOST"),  # noqa: F405
        "PORT": config("POSTGRES_PORT", default="5432"),  # noqa: F405
        "OPTIONS": {
            "connect_timeout": 5,
            "sslmode": config("POSTGRES_SSLMODE", default="verify-full"),  # noqa: F405
        },
    }
)

REDIS_URL = config("REDIS_URL")  # noqa: F405
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": REDIS_URL,
        "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
        "KEY_PREFIX": "casarent:prod:app",
        "TIMEOUT": 300,
    },
    "ratelimit": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": REDIS_URL,
        "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
        "KEY_PREFIX": "casarent:prod:ratelimit",
        "TIMEOUT": 300,
    },
}
RATELIMIT_USE_CACHE = "ratelimit"

SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

if config("BEHIND_HTTPS_PROXY", default=False, cast=bool):  # noqa: F405
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")


# Keep JWT rotation independent from Django sessions and encrypted records.
PII_ENCRYPTION_KEY = config("PII_ENCRYPTION_KEY")  # noqa: F405
SIMPLE_JWT = {**SIMPLE_JWT, "SIGNING_KEY": config("JWT_SIGNING_KEY")}  # noqa: F405

# Never expose development-only commands/routes when base settings were loaded
# from a developer environment with DEBUG=True.
INSTALLED_APPS = [app for app in INSTALLED_APPS if app != "apps.devtools"]  # noqa: F405
SERVE_PUBLIC_MEDIA = False

MIDDLEWARE = list(MIDDLEWARE)  # noqa: F405
MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")
STATIC_ROOT = BASE_DIR / "staticfiles"  # noqa: F405
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

# Container logs are collected by the hosting platform.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}

MEDIA_ROOT = Path(config("PUBLIC_MEDIA_ROOT", default=str(BASE_DIR / "media")))  # noqa: F405
PRIVATE_MEDIA_ROOT = Path(config("PRIVATE_MEDIA_ROOT", default=str(BASE_DIR / "private-media")))  # noqa: F405

# Only use a forwarded address when the deployment proxy overwrites it.
RATELIMIT_IP_META_KEY = config("RATELIMIT_IP_META_KEY", default="REMOTE_ADDR")  # noqa: F405
