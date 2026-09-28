import json
import os
import subprocess
import sys

from django.conf import settings
from django.test import SimpleTestCase


class EnvironmentSettingsTests(SimpleTestCase):
    def run_settings(self, module, *, inspect_driver=False, **overrides):
        environment = {
            **os.environ,
            "DJANGO_SETTINGS_MODULE": module,
            "DJANGO_SECRET_KEY": "configuration-test-secret-with-at-least-fifty-characters-only",
            "DJANGO_ALLOWED_HOSTS": "school.example",
            "DJANGO_DATABASE_BACKEND": "postgresql",
            "MYSQL_DRIVER": "mysqlclient",
            "POSTGRES_DB": "school_test",
            "POSTGRES_USER": "school_test",
            "POSTGRES_PASSWORD": "configuration-only-not-a-real-credential",
            "POSTGRES_HOST": "db.example",
            **overrides,
        }
        return subprocess.run([
            sys.executable, "-c",
            ("import django; django.setup(); from django.db import connections; "
             "assert connections['default'].Database.__name__ == 'pymysql'; "
             "assert connections['default'].get_connection_params()['charset'] == 'utf8mb4'; "
             if inspect_driver else "") +
            "import json, sys; from django.conf import settings as s; "
            "print(json.dumps({'engine': s.DATABASES['default']['ENGINE'], "
            "'debug': s.DEBUG, 'secure': s.SESSION_COOKIE_SECURE, "
            "'https': s.SECURE_SSL_REDIRECT, 'options': s.DATABASES['default'].get('OPTIONS', {}), "
            "'pymysql_loaded': 'pymysql' in sys.modules}))",
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

    def mysql_settings(self, **overrides):
        values = dict(DJANGO_DATABASE_BACKEND='mysql', MYSQL_DATABASE='school_test',
                      MYSQL_USER='school_test', MYSQL_PASSWORD='test-only-password',
                      MYSQL_HOST='localhost', POSTGRES_DB='', POSTGRES_PASSWORD='')
        values.update(overrides)
        return self.run_settings('config.settings.production', **values)

    def test_mysql_does_not_require_postgres_and_keeps_production_security(self):
        result = self.mysql_settings()
        self.assertEqual(result.returncode, 0, result.stderr)
        config = json.loads(result.stdout)
        self.assertEqual(config['engine'], 'django.db.backends.mysql')
        self.assertFalse(config['debug'])
        self.assertTrue(config['secure'])
        self.assertTrue(config['https'])
        self.assertEqual(config['options']['charset'], 'utf8mb4')
        self.assertEqual(config['options']['isolation_level'], 'read committed')
        self.assertIn('STRICT_TRANS_TABLES', config['options']['init_command'])
        self.assertIn('INNODB', config['options']['init_command'])

    def test_mysql_requires_its_own_credentials(self):
        for name in ('MYSQL_DATABASE', 'MYSQL_USER', 'MYSQL_PASSWORD', 'MYSQL_HOST'):
            result = self.mysql_settings(**{name: ''})
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(f'Set the {name} environment variable', result.stderr)

    def test_unknown_backend_is_rejected(self):
        result = self.run_settings('config.settings.production', DJANGO_DATABASE_BACKEND='unknown')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('must be mysql or postgresql', result.stderr)

    def test_pymysql_loads_django_backend_without_mysqlclient(self):
        from importlib.util import find_spec
        if find_spec('pymysql') is None:
            self.skipTest('Install requirements-namecheap.txt to test the optional trial driver.')
        result = self.mysql_settings(MYSQL_DRIVER='pymysql', inspect_driver=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(json.loads(result.stdout)['pymysql_loaded'])

    def test_trial_driver_does_not_load_for_postgres_or_sqlite(self):
        for module in ('config.settings.production', 'config.settings.development'):
            result = self.run_settings(module, MYSQL_DRIVER='pymysql')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(json.loads(result.stdout)['pymysql_loaded'])

    def test_unknown_mysql_driver_is_rejected(self):
        result = self.mysql_settings(MYSQL_DRIVER='unknown')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('MYSQL_DRIVER must be mysqlclient or pymysql', result.stderr)

    def test_production_rejects_weak_secret_and_wildcard_hosts(self):
        for overrides, expected in [
            ({"DJANGO_SECRET_KEY": "weak"}, "strong DJANGO_SECRET_KEY"),
            ({"DJANGO_ALLOWED_HOSTS": "*"}, "explicit production DJANGO_ALLOWED_HOSTS"),
        ]:
            with self.subTest(overrides=overrides):
                result = self.run_settings("config.settings.production", **overrides)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(expected, result.stderr)
