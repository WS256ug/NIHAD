"""Local development uses SQLite and Django's static/media serving."""
from .base import *  # noqa: F403

DEBUG = True
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,[::1]")
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.environ.get('SQLITE_DB_PATH', str(BASE_DIR / 'db.sqlite3')),
        "OPTIONS": {"timeout": 20},
    },
}
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
