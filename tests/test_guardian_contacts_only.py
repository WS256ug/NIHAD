from django.test import TestCase, override_settings
from django.urls import reverse
from django.core.exceptions import PermissionDenied

from apps.accounts.forms import StaffSignInForm, ManagedAccountCreationForm
from apps.accounts.models import User
from apps.accounts.permissions import effective_role
from apps.students.services import set_guardian_access


@override_settings(GUARDIAN_ACCOUNTS_ENABLED=False, PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class GuardianContactsOnlyTests(TestCase):
    def test_guardian_login_and_existing_session_are_disabled(self):
        user = User.objects.create_user('old-parent', password='Test-parent-password-123!', role=User.Role.GUARDIAN)
        form = StaffSignInForm(data={'username': user.username, 'password': 'Test-parent-password-123!'})
        self.assertFalse(form.is_valid())
        self.assertIn('Student portal', str(form.errors))
        self.assertIsNone(effective_role(user))
        self.client.force_login(user)
        response = self.client.get(reverse('students:family_home'))
        self.assertRedirects(response, reverse('students:portal_login'), fetch_redirect_response=False)
        self.assertNotIn('_auth_user_id', self.client.session)
        self.assertTrue(User.objects.filter(pk=user.pk).exists())

    def test_admin_cannot_provision_guardian_accounts(self):
        admin = User.objects.create_user('admin-contact-test', role=User.Role.SCHOOL_ADMIN)
        form = ManagedAccountCreationForm(actor=admin)
        self.assertNotIn(User.Role.GUARDIAN, dict(form.fields['role'].choices))
        self.client.force_login(admin)
        self.assertEqual(self.client.get(reverse('students:guardian_access', args=[1])).status_code, 403)
        self.assertEqual(self.client.post(reverse('students:guardian_access', args=[1]), {}).status_code, 403)
        with self.assertRaises(PermissionDenied):
            set_guardian_access(None, {}, admin)
