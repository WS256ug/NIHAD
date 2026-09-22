from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import Client, TestCase
from django.urls import reverse

from apps.accounts.permissions import dashboard_url

User = get_user_model()


class UserFoundationTests(TestCase):
    def test_custom_user_is_configured_before_first_migration(self):
        self.assertEqual(settings.AUTH_USER_MODEL, "accounts.User")
        self.assertEqual(User._meta.label, "accounts.User")

    def test_new_user_has_hashed_password_and_no_privileges(self):
        user = User.objects.create_user("guardian", password="test-only-strong-password")
        self.assertEqual(user.role, User.Role.STUDENT)
        self.assertTrue(user.check_password("test-only-strong-password"))
        self.assertNotEqual(user.password, "test-only-strong-password")
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_createsuperuser_assigns_super_admin_role(self):
        user = User.objects.create_superuser("admin", password="test-only-strong-password")
        self.assertEqual(user.role, User.Role.SUPER_ADMIN)
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)

    def test_createsuperuser_rejects_conflicting_role(self):
        with self.assertRaisesMessage(ValueError, "Superusers must have the Super Admin role"):
            User.objects.create_superuser("admin", role=User.Role.TEACHER)

    def test_invalid_role_is_rejected_by_database(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.create(username="invalid", role="unknown")


class AuthenticationFoundationTests(TestCase):
    password = "test-only-strong-password-73"

    @classmethod
    def setUpTestData(cls):
        cls.users = {
            role: (User.objects.create_superuser(role, password=cls.password)
                   if role == User.Role.SUPER_ADMIN
                   else User.objects.create_user(role, password=cls.password, role=role))
            for role in User.Role.values
        }
        cls.admin = User.objects.create_superuser("admin", password=cls.password)

    def test_anonymous_workspace_requires_login(self):
        response = self.client.get(reverse("dashboard:home"))
        self.assertRedirects(response, reverse("accounts:login") + "?next=/")

    def test_login_renders_local_frontend_assets(self):
        response = self.client.get(reverse("accounts:login"))
        self.assertContains(response, "/static/vendor/oat/oat.min.css")
        self.assertContains(response, "/static/vendor/htmx/htmx.min.js")
        self.assertContains(response, 'name="csrfmiddlewaretoken"')

    def test_every_role_can_sign_in_and_only_see_own_account(self):
        for role, user in self.users.items():
            if role == User.Role.STUDENT:
                continue
            with self.subTest(role=role):
                client = Client()
                response = client.post(reverse("accounts:login"), {
                    "username": user.username, "password": self.password,
                })
                self.assertRedirects(response, dashboard_url(user))
                response = client.get(reverse("dashboard:home"), follow=True)
                self.assertContains(response, f"Welcome, {user.username}.")
                self.assertContains(response, user.get_role_display())
                if not user.is_superuser:
                    self.assertNotContains(response, "Open administration")
                self.assertIn("no-store", response.headers["Cache-Control"])

    def test_role_label_alone_does_not_grant_admin_access(self):
        for user in self.users.values():
            if user.is_superuser:
                continue
            with self.subTest(role=user.role):
                self.client.force_login(user)
                response = self.client.get(reverse("admin:accounts_user_changelist"))
                self.assertEqual(response.status_code, 302)
                self.assertTrue(response.url.startswith(reverse("admin:login")))

    def test_superuser_can_manage_custom_users_in_admin(self):
        self.client.force_login(self.admin)
        self.assertContains(self.client.get(reverse("dashboard:home"), follow=True), "Open administration")
        response = self.client.get(reverse("admin:accounts_user_changelist"))
        self.assertContains(response, "Bursar / Finance")
        response = self.client.get(reverse("admin:accounts_user_add"))
        self.assertContains(response, 'name="role"')
        response = self.client.post(reverse("admin:accounts_user_add"), {
            "username": "new_teacher", "role": User.Role.TEACHER,
            "usable_password": "true", "password1": self.password,
            "password2": self.password,
        })
        self.assertEqual(response.status_code, 302)
        created_user = User.objects.get(username="new_teacher")
        self.assertEqual(created_user.role, User.Role.TEACHER)
        self.assertTrue(created_user.check_password(self.password))
        self.assertFalse(created_user.is_staff)

    def test_invalid_password_never_authenticates(self):
        response = self.client.post(reverse("accounts:login"), {
            "username": "teacher", "password": "incorrect-password",
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Please enter a correct username and password")
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertNotContains(response, "incorrect-password")

    def test_inactive_user_cannot_sign_in(self):
        user = self.users[User.Role.TEACHER]
        user.is_active = False
        user.save(update_fields=["is_active"])
        self.client.post(reverse("accounts:login"), {
            "username": user.username, "password": self.password,
        })
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_login_rejects_external_redirect(self):
        response = self.client.post(reverse("accounts:login"), {
            "username": "teacher", "password": self.password,
            "next": "https://untrusted.example/",
        })
        self.assertRedirects(response, dashboard_url(self.users[User.Role.TEACHER]))

    def test_htmx_login_returns_safe_full_page_redirect(self):
        response = self.client.post(reverse("accounts:login"), {
            "username": "teacher", "password": self.password,
            "next": "https://untrusted.example/",
        }, headers={"HX-Request": "true"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["HX-Redirect"], dashboard_url(self.users[User.Role.TEACHER]))
        self.assertIn("_auth_user_id", self.client.session)

    def test_htmx_invalid_login_returns_replaceable_form(self):
        response = self.client.post(reverse("accounts:login"), {
            "username": "teacher", "password": "wrong",
        }, headers={"HX-Request": "true"})
        self.assertContains(response, 'id="sign-in-panel"')
        self.assertContains(response, "Please enter a correct username and password")
        self.assertNotIn("HX-Redirect", response.headers)

    def test_login_and_logout_require_csrf_and_logout_requires_post(self):
        client = Client(enforce_csrf_checks=True)
        login_url = reverse("accounts:login")
        credentials = {"username": "teacher", "password": self.password}
        self.assertEqual(client.post(login_url, credentials).status_code, 403)
        client.get(login_url)
        response = client.post(login_url, {
            **credentials, "csrfmiddlewaretoken": client.cookies["csrftoken"].value,
        })
        self.assertEqual(response.status_code, 302)
        logout_url = reverse("accounts:logout")
        self.assertEqual(client.get(logout_url).status_code, 405)
        self.assertEqual(client.post(logout_url).status_code, 403)
        response = client.post(logout_url, {
            "csrfmiddlewaretoken": client.cookies["csrftoken"].value,
        })
        self.assertRedirects(response, login_url)
        self.assertNotIn("_auth_user_id", client.session)

    def test_login_escapes_user_controlled_redirect_parameter(self):
        response = self.client.get(reverse("accounts:login"), {"next": '"><script>alert(1)</script>'})
        self.assertNotContains(response, "<script>alert(1)</script>")
