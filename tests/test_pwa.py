from django.contrib.auth import get_user_model
from django.contrib.staticfiles import finders
from django.test import TestCase
from django.urls import reverse
from PIL import Image


class PWATests(TestCase):
    def test_manifest_and_icons_are_installable(self):
        response = self.client.get(reverse('pwa_manifest'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/manifest+json')
        manifest = response.json()
        self.assertEqual(manifest['display'], 'standalone')
        self.assertEqual(manifest['start_url'], reverse('dashboard:home'))
        for size in (192, 512):
            with Image.open(finders.find(f'img/pwa-{size}.png')) as icon:
                self.assertEqual(icon.size, (size, size))

    def test_worker_is_public_and_contains_only_generic_fallback(self):
        anonymous = self.client.get(reverse('pwa_service_worker'))
        self.assertEqual(anonymous.status_code, 200)
        self.assertEqual(anonymous['Content-Type'], 'application/javascript')
        self.assertEqual(anonymous['Service-Worker-Allowed'], '/')
        self.assertIn('no-store', anonymous['Cache-Control'])
        user = get_user_model().objects.create_user(
            'private-staff-name', role='teacher', must_change_password=True,
        )
        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse('pwa_manifest')).status_code, 200)
        authenticated = self.client.get(reverse('pwa_service_worker'))
        self.assertEqual(authenticated.content, anonymous.content)
        self.assertNotIn(b'private-staff-name', authenticated.content)
        self.assertRedirects(self.client.get('/'), reverse('accounts:password_change'))

    def test_login_pages_link_app_metadata(self):
        for route in ('accounts:login', 'students:portal_login'):
            response = self.client.get(reverse(route))
            self.assertContains(response, 'rel="manifest"')
            self.assertContains(response, '/static/js/pwa.js')
