from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.test import Client
from django.urls import reverse

from apps.accounts.models import User
from apps.academics.forms import AssessmentForm, MarkForm
from apps.academics.models import Assessment, AssessmentType, Mark
from apps.academics.services import save_academic, save_mark, set_assessment_status
from apps.schools.models import Stream
from tests.test_academics import AcademicTestCase


class AssessmentTestCase(AcademicTestCase):
    def setUp(self):
        super().setUp()
        self.enrollment = self.enroll(stream=self.stream.pk)
        self.assignment = self.assign(stream=self.stream.pk)
        self.assessment_type = AssessmentType.objects.create(school=self.school, name='Mid-Term')
        # Existing assessments retain their pre-sheet workflow after migration.
        self.assessment = Assessment.objects.create(assessment_type=self.assessment_type, term=self.term, academic_class=self.academic_class, date=date(2026, 3, 1), status='open', requires_mark_review=False)

    def mark_form(self, score='75.00', instance=None, revision=None):
        return MarkForm({'score': score, 'expected_revision': revision if revision is not None else instance.revision if instance else 0}, instance=instance, assessment=self.assessment, enrollment=self.enrollment, subject=self.subject, assignment=self.assignment)

    def mark(self, score='75.00'):
        form = self.mark_form(score)
        self.assertTrue(form.is_valid(), form.errors)
        return save_mark(form, self.teacher.user)

    def mark_url(self):
        return reverse('academics:mark_form', args=[self.assessment.pk, self.subject.pk, self.enrollment.pk])


class AssessmentTests(AssessmentTestCase):
    def test_scores_include_zero_and_max_and_reject_outside_range(self):
        for score in ('0', '100'):
            self.assertTrue(self.mark_form(score).is_valid())
        for score in ('-0.01', '100.01', 'NaN', '', 'abc'):
            self.assertFalse(self.mark_form(score).is_valid())
        mark = self.mark('0')
        self.assertEqual(mark.score, Decimal('0'))
        with self.assertRaises(IntegrityError), transaction.atomic():
            Mark.objects.filter(pk=mark.pk).update(score=-1)

    def test_stale_edits_and_concurrent_creation_are_rejected(self):
        first, second = self.mark_form(), self.mark_form('60')
        self.assertTrue(first.is_valid())
        self.assertTrue(second.is_valid())
        mark = save_mark(first, self.teacher.user)
        with self.assertRaisesMessage(ValidationError, 'another request'):
            save_mark(second, self.teacher.user)
        edit = self.mark_form('80', instance=mark, revision=1)
        self.assertTrue(edit.is_valid(), edit.errors)
        mark = save_mark(edit, self.teacher.user)
        self.assertEqual(mark.revision, 2)

    def test_closed_assessment_denies_new_and_stale_forms(self):
        form = self.mark_form()
        self.assertTrue(form.is_valid())
        set_assessment_status(self.assessment, 'closed', self.actor)
        with self.assertRaisesMessage(ValidationError, 'not open'):
            save_mark(form, self.teacher.user)
        self.assertFalse(Mark.objects.exists())
        set_assessment_status(self.assessment, 'open', self.actor)
        self.mark()

    def test_context_dates_and_limits_are_preserved_after_marks(self):
        self.mark()
        for field, value in [('maximum_score', Decimal('50')), ('date', date(2026, 3, 2)), ('term', self.next_term)]:
            record = Assessment.objects.get(pk=self.assessment.pk)
            setattr(record, field, value)
            with self.assertRaises(ValidationError):
                record.full_clean()
        self.term.end_date = date(2026, 2, 28)
        with self.assertRaisesMessage(ValidationError, 'assessment dates'):
            self.term.full_clean()

    def test_overlapping_assessment_scope_is_rejected(self):
        record = Assessment(assessment_type=self.assessment_type, term=self.term, academic_class=self.academic_class, stream=self.stream, date=date(2026, 3, 1))
        with self.assertRaisesMessage(ValidationError, 'already covers'):
            record.full_clean()

    def test_service_authorization_and_audit_rollback(self):
        form = self.mark_form()
        self.assertTrue(form.is_valid())
        with self.assertRaises(PermissionDenied):
            save_mark(form, self.users[User.Role.HEADTEACHER])
        with patch('apps.schools.services.LogEntry.objects.create', side_effect=RuntimeError('audit')):
            with self.assertRaises(RuntimeError):
                save_mark(form, self.teacher.user)
        self.assertFalse(Mark.objects.exists())

    def test_teacher_scope_subject_stream_and_revocation(self):
        self.client.force_login(self.teacher.user)
        self.assertContains(self.client.get(self.mark_url()), 'Mary')
        self.assignment.is_active = False
        self.assignment.save()
        self.assertEqual(self.client.get(self.mark_url()).status_code, 404)
        self.assertEqual(self.client.post(self.mark_url(), {'score': 50, 'expected_revision': 0}).status_code, 404)

    def test_enrollment_after_assessment_is_excluded(self):
        self.enrollment.enrollment_date = date(2026, 3, 2)
        self.enrollment.save()
        self.client.force_login(self.teacher.user)
        self.assertEqual(self.client.get(self.mark_url()).status_code, 404)

    def test_role_matrix_and_csrf_on_marks(self):
        for role, user in self.users.items():
            self.client.force_login(user)
            can_write = role in (User.Role.SUPER_ADMIN, User.Role.SCHOOL_ADMIN, User.Role.TEACHER)
            self.assertEqual(self.client.get(self.mark_url()).status_code, 200 if can_write else 403)
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.teacher.user)
        self.assertEqual(client.post(self.mark_url(), {'score': 50, 'expected_revision': 0}).status_code, 403)

    def test_http_marks_edit_and_status_flow(self):
        self.client.force_login(self.teacher.user)
        response = self.client.post(self.mark_url(), {'score': '81.5', 'expected_revision': 0}, follow=True)
        self.assertContains(response, '81.5')
        self.client.force_login(self.actor)
        self.assertContains(self.client.get(reverse('academics:record_list', args=['assessments'])), reverse('academics:marks', args=[self.assessment.pk]))
        response = self.client.post(reverse('academics:assessment_close', args=[self.assessment.pk]), {'confirm': 'on'}, follow=True)
        self.assertContains(response, 'Assessment status updated.')
        self.assessment.refresh_from_db()
        self.assertEqual(self.assessment.status, 'closed')
