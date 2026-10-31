from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import Client
from django.urls import reverse

from apps.accounts.models import User
from apps.students.forms import StudentRegistrationForm
from apps.students.models import Student
from apps.students.services import save_student, set_portal_access
from tests.test_students import StudentTestCase


class StudentPortalTests(StudentTestCase):
    def provision(self):
        student = set_portal_access(self.student, self.password, True, self.actor)
        return student.portal_user

    def test_registration_number_sign_in_requires_password_and_password_change(self):
        account = self.provision()
        self.assertEqual(account.username, self.student.student_id)
        self.assertTrue(account.check_password(self.password))
        response = self.client.post(reverse("students:portal_login"), {"username": account.username.lower(), "password": self.password})
        self.assertRedirects(response, reverse("students:portal_home"), fetch_redirect_response=False)
        self.assertRedirects(self.client.get(reverse("students:portal_home")), reverse("accounts:password_change"))
        response = self.client.post(reverse("accounts:password_change"), {"old_password": self.password, "new_password1": self.new_password, "new_password2": self.new_password})
        self.assertRedirects(response, reverse("accounts:password_change_done"))
        self.assertContains(self.client.get(reverse("students:portal_home")), "Mary Wasswa")
        account.refresh_from_db()
        self.assertFalse(account.must_change_password)

    def test_registration_number_alone_and_wrong_password_cannot_authenticate(self):
        account = self.provision()
        for password in ("", "incorrect"):
            self.client.post(reverse("students:portal_login"), {"username": account.username, "password": password})
            self.assertNotIn("_auth_user_id", self.client.session)

    def test_staff_and_student_sign_in_are_separate(self):
        account = self.provision()
        self.client.post(reverse("accounts:login"), {"username": account.username, "password": self.password})
        self.assertNotIn("_auth_user_id", self.client.session)
        self.client.post(reverse("students:portal_login"), {"username": self.actor.username, "password": self.password})
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_portal_has_no_access_to_other_students_or_staff_routes(self):
        account = self.provision()
        account.must_change_password = False
        account.save()
        second = Student.objects.create(gender="female", school=self.school, student_id="STD-000099", first_name="Another", last_name="Child", date_of_birth=self.student.date_of_birth, admission_date=self.student.admission_date)
        self.client.force_login(account)
        response = self.client.get(reverse("students:portal_home"), {"student": second.pk, "pk": second.pk})
        self.assertContains(response, "Mary Wasswa")
        self.assertNotContains(response, "Another Child")
        for url in (reverse("students:list"), reverse("students:detail", args=[second.pk]), reverse("students:photo", args=[second.pk]), reverse("students:guardian_list"), reverse("accounts:user_list"), reverse("schools:overview")):
            self.assertEqual(self.client.get(url).status_code, 403)

    def test_admin_password_reset_invalidates_sessions_and_cannot_grant_staff(self):
        account = self.provision()
        account.must_change_password = False
        account.save()
        self.client.force_login(account)
        set_portal_access(self.student, self.new_password, True, self.actor)
        self.assertEqual(self.client.get(reverse("students:portal_home")).status_code, 302)
        account.refresh_from_db()
        self.assertTrue(account.must_change_password)
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.filter(pk=account.pk).update(is_staff=True)

    def test_portal_identity_cannot_be_changed_and_provisioning_is_audited(self):
        account = self.provision()
        account.username = "different"
        with self.assertRaises(ValidationError):
            account.full_clean()
        account.refresh_from_db()
        account.role = User.Role.TEACHER
        with self.assertRaises(ValidationError):
            account.full_clean()

    def test_failed_contact_write_rolls_back_student_registration(self):
        form = StudentRegistrationForm(self.student_data(), school=self.school)
        self.assertTrue(form.is_valid())
        with patch("apps.students.services.add_guardian_contact", side_effect=ValidationError("invalid guardian")):
            with self.assertRaises(ValidationError):
                save_student(form, self.actor)
        self.assertEqual(Student.objects.count(), 1)

    def test_portal_login_and_access_changes_require_csrf(self):
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(client.post(reverse("students:portal_login"), {}).status_code, 403)
        client.force_login(self.actor)
        self.assertEqual(client.post(reverse("students:portal_access", args=[self.student.pk]), {}).status_code, 403)

    def test_portal_access_form_and_new_registration_have_no_guardian_username(self):
        self.client.force_login(self.actor)
        response = self.client.get(reverse("students:create"))
        self.assertContains(response, 'name="guardian_phone"')
        self.assertNotContains(response, 'name="username"')
        response = self.client.post(reverse("students:portal_access", args=[self.student.pk]), {"new_password1": self.password, "new_password2": self.password, "is_active": "on", "confirm": "on"})
        self.assertRedirects(response, reverse("students:detail", args=[self.student.pk]))
