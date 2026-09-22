from datetime import timedelta
from unittest.mock import patch
from django.test import Client, RequestFactory, override_settings
from django.urls import reverse
from django.utils import timezone
from apps.accounts.models import AuthenticationBucket, User
from apps.accounts.throttling import client_address
from tests.test_accounts import AccountTestCase


@override_settings(LOGIN_FAILURE_LIMIT=3, AUTH_IP_FAILURE_LIMIT=20, RESET_REQUEST_LIMIT=3, AUTH_WINDOW_SECONDS=60)
class SecurityTests(AccountTestCase):
    def test_failed_logins_are_limited_across_login_pages_without_storing_identity(self):
        for _ in range(3):
            response = self.client.post(reverse('accounts:login'), {'username': 'teacher', 'password': 'incorrect-secret'})
            self.assertEqual(response.status_code, 200)
        for name in ('accounts:login', 'students:portal_login', 'admin:login'):
            response = self.client.post(reverse(name), {'username': 'teacher', 'password': self.password})
            self.assertEqual(response.status_code, 429)
            self.assertIn('Retry-After', response)
            self.assertIn('no-store', response['Cache-Control'])
            self.assertNotContains(response, 'incorrect-secret', status_code=429)
        self.assertNotIn('_auth_user_id', self.client.session)
        for key in AuthenticationBucket.objects.values_list('key', flat=True):
            self.assertEqual(len(key), 64)
            self.assertNotIn('teacher', key)
            self.assertNotIn('127.0.0.1', key)

    def test_expired_window_restores_login_and_success_resets_identity_counter(self):
        for _ in range(3):
            self.client.post(reverse('accounts:login'), {'username': 'teacher', 'password': 'bad'})
        AuthenticationBucket.objects.update(window_started=timezone.now() - timedelta(seconds=61))
        self.assertEqual(self.client.post(reverse('accounts:login'), {'username': 'teacher', 'password': self.password}).status_code, 302)
        self.assertEqual(AuthenticationBucket.objects.count(), 1)

    def test_untrusted_forwarding_headers_cannot_bypass_throttle(self):
        for index in range(3):
            self.client.post(reverse('accounts:login'), {'username': 'teacher', 'password': 'bad'}, HTTP_X_REAL_IP=f'203.0.113.{index + 1}')
        response = self.client.post(reverse('accounts:login'), {'username': 'teacher', 'password': self.password}, HTTP_X_REAL_IP='203.0.113.99')
        self.assertEqual(response.status_code, 429)
        request = RequestFactory().get('/', REMOTE_ADDR='127.0.0.1', HTTP_X_REAL_IP='203.0.113.10')
        self.assertEqual(client_address(request), '127.0.0.1')
        with override_settings(AUTH_TRUSTED_PROXIES=['127.0.0.1']):
            self.assertEqual(client_address(request), '203.0.113.10')

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_password_recovery_is_rate_limited_without_disclosing_account_presence(self):
        for address in ('missing@example.test', 'teacher@example.test', 'other@example.test'):
            self.assertEqual(self.client.post(reverse('accounts:password_reset'), {'email': address}).status_code, 302)
        response = self.client.post(reverse('accounts:password_reset'), {'email': 'missing@example.test'})
        self.assertEqual(response.status_code, 429)

    def test_csp_and_csrf_cover_authentication(self):
        response = self.client.get(reverse('accounts:login'))
        self.assertIn("script-src 'self'", response['Content-Security-Policy'])
        self.assertIn("frame-ancestors 'none'", response['Content-Security-Policy'])
        self.assertEqual(response['X-Content-Type-Options'], 'nosniff')
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(client.post(reverse('accounts:login'), {'username': 'teacher', 'password': self.password}).status_code, 403)
        self.assertEqual(AuthenticationBucket.objects.count(), 0)

    def test_staff_accounts_issued_by_admin_require_initial_password_change(self):
        self.client.force_login(self.users[User.Role.SCHOOL_ADMIN])
        response = self.client.post(reverse('accounts:user_create'), {'username': 'new-individual-teacher', 'first_name': 'Jane', 'last_name': 'Doe', 'email': 'jane@example.test', 'role': 'teacher', 'password1': self.new_password, 'password2': self.new_password})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.get(username='new-individual-teacher').must_change_password)

    @override_settings(DEBUG=False)
    def test_unknown_page_has_safe_error_response(self):
        response = self.client.get('/unknown-private-record/')
        self.assertEqual(response.status_code, 404)
        self.assertNotContains(response, 'Traceback', status_code=404)
