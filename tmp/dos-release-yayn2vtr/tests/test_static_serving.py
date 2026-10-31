from tempfile import TemporaryDirectory

from django.contrib.staticfiles.storage import staticfiles_storage
from django.core.management import call_command
from django.http import HttpResponseNotFound
from django.test import RequestFactory, SimpleTestCase, override_settings
from whitenoise.middleware import WhiteNoiseMiddleware


class ProductionStaticTests(SimpleTestCase):
    def test_collected_assets_have_correct_types_and_private_paths_are_not_served(self):
        with TemporaryDirectory() as root, override_settings(
            DEBUG=False, STATIC_ROOT=root, STATIC_URL='/static/',
            STORAGES={
                'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
                'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage'},
            },
        ):
            call_command('collectstatic', interactive=False, verbosity=0)
            handler = WhiteNoiseMiddleware(lambda request: HttpResponseNotFound())
            factory = RequestFactory()
            for path, content_type in (
                ('css/app.css', 'text/css'),
                ('vendor/oat/oat.min.css', 'text/css'),
                ('js/app.js', 'text/javascript'),
                ('js/pwa.js', 'text/javascript'),
                ('vendor/htmx/htmx.min.js', 'text/javascript'),
                ('img/nihad-logo.png', 'image/png'),
                ('img/pwa-192.png', 'image/png'),
            ):
                with self.subTest(path=path):
                    response = handler(factory.get(staticfiles_storage.url(path)))
                    try:
                        self.assertEqual(response.status_code, 200)
                        self.assertEqual(response['Content-Type'].split(';')[0], content_type)
                        self.assertIn('immutable', response['Cache-Control'])
                        self.assertTrue(b''.join(response.streaming_content))
                    finally:
                        response.close()
            for path in ('/.env', '/media/student.png', '/private_media/student.png', '/static/missing.css'):
                self.assertEqual(handler(factory.get(path)).status_code, 404)
