"""Shared settings. Secrets come from the environment or the local .env file."""
import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / ".env", override=False)


def required_env(name):
    value = os.environ.get(name, "").strip()
    if not value:
        raise ImproperlyConfigured(f"Set the {name} environment variable.")
    return value


def env_list(name, default=""):
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]


SECRET_KEY = required_env("DJANGO_SECRET_KEY")
DEBUG = False

INSTALLED_APPS = [
    "config.apps.SchoolAdminConfig",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "apps.accounts.apps.AccountsConfig",
    "apps.dashboard.apps.DashboardConfig",
    "apps.schools.apps.SchoolsConfig",
    "apps.students.apps.StudentsConfig",
    "apps.academics.apps.AcademicsConfig",
    "apps.reports.apps.ReportsConfig",
    "apps.finance.apps.FinanceConfig",
    "apps.expenses.apps.ExpensesConfig",
    "apps.promotions.apps.PromotionsConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "apps.accounts.middleware.ResponseSecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "apps.accounts.middleware.LoginThrottleMiddleware",
    "apps.accounts.middleware.InitialPasswordChangeMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

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
                "apps.accounts.context_processors.account_navigation",
                "apps.schools.context_processors.school_identity",
            ],
        },
    },
]

AUTH_USER_MODEL = "accounts.User"
AUTHENTICATION_BACKENDS = ['apps.accounts.throttling.ThrottledModelBackend']
LOGIN_FAILURE_LIMIT = int(os.environ.get('LOGIN_FAILURE_LIMIT', '5'))
AUTH_IP_FAILURE_LIMIT = int(os.environ.get('AUTH_IP_FAILURE_LIMIT', '100'))
AUTH_WINDOW_SECONDS = int(os.environ.get('AUTH_WINDOW_SECONDS', '900'))
RESET_REQUEST_LIMIT = int(os.environ.get('RESET_REQUEST_LIMIT', '5'))
AUTH_TRUSTED_PROXIES = env_list('AUTH_TRUSTED_PROXIES')
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "dashboard:home"
LOGOUT_REDIRECT_URL = "accounts:login"
PASSWORD_RESET_TIMEOUT = 3600
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "NIHAD School <noreply@localhost>")

LANGUAGE_CODE = "en"
TIME_ZONE = os.environ.get("DJANGO_TIME_ZONE", "Africa/Nairobi")
USE_I18N = True
USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = Path(os.environ.get('DJANGO_MEDIA_ROOT', str(BASE_DIR / 'media')))
PRIVATE_MEDIA_ROOT = Path(os.environ.get('DJANGO_PRIVATE_MEDIA_ROOT', str(BASE_DIR / 'private_media')))
BACKUP_ROOT = Path(os.environ.get('DJANGO_BACKUP_ROOT', str(BASE_DIR / 'backups')))
POSTGRES_BIN_DIR = os.environ.get('POSTGRES_BIN_DIR', '')

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
DATA_UPLOAD_MAX_MEMORY_SIZE = 6 * 1024 * 1024

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}
