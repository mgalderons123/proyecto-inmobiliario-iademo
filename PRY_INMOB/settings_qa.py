"""Settings for the isolated local QA environment."""

from .settings import *  # noqa: F403


DEBUG = False

MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")  # noqa: F405

ALLOWED_HOSTS = config(  # noqa: F405
    "ALLOWED_HOSTS",
    default="localhost,127.0.0.1,web",
    cast=Csv(),  # noqa: F405
)
CSRF_TRUSTED_ORIGINS = config(  # noqa: F405
    "CSRF_TRUSTED_ORIGINS",
    default="http://localhost:4100,http://127.0.0.1:4100",
    cast=Csv(),  # noqa: F405
)

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": config("POSTGRES_DB", default="casarent_qa"),  # noqa: F405
        "USER": config("POSTGRES_USER", default="casarent_qa"),  # noqa: F405
        "PASSWORD": config("POSTGRES_PASSWORD"),  # noqa: F405
        "HOST": config("POSTGRES_HOST", default="db"),  # noqa: F405
        "PORT": config("POSTGRES_PORT", default="5432"),  # noqa: F405
        "CONN_MAX_AGE": 60,
        "OPTIONS": {"connect_timeout": 5},
    }
}

REDIS_URL = config("REDIS_URL", default="redis://redis:6379/0")  # noqa: F405
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": REDIS_URL,
        "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
        "KEY_PREFIX": "casarent:qa:app",
        "TIMEOUT": 300,
    },
    "ratelimit": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": REDIS_URL,
        "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
        "KEY_PREFIX": "casarent:qa:ratelimit",
        "TIMEOUT": 300,
    },
}
RATELIMIT_USE_CACHE = "ratelimit"

PII_ENCRYPTION_KEY = config("PII_ENCRYPTION_KEY")  # noqa: F405
SIMPLE_JWT = {  # noqa: F405
    **SIMPLE_JWT,
    "SIGNING_KEY": config("JWT_SIGNING_KEY"),  # noqa: F405
}

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = config("EMAIL_HOST", default="mailpit")  # noqa: F405
EMAIL_PORT = config("EMAIL_PORT", default=1025, cast=int)  # noqa: F405
EMAIL_USE_TLS = False
EMAIL_HOST_USER = config("EMAIL_HOST_USER", default="")  # noqa: F405
EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD", default="")  # noqa: F405
EMAIL_TIMEOUT = 10
DEFAULT_FROM_EMAIL = config("DEFAULT_FROM_EMAIL", default="qa@casarent.test")  # noqa: F405

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"  # noqa: F405
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
    },
}
MEDIA_URL = "/media/"
MEDIA_ROOT = Path(config("PUBLIC_MEDIA_ROOT", default=str(BASE_DIR / "qa-data" / "public")))  # noqa: F405
PRIVATE_MEDIA_ROOT = Path(  # noqa: F405
    config("PRIVATE_MEDIA_ROOT", default=str(BASE_DIR / "qa-data" / "private"))  # noqa: F405
)
SERVE_PUBLIC_MEDIA = True

DATA_UPLOAD_MAX_MEMORY_SIZE = config(  # noqa: F405
    "DATA_UPLOAD_MAX_MEMORY_SIZE", default=25 * 1024 * 1024, cast=int
)
FILE_UPLOAD_MAX_MEMORY_SIZE = config(  # noqa: F405
    "FILE_UPLOAD_MAX_MEMORY_SIZE", default=5 * 1024 * 1024, cast=int
)

# Local QA uses HTTP on localhost. Production security flags are tested in the
# production settings and must not be copied from this module.
SECURE = False
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{asctime} [{levelname}] {name}: {message}",
            "style": "{",
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        }
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "django": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "apps": {"handlers": ["console"], "level": "INFO", "propagate": False},
    },
}
