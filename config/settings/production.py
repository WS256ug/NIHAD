"""Production settings behind an explicitly trusted HTTPS proxy."""
import os

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403

DEBUG = False
# Serve collected assets through Passenger/WSGI when no web-server alias exists.
MIDDLEWARE = list(MIDDLEWARE)
MIDDLEWARE.insert(
    MIDDLEWARE.index("django.middleware.security.SecurityMiddleware") + 1,
    "whitenoise.middleware.WhiteNoiseMiddleware",
)
if len(SECRET_KEY) < 50 or len(set(SECRET_KEY)) < 5 or SECRET_KEY.startswith("django-insecure-"):
    raise ImproperlyConfigured("Use a strong DJANGO_SECRET_KEY of at least 50 characters.")

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS")
if not ALLOWED_HOSTS or "*" in ALLOWED_HOSTS:
    raise ImproperlyConfigured("Set explicit production DJANGO_ALLOWED_HOSTS.")

CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = os.environ.get("EMAIL_HOST", "localhost")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "true").lower() == "true"
EMAIL_USE_SSL = os.environ.get("EMAIL_USE_SSL", "false").lower() == "true"
EMAIL_TIMEOUT = 10
DATABASE_BACKEND = os.environ.get("DJANGO_DATABASE_BACKEND", "postgresql").strip().lower()
if DATABASE_BACKEND == "mysql":
    MYSQL_DRIVER = os.environ.get("MYSQL_DRIVER", "mysqlclient").strip().lower()
    if MYSQL_DRIVER == "pymysql":
        try:
            import pymysql
        except ImportError as error:
            raise ImproperlyConfigured(
                'Install requirements-namecheap.txt to use MYSQL_DRIVER=pymysql.'
            ) from error
        pymysql.install_as_MySQLdb()
    elif MYSQL_DRIVER != "mysqlclient":
        raise ImproperlyConfigured("MYSQL_DRIVER must be mysqlclient or pymysql.")
    DATABASES = {"default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": required_env("MYSQL_DATABASE"),
        "USER": required_env("MYSQL_USER"),
        "PASSWORD": required_env("MYSQL_PASSWORD"),
        "HOST": required_env("MYSQL_HOST"),
        "PORT": os.environ.get("MYSQL_PORT", "3306"),
        "CONN_MAX_AGE": 60,
        "CONN_HEALTH_CHECKS": True,
        "OPTIONS": {
            "charset": "utf8mb4",
            "isolation_level": "read committed",
            "init_command": "SET sql_mode='STRICT_TRANS_TABLES', default_storage_engine=INNODB",
        },
    }}
    if os.environ.get("MYSQL_SSL_CA"):
        DATABASES["default"]["OPTIONS"]["ssl"] = {"ca": os.environ["MYSQL_SSL_CA"]}
elif DATABASE_BACKEND == "postgresql":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": required_env("POSTGRES_DB"),
            "USER": required_env("POSTGRES_USER"),
            "PASSWORD": required_env("POSTGRES_PASSWORD"),
            "HOST": required_env("POSTGRES_HOST"),
            "PORT": os.environ.get("POSTGRES_PORT", "5432"),
            "CONN_MAX_AGE": 60,
            "CONN_HEALTH_CHECKS": True,
            "OPTIONS": {"sslmode": os.environ.get("POSTGRES_SSLMODE", "require")},
        },
    }
else:
    raise ImproperlyConfigured("DJANGO_DATABASE_BACKEND must be mysql or postgresql.")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
if os.environ.get('DJANGO_BEHIND_HTTPS_PROXY', 'false').lower() == 'true':
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SESSION_COOKIE_AGE = 8 * 60 * 60
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}
