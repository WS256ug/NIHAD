from datetime import date
from unittest.mock import patch
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import Client
from django.urls import reverse
from apps.accounts.models import User
from apps.promotions.forms import BatchForm
from apps.promotions.models import PromotionBatch
from apps.promotions.services import confirm_batch, create_batch, save_decisions
from apps.schools.models import AcademicClass
from apps.students.models import Enrollment, Student
from tests.test_reports import ReportTestCase


class PromotionTests(ReportTestCase):
    def setUp(self):
        super().setUp()
        self.destination = AcademicClass.objects.create(section=self.primary, name='Next class', sort_order=6)

    def batch_data(self):
        return {'source_year': self.year.pk, 'source_class': self.academic_class.pk, 'source_stream': '', 'completion_date': '2026-12-31', 'destination_year': self.next_year.pk, 'destination_class': self.destination.pk, 'destination_stream': '', 'enrollment_date': '2027-01-02'}

    def batch(self, decision='promoted'):
        form = BatchForm(self.batch_data())
        self.assertTrue(form.is_valid(), form.errors)
        batch = create_batch(form, self.actor)
        return save_decisions(batch, [{'enrollment': self.enrollment, 'selected': True, 'decision': decision, 'notes': ''}], 0, self.actor)

    def test_promote_creates_new_enrollment_and_preserves_report_and_history(self):
        report = self.published()
        original = report.snapshot.copy()
        batch = self.batch()
        confirm_batch(batch, batch.revision, self.actor)
        self.enrollment.refresh_from_db()
        self.assertEqual(self.enrollment.status, 'promoted')
        self.assertEqual(self.enrollment.academic_class_id, self.academic_class.pk)
        self.assertEqual(self.enrollment.academic_year_id, self.year.pk)
        current = self.student.enrollments.get(academic_year=self.next_year)
        self.assertEqual(current.academic_class_id, self.destination.pk)
        report.refresh_from_db()
        self.assertEqual(report.snapshot, original)
        self.assertEqual(report.enrollment_id, self.enrollment.pk)

    def test_repeat_stays_in_source_class_and_stream_in_new_year(self):
        batch = self.batch('repeating')
        confirm_batch(batch, batch.revision, self.actor)
        new = self.student.enrollments.get(academic_year=self.next_year)
        self.assertEqual((new.academic_class_id, new.stream_id), (self.academic_class.pk, self.stream.pk))

    def test_terminal_decision_closes_history_without_new_enrollment(self):
        batch = self.batch('graduated')
        confirm_batch(batch, batch.revision, self.actor)
        self.student.refresh_from_db()
        self.assertEqual(self.student.status, 'graduated')
        self.assertEqual(self.student.enrollments.count(), 1)
        self.assertEqual(self.student.enrollments.get().status, 'graduated')

    def test_confirmation_is_idempotent_and_decisions_become_immutable(self):
        batch = self.batch()
        confirm_batch(batch, batch.revision, self.actor)
        confirm_batch(batch, batch.revision, self.actor)
        self.assertEqual(self.student.enrollments.count(), 2)
        decision = batch.decisions.get()
        decision.decision = 'withdrawn'
        with self.assertRaises(ValidationError):
            decision.full_clean()

    def test_stale_preview_and_stale_selection_are_rejected(self):
        batch = self.batch()
        with self.assertRaisesMessage(ValidationError, 'after the preview'):
            confirm_batch(batch, 0, self.actor)
        with self.assertRaisesMessage(ValidationError, 'another request'):
            save_decisions(batch, [], 0, self.actor)
        self.assertEqual(self.student.enrollments.count(), 1)

    def test_existing_destination_conflict_rolls_back_whole_batch(self):
        batch = self.batch()
        Enrollment.objects.create(student=self.student, academic_year=self.next_year, section=self.primary, academic_class=self.destination, enrollment_date=date(2027, 1, 2))
        with self.assertRaises(ValidationError):
            confirm_batch(batch, batch.revision, self.actor)
        self.enrollment.refresh_from_db()
        self.student.refresh_from_db()
        batch.refresh_from_db()
        self.assertEqual((self.enrollment.status, self.student.status, batch.status), ('current', 'active', 'draft'))

    def test_audit_failure_rolls_back_closure_and_new_enrollment(self):
        batch = self.batch()
        from apps.schools.services import write_record
        def fail_on_new(record, *args, **kwargs):
            if isinstance(record, Enrollment) and record._state.adding:
                raise RuntimeError('New enrollment write failed')
            return write_record(record, *args, **kwargs)
        with patch('apps.promotions.services.write_record', side_effect=fail_on_new):
            with self.assertRaises(RuntimeError):
                confirm_batch(batch, batch.revision, self.actor)
        self.enrollment.refresh_from_db()
        self.assertEqual(self.enrollment.status, 'current')
        self.assertEqual(self.student.enrollments.count(), 1)

    def test_completion_cannot_exclude_recorded_marks(self):
        self.mark()
        self.enrollment.status = 'completed'
        self.enrollment.completion_date = date(2026, 2, 1)
        with self.assertRaisesMessage(ValidationError, 'existing assessment'):
            self.enrollment.full_clean()

    def test_role_matrix_and_csrf(self):
        batch = self.batch()
        for role, user in self.users.items():
            self.client.force_login(user)
            allowed = role in (User.Role.SUPER_ADMIN, User.Role.SCHOOL_ADMIN, User.Role.HEADTEACHER)
            for url in (reverse('promotions:list'), reverse('promotions:create'), reverse('promotions:edit', args=[batch.pk]), reverse('promotions:preview', args=[batch.pk])):
                self.assertEqual(self.client.get(url).status_code, 200 if allowed else 403)
            if not allowed:
                with self.assertRaises(PermissionDenied):
                    confirm_batch(batch, batch.revision, user)
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.actor)
        self.assertEqual(client.post(reverse('promotions:preview', args=[batch.pk]), {'confirm': 'on', 'revision': batch.revision}).status_code, 403)

    def test_http_selection_preview_confirmation(self):
        self.client.force_login(self.actor)
        response = self.client.post(reverse('promotions:create'), self.batch_data(), follow=True)
        self.assertContains(response, 'Choose student decisions')
        batch = PromotionBatch.objects.get()
        data = {'revision': 0, 'form-TOTAL_FORMS': 1, 'form-INITIAL_FORMS': 1, 'form-MIN_NUM_FORMS': 0, 'form-MAX_NUM_FORMS': 1000, 'form-0-enrollment': self.enrollment.pk, 'form-0-selected': 'on', 'form-0-decision': 'promoted', 'form-0-notes': 'Ready for the next class'}
        response = self.client.post(reverse('promotions:edit', args=[batch.pk]), data, follow=True)
        self.assertContains(response, 'Confirm batch')
        response = self.client.post(reverse('promotions:preview', args=[batch.pk]), {'confirm': 'on', 'revision': 1}, follow=True)
        self.assertContains(response, 'Promotion confirmed')

    def test_destination_choices_exclude_same_or_earlier_years_and_classes(self):
        empty = BatchForm()
        self.assertFalse(empty.fields['destination_year'].queryset.exists())
        form = BatchForm(initial=self.batch_data())
        self.assertEqual(list(form.fields['destination_year'].queryset), [self.next_year])
        self.assertNotIn(self.academic_class, form.fields['destination_class'].queryset)
        self.assertIn(self.destination, form.fields['destination_class'].queryset)
        for field, value in [('destination_year', self.year.pk), ('destination_class', self.academic_class.pk)]:
            bad = BatchForm({**self.batch_data(), field: value})
            self.assertFalse(bad.is_valid())
            self.assertIn(field, bad.errors)

    def test_downward_promotion_rejected_on_confirmation_and_cross_section_progression(self):
        from apps.schools.models import Section
        batch = self.batch()
        PromotionBatch.objects.filter(pk=batch.pk).update(destination_class=self.academic_class)
        with self.assertRaises(ValidationError):
            confirm_batch(batch, batch.revision, self.actor)
        self.assertEqual(self.student.enrollments.count(), 1)
        upper = Section.objects.create(school=self.school, name='Upper section', sort_order=self.primary.sort_order + 1)
        upper_class = AcademicClass.objects.create(section=upper, name='First upper class', sort_order=0)
        form = BatchForm({**self.batch_data(), 'destination_class': upper_class.pk})
        self.assertTrue(form.is_valid(), form.errors)

    def test_promotion_choices_refresh_keeps_dialog_and_filters_years(self):
        self.client.force_login(self.actor)
        response = self.client.get(reverse('promotions:create'), {**self.batch_data(), 'dialog': '1'},
                                   HTTP_HX_REQUEST='true', HTTP_HX_TARGET='promotion-batch-form')
        self.assertTemplateUsed(response, 'includes/dialog_base.html')
        self.assertContains(response, 'id="promotion-batch-form"')
        self.assertContains(response, 'hx-select="#promotion-batch-form"')
        self.assertContains(response, 'hx-target="#configuration-dialog-content"')
        self.assertEqual(list(response.context['form'].fields['destination_year'].queryset), [self.next_year])
