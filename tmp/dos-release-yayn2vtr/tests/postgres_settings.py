"""Opt-in PostgreSQL verification database; never uses production credentials."""
from config.settings.base import *  # noqa: F403

DEBUG = False
ALLOWED_HOSTS = ['testserver', '127.0.0.1', 'localhost']
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
DATABASES = {'default': {
    'ENGINE': 'django.db.backends.postgresql',
    'NAME': required_env('POSTGRES_TEST_DB'),
    'USER': required_env('POSTGRES_TEST_USER'),
    'PASSWORD': required_env('POSTGRES_TEST_PASSWORD'),
    'HOST': os.environ.get('POSTGRES_TEST_HOST', '127.0.0.1'),
    'PORT': os.environ.get('POSTGRES_TEST_PORT', '5432'),
    'OPTIONS': {'sslmode': os.environ.get('POSTGRES_TEST_SSLMODE', 'require')},
    'TEST': {'NAME': 'test_' + required_env('POSTGRES_TEST_DB')},
}}
