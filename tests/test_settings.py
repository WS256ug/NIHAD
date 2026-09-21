import json
import os
import subprocess
import sys

from django.conf import settings
from django.test import SimpleTestCase


class EnvironmentSettingsTests(SimpleTestCase):
    def run_settings(self, module, **overrides):
        environment = {
            **os.environ,
            "DJANGO_SETTINGS_MODULE": module,
            "DJANGO_SECRET_KEY": "configuration-test-secret-with-at-least-fifty-characters-only",
            "DJANGO_ALLOWED_HOSTS": "school.example",
            "POSTGRES_DB": "school_test",
            "POSTGRES_USER": "school_test",
            "POSTGRES_PASSWORD": "configuration-only-not-a-real-credential",
            "POSTGRES_HOST": "db.example",
            **overrides,
        }
        return subprocess.run([
            sys.executable, "-c",
            "import json; from django.conf import settings as s; "
            "print(json.dumps({'engine': s.DATABASES['default']['ENGINE'], "
            "'debug': s.DEBUG, 'secure': s.SESSION_COOKIE_SECURE, "
            "'https': s.SECURE_SSL_REDIRECT}))",
        ], cwd=settings.BASE_DIR, env=environment, capture_output=True, text=True, timeout=20)

    def test_development_uses_sqlite(self):
        result = self.run_settings("config.settings.development")
        self.assertEqual(result.returncode, 0, result.stderr)
        config = json.loads(result.stdout)
        self.assertEqual(config["engine"], "django.db.backends.sqlite3")
        self.assertTrue(config["debug"])

    def test_production_uses_postgresql_with_https_and_debug_disabled(self):
        result = self.run_settings("config.settings.production")
        self.assertEqual(result.returncode, 0, result.stderr)
        config = json.loads(result.stdout)
        self.assertEqual(config["engine"], "django.db.backends.postgresql")
        self.assertFalse(config["debug"])
        self.assertTrue(config["secure"])
        self.assertTrue(config["https"])

    def test_production_requires_database_credentials(self):
        result = self.run_settings("config.settings.production", POSTGRES_PASSWORD="")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Set the POSTGRES_PASSWORD environment variable", result.stderr)

    def test_production_rejects_weak_secret_and_wildcard_hosts(self):
        for overrides, expected in [
            ({"DJANGO_SECRET_KEY": "weak"}, "strong DJANGO_SECRET_KEY"),
            ({"DJANGO_ALLOWED_HOSTS": "*"}, "explicit production DJANGO_ALLOWED_HOSTS"),
        ]:
            with self.subTest(overrides=overrides):
                result = self.run_settings("config.settings.production", **overrides)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(expected, result.stderr)
