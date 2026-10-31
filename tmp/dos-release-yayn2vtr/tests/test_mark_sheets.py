from datetime import date
from decimal import Decimal
from io import StringIO
import os
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import User
from apps.academics.forms import MarkForm
from apps.academics.grading import calculate_results, competition_positions
from apps.academics.models import GradeRule, GradingScheme, Mark, MarkSubmission, Subject, TeachingAssignment
from apps.academics.services import save_mark, set_academic_active, set_assessment_status
from apps.reports.services import begin_correction, generate_reports
from apps.students.models import Enrollment, Student
from tests.test_reports import ReportTestCase


class MarkSheetTests(ReportTestCase):
    def setUp(self):
        super().setUp()
        self.assessment.requires_mark_review = True
        self.assessment.save(update_fields=["requires_mark_review"])
        self.second = Student.objects.create(school=self.school, student_id="STD-000002", first_name="Sarah", last_name="Second", gender="female", date_of_birth=date(2018, 1, 1), admission_date=date(2025, 1, 1))
        self.second_enrollment = Enrollment.objects.create(student=self.second, academic_year=self.year, section=self.primary, academic_class=self.academic_class, stream=self.stream, enrollment_date=date(2026, 1, 1))
        self.url = reverse("academics:marks", args=[self.assessment.pk]) + f"?assignment={self.assignment.pk}"
        self.client.force_login(self.teacher.user)

    def test_missing_subject_assignments_explained_and_explicit_selection_wins(self):
        subject = Subject.objects.create(section=self.primary, code="SCI", name="Science")
        self.client.force_login(self.actor)
        response = self.client.get(self.url)
        self.assertContains(response, "Science")
        self.assertContains(response, "Manage teaching assignments")
        self.assertEqual(list(response.context["unassigned_subjects"]), [subject])
        response = self.client.get(self.url + f"&subject={subject.pk}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["assignment"], self.assignment)
        self.client.force_login(self.teacher.user)
        self.assertNotContains(self.client.get(self.url), "Manage teaching assignments")

    def test_close_confirmation_has_no_checkbox_and_button_requires_approval(self):
        self.client.force_login(self.actor)
        self.assertFalse(self.client.get(self.url).context["can_close_marks"])
        close_url = reverse("academics:assessment_close", args=[self.assessment.pk])
        response = self.client.get(close_url, HTTP_HX_REQUEST="true", HTTP_HX_TARGET="configuration-dialog-content")
        self.assertContains(response, "Close marks entry?")
        self.assertContains(response, "All subject sheets must be approved")
        self.assertNotContains(response, 'type="checkbox"')
        response = self.client.post(close_url, {})
        self.assertEqual(response.status_code, 200)
        self.assessment.refresh_from_db()
        self.assertEqual(self.assessment.status, "open")
        self.submit()
        self.review()
        self.client.force_login(self.actor)
        self.assertTrue(self.client.get(self.url).context["can_close_marks"])
        response = self.client.post(close_url, {}, HTTP_HX_REQUEST="true", HTTP_HX_TARGET="configuration-dialog-content")
        self.assertEqual(response.status_code, 204)
        self.assessment.refresh_from_db()
        self.assertEqual(self.assessment.status, "closed")

    def payload(self, action="save", values=None):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        control = response.context["control"]
        data = {"roster": control.initial["roster"], "revision": control.initial["revision"], "action": action}
        for row in response.context["rows"]:
            prefix = row.prefix
            data[f"{prefix}-expected_revision"] = row.initial["expected_revision"]
            data[f"{prefix}-is_absent"] = "on" if row.initial["is_absent"] else ""
            field = "level" if "level" in row.fields else "score"
            data[f"{prefix}-{field}"] = row.initial[field] if row.initial[field] is not None else ""
            for key, value in (values or {}).get(row.enrollment.pk, {}).items():
                data[f"{prefix}-{key}"] = value
        return data

    def submit(self):
        response = self.client.post(self.url, self.payload("submit", {
            self.enrollment.pk: {"score": "80"}, self.second_enrollment.pk: {"score": "70"},
        }))
        self.assertEqual(response.status_code, 302)
        return MarkSubmission.objects.get()

    def review(self, action="approve", note=""):
        self.client.force_login(self.users[User.Role.HEADTEACHER])
        return self.client.post(self.url, {"review-action": action, "review-note": note, "review-revision": MarkSubmission.objects.get().revision})

    def test_sheet_lists_all_students_and_saves_partial_progress_including_zero(self):
        response = self.client.get(self.url)
        self.assertContains(response, "Save progress")
        self.assertContains(response, "Submit for review")
        self.assertContains(response, "Mary Wasswa")
        self.assertContains(response, "Sarah Second")
        response = self.client.post(self.url, self.payload(values={self.enrollment.pk: {"score": "0"}}), follow=True)
        self.assertContains(response, "1 of 2 completed")
        self.assertEqual(Mark.objects.get().score, Decimal("0"))
        self.assertEqual(MarkSubmission.objects.get().status, "draft")
        self.assertFalse(Mark.objects.filter(enrollment=self.second_enrollment).exists())

    def test_submit_requires_all_rows_and_preserves_entered_values(self):
        response = self.client.post(self.url, self.payload("submit", {self.enrollment.pk: {"score": "82"}}))
        self.assertContains(response, "Enter a result or mark this student absent")
        self.assertContains(response, 'value="82"')
        self.assertFalse(Mark.objects.exists())

    def test_invalid_row_does_not_partially_save_other_students(self):
        response = self.client.post(self.url, self.payload(values={self.enrollment.pk: {"score": "80"}, self.second_enrollment.pk: {"score": "101"}}))
        self.assertContains(response, "Enter a mark from 0 to")
        self.assertFalse(Mark.objects.exists())

    def test_submit_locks_bulk_and_single_student_endpoints_until_returned(self):
        stale_payload = self.payload()
        self.submit()
        self.assertEqual(self.client.post(self.url, stale_payload).status_code, 403)
        mark = Mark.objects.get(enrollment=self.enrollment)
        url = reverse("academics:mark_form", args=[self.assessment.pk, self.subject.pk, self.enrollment.pk])
        response = self.client.post(url, {"score": "99", "expected_revision": mark.revision})
        self.assertContains(response, "sheet is locked")
        self.assertEqual(self.review("return").status_code, 200)
        self.assertEqual(MarkSubmission.objects.get().status, "submitted")
        self.assertEqual(self.review("return", "Check the second student's result.").status_code, 302)
        self.client.force_login(self.teacher.user)
        self.assertContains(self.client.get(self.url), "Check the second student")
        response = self.client.post(self.url, self.payload(values={self.enrollment.pk: {"score": "90"}}))
        self.assertEqual(response.status_code, 302)
        mark.refresh_from_db()
        self.assertEqual(mark.score, 90)

    def test_approval_is_required_before_closing_and_reports(self):
        with self.assertRaisesMessage(ValidationError, "Approve the complete marks sheet"):
            set_assessment_status(self.assessment, "closed", self.actor)
        self.submit()
        with self.assertRaises(ValidationError):
            set_assessment_status(self.assessment, "closed", self.actor)
        self.assertEqual(self.review().status_code, 302)
        self.assessment = set_assessment_status(self.assessment, "closed", self.actor)
        self.assertEqual(len(generate_reports(self.assessment, self.actor)), 2)

    def test_headteacher_cannot_change_marks_and_teacher_cannot_approve(self):
        self.submit()
        review_data = {"review-action": "approve", "review-note": "", "review-revision": MarkSubmission.objects.get().revision}
        self.assertEqual(self.client.post(self.url, review_data).status_code, 403)
        self.client.force_login(self.users[User.Role.HEADTEACHER])
        self.assertFalse(self.client.get(self.url).context["can_edit"])
        self.assertEqual(self.client.post(self.url, {"action": "save"}).status_code, 403)

    def test_absence_is_not_zero_and_is_excluded_from_overall_results_and_ranking(self):
        response = self.client.post(self.url, self.payload("submit", {
            self.enrollment.pk: {"score": "0"}, self.second_enrollment.pk: {"score": "", "is_absent": "on"},
        }))
        self.assertEqual(response.status_code, 302)
        absent = Mark.objects.get(enrollment=self.second_enrollment)
        self.assertTrue(absent.is_absent)
        self.assertIsNone(absent.score)
        self.assertEqual(self.review().status_code, 302)
        self.school.enable_ranking = True
        self.school.save()
        self.assessment = set_assessment_status(self.assessment, "closed", self.actor)
        reports = generate_reports(self.assessment, self.actor)
        data = next(report.snapshot for report in reports if report.enrollment_id == self.second_enrollment.pk)
        self.assertEqual(data["subjects"][0]["grade"], "Absent")
        for field in ("total", "average", "aggregate", "division", "position"):
            self.assertIsNone(data[field])
        zero = next(report.snapshot for report in reports if report.enrollment_id == self.enrollment.pk)
        self.assertEqual(zero["average"], "0.00")
        self.assertEqual(zero["position"], 1)
        self.assertEqual(zero["cohort_size"], 1)

    def test_absent_and_score_together_are_rejected(self):
        response = self.client.post(self.url, self.payload(values={self.enrollment.pk: {"score": "40", "is_absent": "on"}}))
        self.assertContains(response, "Clear the result")
        self.assertFalse(Mark.objects.exists())

    def test_descriptive_sheet_uses_learning_levels(self):
        scheme = GradingScheme.objects.create(section=self.primary, name="Learning levels", mode="descriptive")
        level = GradeRule.objects.create(scheme=scheme, label="Achieved")
        scheme = set_academic_active(scheme, True, self.actor)
        self.assessment.grading_scheme = scheme
        self.assessment.save()
        response = self.client.get(self.url)
        self.assertContains(response, "Learning level")
        self.assertNotContains(response, f'name="mark-{self.enrollment.pk}-score"')
        response = self.client.post(self.url, self.payload("submit", {
            self.enrollment.pk: {"level": level.pk}, self.second_enrollment.pk: {"is_absent": "on"},
        }))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Mark.objects.get(enrollment=self.enrollment).level_id, level.pk)

    def test_stale_marks_or_roster_tokens_do_not_overwrite_results(self):
        payload = self.payload(values={self.enrollment.pk: {"score": "50"}})
        self.mark("60")
        response = self.client.post(self.url, payload)
        self.assertContains(response, "changed. Reload before saving")
        self.assertEqual(Mark.objects.get().score, 60)
        data = self.payload()
        data["roster"] += "tampered"
        self.assertContains(self.client.post(self.url, data), "expired or changed")

    def test_changed_roster_invalidates_submission_approval(self):
        self.submit()
        self.second_enrollment.enrollment_date = date(2026, 4, 1)
        self.second_enrollment.save()
        response = self.review()
        self.assertContains(response, "student list changed")
        self.assertEqual(MarkSubmission.objects.get().status, "submitted")

    def test_teacher_assignment_scope_and_csrf(self):
        self.assignment.is_active = False
        self.assignment.save()
        self.assertEqual(self.client.get(self.url).status_code, 404)
        self.assertEqual(self.client.post(self.url, {}).status_code, 404)
        self.assignment.is_active = True
        self.assignment.save()
        for role in (User.Role.GUARDIAN, User.Role.BURSAR):
            self.client.force_login(self.users[role])
            self.assertEqual(self.client.get(self.url).status_code, 403)
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.teacher.user)
        self.assertEqual(client.post(self.url, {"action": "save"}).status_code, 403)

    def test_audit_failure_rolls_back_all_marks_and_submission(self):
        data = self.payload("submit", {self.enrollment.pk: {"score": "80"}, self.second_enrollment.pk: {"score": "70"}})
        with patch("apps.schools.services.LogEntry.objects.create", side_effect=RuntimeError("audit failure")):
            with self.assertRaises(RuntimeError):
                self.client.post(self.url, data)
        self.assertFalse(Mark.objects.exists())
        self.assertFalse(MarkSubmission.objects.exists())

    def test_report_correction_returns_approved_sheets_without_changing_snapshots(self):
        self.submit()
        self.review()
        self.assessment = set_assessment_status(self.assessment, "closed", self.actor)
        reports = generate_reports(self.assessment, self.actor)
        old = reports[0].snapshot.copy()
        begin_correction(self.assessment, "Correct a transcription error", self.actor)
        self.assertEqual(MarkSubmission.objects.get().status, "returned")
        reports[0].refresh_from_db()
        self.assertEqual(reports[0].snapshot, old)

    def test_explicit_stream_assignment_does_not_include_other_streams(self):
        self.second_enrollment.stream = None
        self.second_enrollment.save()
        response = self.client.get(self.url)
        self.assertContains(response, "Mary Wasswa")
        self.assertNotContains(response, "Sarah Second")

    def test_new_assessments_disable_review_by_default(self):
        self.assertFalse(self.assessment._meta.get_field("requires_mark_review").default)

    def test_review_off_saves_closes_and_generates_without_submission(self):
        self.assessment.requires_mark_review = False
        self.assessment.save(update_fields=["requires_mark_review"])
        self.assertNotContains(self.client.get(self.url), "Submit for review")
        values = {self.enrollment.pk: {"score": "80"}, self.second_enrollment.pk: {"score": "70"}}
        forged = self.client.post(self.url, self.payload("submit", values))
        self.assertEqual(forged.status_code, 200)
        self.assertFalse(Mark.objects.exists())
        self.assertEqual(self.client.post(self.url, self.payload("save", values)).status_code, 302)
        self.assessment.refresh_from_db()
        self.assertFalse(self.assessment.requires_mark_review)
        self.assertEqual(MarkSubmission.objects.get().status, "draft")
        self.client.force_login(self.actor)
        self.assertTrue(self.client.get(self.url).context["can_close_marks"])
        response = self.client.post(reverse("academics:assessment_close", args=[self.assessment.pk]), {})
        self.assertEqual(response.status_code, 302)
        self.assessment.refresh_from_db()
        self.assertEqual(self.assessment.status, "closed")
        self.assertEqual(len(generate_reports(self.assessment, self.actor)), 2)

    def test_review_toggle_is_editable_and_old_submissions_do_not_lock_when_off(self):
        from apps.academics.forms import AssessmentForm
        from apps.academics.services import save_academic
        self.submit()
        def toggle(enabled):
            self.assessment.refresh_from_db()
            data = {"assessment_type": self.assessment.assessment_type_id, "term": self.term.pk,
                    "academic_class": self.academic_class.pk, "stream": self.assessment.stream_id or "",
                    "date": self.assessment.date, "maximum_score": self.assessment.maximum_score,
                    "requires_mark_review": enabled}
            form = AssessmentForm(data, instance=self.assessment, school=self.school, actor=self.actor)
            self.assertTrue(form.is_valid(), form.errors)
            save_academic(form, self.actor)
        toggle(False)
        self.assertTrue(self.client.get(self.url).context["can_edit"])
        self.assertEqual(self.client.post(self.url, self.payload("save", {self.enrollment.pk: {"score": "81"}})).status_code, 302)
        self.assertEqual(MarkSubmission.objects.get().status, "draft")
        self.client.force_login(self.actor)
        self.assertEqual(self.review().status_code, 403)
        toggle(True)
        self.client.force_login(self.teacher.user)
        self.assertContains(self.client.get(self.url), "Submit for review")
        self.assertEqual(self.client.post(self.url, self.payload("submit")).status_code, 302)
        self.assertEqual(self.review().status_code, 302)


@override_settings(DEBUG=True, PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class DemoMarkSheetTests(TestCase):
    def test_demo_school_includes_reviewed_sheets_and_reports(self):
        with patch.dict(os.environ, {"NIHAD_DEMO_PASSWORD": "Demo-test-password-95!"}):
            call_command("seed_demo", stdout=StringIO())
        self.assertTrue(MarkSubmission.objects.exists())
        self.assertFalse(MarkSubmission.objects.exclude(status="approved").exists())
