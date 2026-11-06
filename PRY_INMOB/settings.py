"""Django settings for PRY_INMOB project."""
import os
from datetime import timedelta
from pathlib import Path

from decouple import Config, Csv, RepositoryEnv, config
from django.core.exceptions import ImproperlyConfigured
from django.utils.translation import gettext_lazy as _

BASE_DIR = Path(__file__).resolve().parent.parent


def database_config(name, default=None):
    """Read DB settings from the environment, .env, or local DB env file."""
    value = config(name, default=None)
    postgres_env = BASE_DIR / ".env.postgres"
    if value is None and postgres_env.exists():
        value = Config(RepositoryEnv(str(postgres_env)))(name, default=None)
    if value is None:
        value = default
    return value

if not os.environ.get("SSL_CERT_FILE"):
    try:
        import certifi
        os.environ["SSL_CERT_FILE"] = certifi.where()
    except ImportError:
        pass

SECRET_KEY = config("SECRET_KEY") # NO TOCAR EN PRODUCCIÓN: NUNCA DEJAR UN VALOR DEFAULT INSEGURO AQUÍ
DEBUG = config("DEBUG", cast=bool)
ALLOWED_HOSTS = config("ALLOWED_HOSTS", cast=Csv())

INSTALLED_APPS = [
    "apps.core",
    "apps.api",
    "apps.inmuebles",
    "apps.users",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    "rest_framework",
    "rest_framework_simplejwt",
]

AUTHENTICATION_BACKENDS = ["apps.core.backends.EmailOrUsernameBackend"]

if DEBUG:
    INSTALLED_APPS.insert(3, "apps.devtools")

SITE_ID = 1

SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

SECURE = config("SECURE", default=False, cast=bool)
if SECURE:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

RATELIMIT_ENABLE = config("RATELIMIT_ENABLE", default=True, cast=bool)

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "casarent-development",
        "KEY_PREFIX": "casarent-dev",
        "TIMEOUT": 300,
    }
}
RATELIMIT_USE_CACHE = "default"
PUBLIC_LANDING_CACHE_TIMEOUT = config(
    "PUBLIC_LANDING_CACHE_TIMEOUT",
    default=0 if DEBUG else 300,
    cast=int,
)
PUBLIC_LANDING_CACHE_VERSION = "v1"

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "apps.core.middleware.ExceptionLoggingMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "apps.core.middleware.AccountContextMiddleware",
    "apps.core.middleware.ForcePasswordChangeMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.core.middleware.UserProfileLanguageMiddleware",
]

ROOT_URLCONF = "PRY_INMOB.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "django.template.context_processors.i18n",
                "apps.users.context_processors.theme_preferences",
            ],
        },
    },
]

WSGI_APPLICATION = "PRY_INMOB.wsgi.application"
ASGI_APPLICATION = "PRY_INMOB.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": database_config("POSTGRES_DB", "casarent_dev"),
        "USER": database_config("POSTGRES_USER", "casarent_dev"),
        "PASSWORD": database_config("POSTGRES_PASSWORD"),
        "HOST": database_config("POSTGRES_HOST", "127.0.0.1"),
        "PORT": database_config("POSTGRES_PORT", "5432"),
        "CONN_MAX_AGE": 60,
        "CONN_HEALTH_CHECKS": True,
        "OPTIONS": {"connect_timeout": 5},
    }
}

if not DATABASES["default"]["PASSWORD"]:
    raise ImproperlyConfigured(
        "POSTGRES_PASSWORD is required. Run ./scripts/postgres-up.sh or configure it in the environment."
    )

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
    "django.contrib.auth.hashers.BCryptSHA256PasswordHasher",
    "django.contrib.auth.hashers.ScryptPasswordHasher",
]

LANGUAGE_CODE = "es"
LANGUAGES = [
    ("es", _("Español")),
    ("en", _("English")),
    ("pt", _("Português")),
]
TIME_ZONE = "UTC"
USE_I18N = True
USE_L10N = True

LOCALE_PATHS = [
    BASE_DIR / "locale",
]
USE_TZ = True

STATIC_URL = "static/"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"
PRIVATE_MEDIA_ROOT = BASE_DIR / "private-media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "apps.api.authentication.PasswordChangeJWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),
    "CHECK_REVOKE_TOKEN": True,  # nosec B105
}

LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"

EMAIL_BACKEND = config("EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = config("EMAIL_HOST", default="localhost")
EMAIL_PORT = config("EMAIL_PORT", default=25, cast=int)
EMAIL_USE_TLS = config("EMAIL_USE_TLS", default=False, cast=bool)
EMAIL_HOST_USER = config("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD", default="")
DEFAULT_FROM_EMAIL = config("DEFAULT_FROM_EMAIL", default="no-reply@miproyecto.local")
PASSWORD_RESET_TIMEOUT = config("PASSWORD_RESET_TIMEOUT", default=3600, cast=int)

VERIFICATION_TOKEN_TIMEOUT = config("VERIFICATION_TOKEN_TIMEOUT", default=86400, cast=int)

LOGIN_URL = "login"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{asctime} [{levelname}] {name}: {message}",
            "style": "{",
        },
    },
    "handlers": {
        "file": {
            "level": "ERROR",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": BASE_DIR / "logs" / "django_errors.log",
            "maxBytes": 5 * 1024 * 1024,
            "backupCount": 3,
            "formatter": "verbose",
        },
    },
    "loggers": {
        "apps.core.middleware": {
            "handlers": ["file"],
            "level": "ERROR",
            "propagate": False,
        },
    },
}
