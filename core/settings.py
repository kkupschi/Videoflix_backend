"""Django settings for the Videoflix backend."""
import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")


def env_list(name, default=""):
    """Read a comma separated environment variable as a list of strings."""
    raw = os.environ.get(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


def env_bool(name, default="False"):
    """Read an environment variable as a boolean value."""
    return os.environ.get(name, default).strip().lower() == "true"


SECRET_KEY = os.environ.get("SECRET_KEY", "")
DEBUG = env_bool("DEBUG")
ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework.authtoken",
    "corsheaders",
    "django_rq",
    "auth_app",
    "video_app",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "core.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "core.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("DB_NAME"),
        "USER": os.environ.get("DB_USER"),
        "PASSWORD": os.environ.get("DB_PASSWORD"),
        "HOST": os.environ.get("DB_HOST", "db"),
        "PORT": os.environ.get("DB_PORT", "5432"),
    }
}

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": os.environ.get("REDIS_LOCATION", "redis://redis:6379/1"),
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
    }
}

RQ_QUEUES = {
    "default": {
        "HOST": os.environ.get("REDIS_HOST", "redis"),
        "PORT": os.environ.get("REDIS_PORT", "6379"),
        "DB": int(os.environ.get("REDIS_DB", "0")),
        "DEFAULT_TIMEOUT": 900,
    }
}

PASSWORD_VALIDATION_PATH = "django.contrib.auth.password_validation"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": f"{PASSWORD_VALIDATION_PATH}.UserAttributeSimilarityValidator"},
    {"NAME": f"{PASSWORD_VALIDATION_PATH}.MinimumLengthValidator"},
    {"NAME": f"{PASSWORD_VALIDATION_PATH}.CommonPasswordValidator"},
    {"NAME": f"{PASSWORD_VALIDATION_PATH}.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Europe/Berlin"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "static"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "auth_app.CustomUser"

EMAIL_HOST = os.environ.get("EMAIL_HOST", "")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", "True")
EMAIL_USE_SSL = env_bool("EMAIL_USE_SSL")

PLACEHOLDER_EMAIL_HOSTS = ("", "smtp.example.com")
FALLBACK_FROM_EMAIL = "noreply@videoflix.local"


def resolve_email_backend():
    """Write mails to the console while no real SMTP server is set up."""
    backend = os.environ.get("EMAIL_BACKEND", "")
    if backend:
        return backend
    if EMAIL_HOST in PLACEHOLDER_EMAIL_HOSTS:
        return "django.core.mail.backends.console.EmailBackend"
    return "django.core.mail.backends.smtp.EmailBackend"


def resolve_from_email():
    """Ignore the placeholder sender that ships with the env template."""
    sender = os.environ.get("DEFAULT_FROM_EMAIL", "")
    return sender if "@" in sender else FALLBACK_FROM_EMAIL


EMAIL_BACKEND = resolve_email_backend()
DEFAULT_FROM_EMAIL = resolve_from_email()

DEFAULT_FRONTEND_URL = "http://localhost:5500"


def resolve_frontend_url():
    """Derive the frontend address from the trusted origins if needed."""
    configured = os.environ.get("FRONTEND_URL", "")
    if configured:
        return configured.rstrip("/")
    if CSRF_TRUSTED_ORIGINS:
        return CSRF_TRUSTED_ORIGINS[0].rstrip("/")
    return DEFAULT_FRONTEND_URL


FRONTEND_URL = resolve_frontend_url()

ACTIVATION_URL_TEMPLATE = os.environ.get(
    "ACTIVATION_URL_TEMPLATE",
    FRONTEND_URL + "/pages/auth/activate.html?uid={uid}&token={token}",
)

REST_FRAMEWORK = {
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "auth_app.api.authentication.CookieJWTAuthentication",
    ],
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),
}

JWT_ACCESS_COOKIE = "access_token"
JWT_REFRESH_COOKIE = "refresh_token"
JWT_COOKIE_SECURE = env_bool("JWT_COOKIE_SECURE", str(not DEBUG))
JWT_COOKIE_SAMESITE = os.environ.get("JWT_COOKIE_SAMESITE", "Lax")

CORS_ALLOWED_ORIGINS = env_list(
    "CORS_ALLOWED_ORIGINS", ",".join(CSRF_TRUSTED_ORIGINS)
)
CORS_ALLOW_CREDENTIALS = True
