from datetime import datetime, timedelta
from unittest.mock import patch

from django.contrib.admin.models import ADDITION, CHANGE, LogEntry
from django.contrib.auth.models import AnonymousUser, Group, Permission
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from apps.accounts.models import User
from apps.accounts.permissions import can_manage_accounts, dashboard_url, effective_role, has_role


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class AccountTestCase(TestCase):
    password = "Initial-test-password-73!"
    new_password = "Changed-test-password-94!"

    @classmethod
    def setUpTestData(cls):
        cls.users = {}
        for role in User.Role.values:
            create = User.objects.create_superuser if role == User.Role.SUPER_ADMIN else User.objects.create_user
            cls.users[role] = create(role, email=f"{role}@example.test", password=cls.password, role=role)


class RoleAccessTests(AccountTestCase):
    def test_full_role_access_matrix_and_navigation(self):
        for role, user in self.users.items():
            self.client.force_login(user)
            for target_role in User.Role.values:
                with self.subTest(role=role, target=target_role):
                    response = self.client.get(reverse(f"dashboard:{target_role}"))
                    allowed = role == target_role or user.is_superuser
                    self.assertEqual(response.status_code, 302 if role == target_role and role in (User.Role.STUDENT, User.Role.GUARDIAN) else (200 if allowed else 403))
            if role == User.Role.STUDENT:
                self.assertEqual(self.client.get(dashboard_url(user)).status_code, 404)
                continue
            home = self.client.get(dashboard_url(user))
            self.assertContains(home, 'href="' + reverse("accounts:profile") + '"')
            if role in (User.Role.SUPER_ADMIN, User.Role.SCHOOL_ADMIN):
                self.assertContains(home, 'href="' + reverse("accounts:user_list") + '"')
            else:
                self.assertNotContains(home, 'href="' + reverse("accounts:user_list") + '"')
            self.assertContains(home, f'href="{dashboard_url(user)}" aria-current="page"')

    def test_helpers_reject_anonymous_inactive_and_invalid_roles(self):
        for user in [AnonymousUser(), User(role="unknown"), User(role=User.Role.SUPER_ADMIN)]:
            self.assertIsNone(effective_role(user))
            self.assertFalse(can_manage_accounts(user))
        admin = self.users[User.Role.SUPER_ADMIN]
        admin.is_active = False
        self.assertFalse(has_role(admin, User.Role.TEACHER))

    def test_authenticated_requests_to_other_role_do_not_redirect_in_a_loop(self):
        self.client.force_login(self.users[User.Role.STUDENT])
        response = self.client.get(reverse("dashboard:teacher"), follow=True)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.redirect_chain, [])

    def test_safe_next_is_preserved_but_target_still_checks_role(self):
        response = self.client.post(reverse("accounts:login"), {
            "username": "teacher", "password": self.password, "next": reverse("accounts:profile"),
        })
        self.assertRedirects(response, reverse("accounts:profile"))
        response = self.client.post(reverse("accounts:login"), {
            "username": "teacher", "password": self.password, "next": reverse("dashboard:bursar"),
        }, follow=True)
        self.assertEqual(response.status_code, 403)

    def test_each_role_logs_out_and_private_pages_require_authentication(self):
        for role, user in self.users.items():
            with self.subTest(role=role):
                self.client.force_login(user)
                response = self.client.post(reverse("accounts:logout"))
                self.assertRedirects(response, reverse("accounts:login"))
                response = self.client.get(dashboard_url(user))
                self.assertEqual(response.status_code, 302)
                self.assertTrue(response.url.startswith(reverse("students:portal_login" if role == User.Role.STUDENT else "accounts:login")))

    def test_staff_with_django_permissions_cannot_enter_privileged_admin(self):
        teacher = self.users[User.Role.TEACHER]
        teacher.is_staff = True
        teacher.save()
        teacher.user_permissions.add(*Permission.objects.filter(content_type__app_label__in=["auth", "accounts"]))
        self.client.force_login(teacher)
        for name in ["admin:index", "admin:accounts_user_changelist", "admin:auth_group_changelist"]:
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 302)
            self.assertTrue(response.url.startswith(reverse("admin:login")))

        self.client.logout()
        response = self.client.post(reverse("admin:login"), {"username": teacher.username, "password": self.password, "next": "/admin/"})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_super_admin_role_requires_superuser_and_staff_at_database_level(self):
        invalid = [
            {"role": User.Role.SUPER_ADMIN},
            {"role": User.Role.TEACHER, "is_superuser": True, "is_staff": True},
            {"role": User.Role.SUPER_ADMIN, "is_superuser": True, "is_staff": False},
        ]
        for fields in invalid:
            with self.subTest(fields=fields), self.assertRaises(IntegrityError), transaction.atomic():
                User.objects.create(username="invalid", **fields)

    def test_role_mismatch_produces_form_validation_error(self):
        user = User(username="invalid", role=User.Role.SUPER_ADMIN)
        with self.assertRaises(ValidationError):
            user.clean()


class AccountManagementTests(AccountTestCase):
    def setUp(self):
        self.actor = self.users[User.Role.SCHOOL_ADMIN]
        self.target = self.users[User.Role.TEACHER]
        self.client.force_login(self.actor)

    def account_data(self, **overrides):
        return {
            "username": "new_account", "email": "new@example.test", "first_name": "New",
            "last_name": "Teacher", "role": User.Role.TEACHER,
            "password1": self.password, "password2": self.password, **overrides,
        }

    def test_school_admin_creates_allowed_roles_without_granting_privileges(self):
        for role in [User.Role.TEACHER, User.Role.HEADTEACHER, User.Role.BURSAR]:
            with self.subTest(role=role):
                response = self.client.post(reverse("accounts:user_create"), self.account_data(
                    username=f"new_{role}", role=role, is_staff="on", is_superuser="on", groups=[1], user_permissions=[1],
                ))
                self.assertRedirects(response, reverse("accounts:user_list"))
                user = User.objects.get(username=f"new_{role}")
                self.assertEqual(user.role, role)
                self.assertTrue(user.check_password(self.password))
                self.assertFalse(user.is_staff or user.is_superuser)
                self.assertEqual(user.groups.count() + user.user_permissions.count(), 0)
                log = LogEntry.objects.get(object_id=str(user.pk), action_flag=ADDITION)
                self.assertEqual(log.user, self.actor)
                self.assertNotIn(self.password, log.change_message)

    def test_school_admin_cannot_create_school_admin_or_superuser(self):
        for role in [User.Role.SCHOOL_ADMIN, User.Role.SUPER_ADMIN, User.Role.STUDENT, "invalid"]:
            with self.subTest(role=role):
                response = self.client.post(reverse("accounts:user_create"), self.account_data(role=role))
                self.assertEqual(response.status_code, 200)
                self.assertIn("role", response.context["form"].errors)
                self.assertFalse(User.objects.filter(username="new_account").exists())

    def test_superuser_can_provision_school_admin_without_staff_access(self):
        self.client.force_login(self.users[User.Role.SUPER_ADMIN])
        response = self.client.post(reverse("accounts:user_create"), self.account_data(role=User.Role.SCHOOL_ADMIN))
        self.assertRedirects(response, reverse("accounts:user_list"))
        user = User.objects.get(username="new_account")
        self.assertEqual(user.role, User.Role.SCHOOL_ADMIN)
        self.assertFalse(user.is_staff or user.is_superuser)

    def test_unauthorized_roles_cannot_read_or_modify_accounts(self):
        endpoints = [
            reverse("accounts:user_list"), reverse("accounts:user_create"),
            reverse("accounts:user_edit", args=[self.target.pk]),
            reverse("accounts:user_deactivate", args=[self.target.pk]),
            reverse("accounts:user_activate", args=[self.target.pk]),
        ]
        for role in [User.Role.HEADTEACHER, User.Role.TEACHER, User.Role.BURSAR, User.Role.STUDENT]:
            self.client.force_login(self.users[role])
            for url in endpoints:
                with self.subTest(role=role, url=url):
                    self.assertEqual(self.client.get(url).status_code, 403)
                    self.assertEqual(self.client.post(url, self.account_data()).status_code, 403)

    def test_privileged_accounts_are_excluded_from_lists_and_direct_updates(self):
        staff = User.objects.create_user("staff_account", role=User.Role.TEACHER, is_staff=True)
        grouped = User.objects.create_user("grouped_account", role=User.Role.TEACHER)
        grouped.groups.add(Group.objects.create(name="Elevated"))
        delegated = User.objects.create_user("delegated_account", role=User.Role.TEACHER)
        delegated.user_permissions.add(Permission.objects.get(codename="change_user", content_type__app_label="accounts"))
        protected = [self.actor, self.users[User.Role.SUPER_ADMIN], staff, grouped, delegated]
        listed = self.client.get(reverse("accounts:user_list")).context["page_obj"].object_list
        self.assertFalse(set(account.pk for account in protected) & {account.pk for account in listed})
        for target in protected:
            for action in ["user_edit", "user_deactivate", "user_activate"]:
                with self.subTest(target=target.username, action=action):
                    url = reverse(f"accounts:{action}", args=[target.pk])
                    self.assertEqual(self.client.get(url).status_code, 404)
                    self.assertEqual(self.client.post(url, self.account_data(confirm=True)).status_code, 404)

    def test_edit_cannot_promote_role_or_set_privilege_fields(self):
        url = reverse("accounts:user_edit", args=[self.target.pk])
        response = self.client.post(url, self.account_data(username=self.target.username, role=User.Role.SCHOOL_ADMIN))
        self.assertIn("role", response.context["form"].errors)
        self.target.refresh_from_db()
        self.assertEqual(self.target.role, User.Role.TEACHER)
        response = self.client.post(url, self.account_data(
            username=self.target.username, role=User.Role.HEADTEACHER,
            is_staff="on", is_superuser="on", password="injected", is_active="",
        ))
        self.assertRedirects(response, reverse("accounts:user_list"))
        self.target.refresh_from_db()
        self.assertEqual(self.target.role, User.Role.HEADTEACHER)
        self.assertTrue(self.target.is_active)
        self.assertFalse(self.target.is_staff or self.target.is_superuser)
        self.assertTrue(self.target.check_password(self.password))
        self.assertTrue(LogEntry.objects.filter(object_id=str(self.target.pk), action_flag=CHANGE).exists())

    def test_status_changes_require_confirmation_and_revoke_session_access(self):
        target_client = Client()
        target_client.force_login(self.target)
        url = reverse("accounts:user_deactivate", args=[self.target.pk])
        self.assertEqual(self.client.get(url).status_code, 200)
        self.client.post(url, {})
        self.target.refresh_from_db()
        self.assertTrue(self.target.is_active)
        self.assertRedirects(self.client.post(url, {"confirm": "on"}), reverse("accounts:user_list"))
        self.target.refresh_from_db()
        self.assertFalse(self.target.is_active)
        self.assertEqual(target_client.get(reverse("dashboard:teacher")).status_code, 302)
        self.assertTrue(User.objects.filter(pk=self.target.pk).exists())
        response = self.client.post(reverse("accounts:user_activate", args=[self.target.pk]), {"confirm": "on"})
        self.assertRedirects(response, reverse("accounts:user_list"))
        self.target.refresh_from_db()
        self.assertTrue(self.target.is_active)

    def test_account_posts_require_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.actor)
        for url in [reverse("accounts:user_create"), reverse("accounts:user_edit", args=[self.target.pk]), reverse("accounts:user_deactivate", args=[self.target.pk])]:
            self.assertEqual(client.post(url, self.account_data(confirm="on")).status_code, 403)

    def test_search_role_filter_and_pagination_preserve_scope(self):
        User.objects.bulk_create([
            User(username=f"search_teacher_{i:02d}", role=User.Role.TEACHER, email=f"teacher{i}@example.test")
            for i in range(23)
        ])
        response = self.client.get(reverse("accounts:user_list"), {"q": "search_teacher", "role": "teacher"}, headers={"HX-Request": "true"})
        self.assertEqual(response.context["page_obj"].paginator.count, 23)
        self.assertEqual(len(response.context["page_obj"]), 20)
        self.assertContains(response, 'id="account-results"')
        self.assertContains(response, 'q=search_teacher&amp;role=teacher&amp;page=2')
        response = self.client.get(reverse("accounts:user_list"), {"role": "super_admin"})
        self.assertContains(response, "No accounts match your search")

    def test_create_validates_passwords_email_and_unique_username(self):
        for data, field in [
            (self.account_data(password2="different"), "password2"),
            (self.account_data(password1="123", password2="123"), "password2"),
            (self.account_data(email=""), "email"),
            (self.account_data(username=self.target.username), "username"),
        ]:
            with self.subTest(field=field):
                response = self.client.post(reverse("accounts:user_create"), data)
                self.assertEqual(response.status_code, 200)
                self.assertIn(field, response.context["form"].errors)
                self.assertFalse(User.objects.filter(username="new_account").exists())


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class PasswordManagementTests(AccountTestCase):
    def setUp(self):
        self.user = self.users[User.Role.TEACHER]

    def reset_url(self, token=None):
        return reverse("accounts:password_reset_confirm", kwargs={
            "uidb64": urlsafe_base64_encode(force_bytes(self.user.pk)),
            "token": token or default_token_generator.make_token(self.user),
        })

    def test_every_role_can_change_password_and_keep_current_session(self):
        for role, user in self.users.items():
            with self.subTest(role=role):
                client = Client()
                other_session = Client()
                client.force_login(user)
                other_session.force_login(user)
                response = client.post(reverse("accounts:password_change"), {
                    "old_password": self.password, "new_password1": self.new_password,
                    "new_password2": self.new_password,
                })
                self.assertRedirects(response, reverse("accounts:password_change_done"))
                user.refresh_from_db()
                self.assertTrue(user.check_password(self.new_password))
                self.assertFalse(user.check_password(self.password))
                self.assertEqual(client.get(reverse("accounts:profile")).status_code, 200)
                self.assertEqual(other_session.get(reverse("accounts:profile")).status_code, 302)

    def test_change_password_requires_login_current_password_and_valid_new_password(self):
        url = reverse("accounts:password_change")
        self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(self.user)
        for old, first, second in [("wrong", self.new_password, self.new_password), (self.password, "123", "123"), (self.password, self.new_password, "different")]:
            response = self.client.post(url, {"old_password": old, "new_password1": first, "new_password2": second})
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.context["form"].errors)
            self.user.refresh_from_db()
            self.assertTrue(self.user.check_password(self.password))

    def test_password_forms_require_csrf(self):
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(client.post(reverse("accounts:password_reset"), {"email": self.user.email}).status_code, 403)
        client.force_login(self.user)
        self.assertEqual(client.post(reverse("accounts:password_change"), {}).status_code, 403)
        client.logout()
        response = client.get(self.reset_url())
        self.assertEqual(response.status_code, 302)
        self.assertEqual(client.post(response.url, {"new_password1": self.new_password, "new_password2": self.new_password}).status_code, 403)

    def test_every_role_receives_a_valid_reset_link(self):
        for role, user in self.users.items():
            with self.subTest(role=role):
                response = self.client.post(reverse("accounts:password_reset"), {"email": user.email.upper()})
                self.assertRedirects(response, reverse("accounts:password_reset_done"))
                message = mail.outbox[-1]
                self.assertEqual(message.to, [user.email])
                self.assertIn(user.username, message.body)
                self.assertIn("/accounts/password/reset/", message.body)
                self.assertNotIn(self.password, message.body)

    def test_reset_response_does_not_reveal_missing_or_inactive_accounts(self):
        inactive = User.objects.create_user("inactive", email="inactive@example.test", password=self.password, is_active=False)
        unusable = User.objects.create_user("unusable", email="unusable@example.test")
        responses = []
        for email in [self.user.email, "missing@example.test", inactive.email, unusable.email]:
            responses.append(self.client.post(reverse("accounts:password_reset"), {"email": email}, follow=True))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual({response.redirect_chain[0][0] for response in responses}, {reverse("accounts:password_reset_done")})
        for response in responses:
            self.assertContains(response, "If an active account uses that address")

    def test_reset_link_is_single_use_and_revokes_existing_sessions(self):
        logged_in = Client()
        logged_in.force_login(self.user)
        original_url = self.reset_url()
        response = self.client.get(original_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("set-password", response.url)
        form_url = response.url
        self.assertContains(self.client.get(form_url), "Choose a new password")
        response = self.client.post(form_url, {"new_password1": self.new_password, "new_password2": self.new_password})
        self.assertRedirects(response, reverse("accounts:password_reset_complete"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(self.new_password))
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertEqual(logged_in.get(reverse("accounts:profile")).status_code, 302)
        self.assertContains(self.client.get(original_url), "This link is no longer valid")
        self.assertContains(self.client.get(form_url), "This link is no longer valid")

    def test_expired_and_tampered_tokens_are_rejected(self):
        issued_at = datetime(2026, 1, 1, 12, 0)
        with patch.object(default_token_generator, "_now", return_value=issued_at):
            token = default_token_generator.make_token(self.user)
        with patch.object(default_token_generator, "_now", return_value=issued_at + timedelta(hours=2)):
            self.assertContains(self.client.get(self.reset_url(token)), "This link is no longer valid")
        self.assertContains(self.client.get(self.reset_url("invalid-token")), "This link is no longer valid")
        self.assertContains(self.client.get(reverse("accounts:password_reset_confirm", args=["invalid-uid", "invalid-token"])), "This link is no longer valid")

    def test_reset_rejects_weak_or_mismatched_passwords(self):
        form_url = self.client.get(self.reset_url()).url
        for first, second in [("123", "123"), (self.new_password, "different")]:
            response = self.client.post(form_url, {"new_password1": first, "new_password2": second})
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.context["form"].errors)
            self.user.refresh_from_db()
            self.assertTrue(self.user.check_password(self.password))

    def test_profile_cannot_be_used_to_edit_privileges_or_read_another_user(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("accounts:profile"), {"user_id": self.users[User.Role.SUPER_ADMIN].pk})
        self.assertContains(response, self.user.email)
        self.assertNotContains(response, self.users[User.Role.SUPER_ADMIN].email)
        self.assertEqual(self.client.post(reverse("accounts:profile"), {"role": "super_admin"}).status_code, 405)
