import json
from io import BytesIO
from tempfile import TemporaryDirectory

from PIL import Image
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.urls import reverse

from apps.accounts.models import User
from apps.academics.catalog import RESOURCES
from apps.academics.models import Mark
from apps.finance.models import Payment
from tests.test_finance import FinanceTestCase
from tests.test_reports import ReportTestCase


HEADERS = {"HTTP_HX_REQUEST": "true", "HTTP_HX_TARGET": "configuration-dialog-content"}


class WorkspaceDialogTests(ReportTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.actor)

    def test_remaining_forms_render_fragments_with_correct_post_destination(self):
        routes = [
            ("accounts:user_create", []), ("accounts:user_edit", [self.teacher.user_id]),
            ("accounts:user_deactivate", [self.teacher.user_id]), ("accounts:password_change", []),
            ("students:create", []), ("students:edit", [self.student.pk]),
            ("students:guardian_edit", [self.guardian.pk]), ("students:guardian_add", [self.student.pk]),
            ("students:enroll", [self.student.pk]), ("students:status", [self.student.pk]),
            ("schools:profile", []), ("schools:current_period", []),
            ("schools:record_deactivate", ["sections", self.primary.pk]),
            ("finance:structure_create", []), ("finance:charge_create", []),
            ("promotions:create", []), ("academics:mark_form", [self.assessment.pk, self.subject.pk, self.enrollment.pk]),
        ]
        routes += [("academics:record_create", [kind]) for kind in RESOURCES]
        routes += [("expenses:create", [kind]) for kind in ("categories", "expenses", "income")]
        for name, args in routes:
            with self.subTest(name=name, args=args):
                url = reverse(name, args=args)
                response = self.client.get(url, **HEADERS)
                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, "includes/dialog_base.html")
                self.assertNotContains(response, "<!doctype html>")
                self.assertContains(response, f'hx-post="{url}"')
                self.assertContains(response, 'hx-encoding="multipart/form-data"')
                self.assertContains(response, 'name="csrfmiddlewaretoken"')

    def test_student_validation_preserves_values_and_photo_upload_is_saved(self):
        url = reverse("students:edit", args=[self.student.pk])
        response = self.client.post(url, self.student_data(first_name="", last_name="Retained"), **HEADERS)
        self.assertContains(response, 'value="Retained"')
        self.assertTemplateUsed(response, "includes/dialog_base.html")
        self.student.refresh_from_db()
        self.assertEqual(self.student.last_name, "Wasswa")
        buffer = BytesIO()
        Image.new("RGB", (20, 20), "blue").save(buffer, format="PNG")
        with TemporaryDirectory() as media, self.settings(MEDIA_ROOT=media):
            photo = SimpleUploadedFile("photo.png", buffer.getvalue(), content_type="image/png")
            response = self.client.post(url, self.student_data(photo=photo), **HEADERS)
            self.assertEqual(response.status_code, 204)
            payload = json.loads(response.headers["HX-Trigger"])["formSaved"]
            self.assertEqual(payload["url"], reverse("students:detail", args=[self.student.pk]))
            self.student.refresh_from_db()
            self.assertTrue(self.student.photo.storage.exists(self.student.photo.name))

    def test_teacher_marks_validate_and_save_without_navigation(self):
        self.client.force_login(self.teacher.user)
        url = reverse("academics:mark_form", args=[self.assessment.pk, self.subject.pk, self.enrollment.pk])
        response = self.client.post(url, {"score": "101", "expected_revision": 0}, **HEADERS)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors)
        self.assertFalse(Mark.objects.exists())
        response = self.client.post(url, {"score": "80", "expected_revision": 0}, **HEADERS)
        self.assertEqual(response.status_code, 204)
        self.assertEqual(Mark.objects.get().score, 80)

    def test_report_comment_retains_report_workflow(self):
        report = self.generated()
        self.client.force_login(self.teacher.user)
        url = reverse("reports:comment", args=[report.pk])
        self.assertTemplateUsed(self.client.get(url, **HEADERS), "includes/dialog_base.html")
        response = self.client.post(url, {"comment": "Good progress."}, **HEADERS)
        self.assertEqual(response.status_code, 204)
        report.refresh_from_db()
        self.assertEqual(report.status, "review")

    def test_promotion_creation_continues_to_decisions_and_preview_in_dialog(self):
        data = {"source_year": self.year.pk, "source_class": self.academic_class.pk,
                "source_stream": "", "completion_date": "2026-12-31",
                "destination_year": self.next_year.pk, "destination_class": self.academic_class.pk,
                "destination_stream": "", "enrollment_date": "2027-01-02"}
        response = self.client.post(reverse("promotions:create"), data, **HEADERS)
        self.assertEqual(response.status_code, 204)
        step = json.loads(response.headers["HX-Trigger"])["formSaved"]
        self.assertTrue(step["followup"])
        response = self.client.get(step["url"], **HEADERS)
        self.assertTemplateUsed(response, "includes/dialog_base.html")
        formset = response.context["formset"]
        prefix = formset.prefix
        fields = {f"{prefix}-{key}": value for key, value in formset.management_form.initial.items()}
        fields["revision"] = response.context["batch"].revision
        for index, form in enumerate(formset):
            fields.update({f"{prefix}-{index}-enrollment": form.initial["enrollment"],
                           f"{prefix}-{index}-selected": "on", f"{prefix}-{index}-decision": "repeating",
                           f"{prefix}-{index}-notes": ""})
        response = self.client.post(step["url"], fields, **HEADERS)
        self.assertEqual(response.status_code, 204)
        preview = json.loads(response.headers["HX-Trigger"])["formSaved"]
        self.assertTrue(preview["followup"])
        self.assertTemplateUsed(self.client.get(preview["url"], **HEADERS), "includes/dialog_base.html")

    def test_role_and_csrf_restrictions_still_apply(self):
        self.client.force_login(self.users[User.Role.GUARDIAN])
        for url in (reverse("students:create"), reverse("accounts:user_create"), reverse("finance:charge_create")):
            self.assertEqual(self.client.get(url, **HEADERS).status_code, 403)
            self.assertEqual(self.client.post(url, {}, **HEADERS).status_code, 403)
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.actor)
        self.assertEqual(client.post(reverse("students:create"), self.student_data(), **HEADERS).status_code, 403)

    def test_password_change_dialog_keeps_session_authenticated(self):
        response = self.client.post(reverse("accounts:password_change"), {
            "old_password": self.password, "new_password1": self.new_password, "new_password2": self.new_password,
        }, **HEADERS)
        self.assertEqual(response.status_code, 204)
        self.assertEqual(self.client.get(reverse("accounts:profile")).status_code, 200)

    def test_direct_form_pages_and_filter_urls_remain_available(self):
        response = self.client.get(reverse("students:create"))
        self.assertContains(response, "<!doctype html>")
        self.assertNotContains(response, 'hx-post="' + reverse("students:create") + '"')
        for name in ("students:list", "accounts:user_list"):
            self.assertContains(self.client.get(reverse(name)), 'hx-push-url="true"')


class FinanceDialogTests(FinanceTestCase):
    def test_payment_dialog_saves_once_and_returns_receipt_link(self):
        self.client.force_login(self.users[User.Role.BURSAR])
        url = reverse("finance:payment_create", args=[self.charge.pk])
        response = self.client.get(url, **HEADERS)
        self.assertTemplateUsed(response, "includes/dialog_base.html")
        data = {**self.payment_data(), "confirm": "on"}
        response = self.client.post(url, data, **HEADERS)
        self.assertEqual(response.status_code, 204)
        payload = json.loads(response.headers["HX-Trigger"])["formSaved"]
        self.assertEqual(payload["url"], reverse("finance:receipt", args=[Payment.objects.get().pk]))
        self.assertFalse(payload["followup"])
        self.assertEqual(self.client.post(url, data, **HEADERS).status_code, 204)
        self.assertEqual(Payment.objects.count(), 1)
