"""Django settings for the Ahoum sessions marketplace.

All environment-specific values come from the environment (see .env.example at the
repo root). Nothing here should need editing to run the stack.
"""

from datetime import timedelta
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DJANGO_DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, ["localhost", "127.0.0.1", "backend", "nginx"]),
    CORS_ALLOWED_ORIGINS=(list, ["http://localhost:3000", "http://localhost:8080"]),
    ACCESS_TOKEN_LIFETIME_MIN=(int, 15),
    REFRESH_TOKEN_LIFETIME_DAYS=(int, 7),
    GITHUB_CLIENT_ID=(str, ""),
    GITHUB_CLIENT_SECRET=(str, ""),
    OAUTH_REDIRECT_URI=(str, "http://localhost:8080/auth/callback"),
    DATABASE_URL=(str, "postgres://app:change-me@localhost:5432/marketplace"),
)

# Read a repo-root .env when present (handy for running manage.py outside Docker).
_env_file = BASE_DIR.parent / ".env"
if _env_file.exists():
    environ.Env.read_env(_env_file)

SECRET_KEY = env("DJANGO_SECRET_KEY", default="insecure-dev-key-change-me")
DEBUG = env("DJANGO_DEBUG")
ALLOWED_HOSTS = env("ALLOWED_HOSTS")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # third party
    "rest_framework",
    "corsheaders",
    "drf_spectacular",
    # local
    "users",
    "sessions_app",
    "bookings",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
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

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {"default": env.db("DATABASE_URL")}
DATABASES["default"]["ATOMIC_REQUESTS"] = False

AUTH_USER_MODEL = "users.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# Admin static files live behind /static-admin/ so nginx can route them without
# colliding with the Next.js frontend's own /_next/static assets.
STATIC_URL = "/static-admin/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    # JSON only: the API is consumed by the Next.js client and by scripts, and a
    # single renderer keeps every response (including errors) uniformly JSON.
    "DEFAULT_RENDERER_CLASSES": ("rest_framework.renderers.JSONRenderer",),
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    # Deny by default: every public endpoint opts in explicitly with AllowAny.
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 12,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "config.exceptions.api_exception_handler",
    "UNAUTHENTICATED_USER": "django.contrib.auth.models.AnonymousUser",
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=env("ACCESS_TOKEN_LIFETIME_MIN")),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=env("REFRESH_TOKEN_LIFETIME_DAYS")),
    "AUTH_HEADER_TYPES": ("Bearer",),
    "UPDATE_LAST_LOGIN": True,
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Ahoum Sessions Marketplace API",
    "DESCRIPTION": "Sessions catalog, creator CRUD and concurrency-safe bookings.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
}

# The primary path is same-origin through nginx (:8080), so CORS is only needed
# when hitting the backend directly on :8000 during development.
CORS_ALLOWED_ORIGINS = env("CORS_ALLOWED_ORIGINS")

GITHUB_CLIENT_ID = env("GITHUB_CLIENT_ID")
GITHUB_CLIENT_SECRET = env("GITHUB_CLIENT_SECRET")
OAUTH_REDIRECT_URI = env("OAUTH_REDIRECT_URI")

GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_URL = "https://api.github.com/user"
GITHUB_EMAILS_URL = "https://api.github.com/user/emails"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}
