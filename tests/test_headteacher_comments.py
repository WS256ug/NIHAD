from copy import deepcopy
from decimal import Decimal
from types import SimpleNamespace

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.reports.comments import COMMENTS, suggest_headteacher_comment
from apps.reports.forms import ReviewForm
from apps.reports.services import generate_reports, review_report, teacher_comment
from apps.schools.forms import SchoolForm
from tests.test_reports import ReportTestCase


class CommentSelectionTests(SimpleTestCase):
    def suggestion(self, average, **extra):
        school = SimpleNamespace(headteacher_outstanding_min=Decimal('80'), headteacher_moderate_min=Decimal('50'))
        return suggest_headteacher_comment(
            {'mode': 'numeric', 'average': average, **extra}, school,
            assessment_id=3, enrollment_id=5,
        )

    def test_exact_boundaries_and_stable_selection(self):
        for average, band in [('0', 'low'), ('49.99', 'low'), ('50', 'moderate'),
                              ('79.99', 'moderate'), ('80', 'outstanding'), ('100', 'outstanding')]:
            with self.subTest(average=average):
                suggestion = self.suggestion(average)
                self.assertEqual(suggestion['band'], band)
                self.assertIn(suggestion['comment'], COMMENTS[band])
                self.assertEqual(suggestion, self.suggestion(average))

    def test_missing_absent_descriptive_and_invalid_results_need_manual_comment(self):
        for value in (None, '', 'NaN', 'Infinity', '-1', '100.01'):
            self.assertIsNone(self.suggestion(value))
        self.assertIsNone(self.suggestion('90', has_absences=True))
        self.assertIsNone(self.suggestion('90', subjects=[{'absent': True}]))
        self.assertIsNone(self.suggestion('90', mode='descriptive'))

    def test_return_requires_a_reason_and_manual_results_require_comment(self):
        self.assertFalse(ReviewForm({'comment': '', 'decision': 'return'}, suggested_comment='Excellent results.').is_valid())
        self.assertFalse(ReviewForm({'comment': '', 'decision': 'approve'}).is_valid())
        self.assertTrue(ReviewForm({'comment': '', 'decision': 'approve'}, suggested_comment='Excellent results.').is_valid())


class AutomaticCommentWorkflowTests(ReportTestCase):
    def test_generation_stores_comment_and_policy_without_approving(self):
        report = self.generated()
        self.assertIn(report.headteacher_comment, COMMENTS['moderate'])
        self.assertEqual(report.snapshot['headteacher_comment_suggestion']['comment'], report.headteacher_comment)
        self.assertEqual(report.status, 'draft')
        self.assertNotIn('headteacher_name', report.snapshot)
        self.assertEqual(generate_reports(self.assessment, self.actor)[0].headteacher_comment, report.headteacher_comment)

    def test_review_prefills_and_blank_approval_retains_generated_comment(self):
        report = teacher_comment(self.generated(), 'Good progress.', self.teacher.user)
        expected = report.headteacher_comment
        self.client.force_login(self.users[User.Role.HEADTEACHER])
        url = reverse('reports:review', args=[report.pk])
        self.assertContains(self.client.get(url), expected)
        self.assertEqual(self.client.post(url, {'comment': '', 'decision': 'approve'}).status_code, 302)
        report.refresh_from_db()
        self.assertEqual(report.status, 'approved')
        self.assertEqual(report.headteacher_comment, expected)
        self.assertIn('headteacher_name', report.snapshot)

    def test_existing_review_gets_suggestion_and_allows_override(self):
        report = teacher_comment(self.generated(), 'Good progress.', self.teacher.user)
        report.headteacher_comment = ''
        report.snapshot.pop('headteacher_comment_suggestion')
        report.save()
        self.client.force_login(self.users[User.Role.HEADTEACHER])
        url = reverse('reports:review', args=[report.pk])
        response = self.client.get(url)
        self.assertIn(response.context['form'].initial['comment'], COMMENTS['moderate'])
        report.refresh_from_db()
        self.assertEqual(report.headteacher_comment, '')  # GET never writes historical records.
        self.client.post(url, {'comment': 'Excellent improvement in reading.', 'decision': 'approve'})
        report.refresh_from_db()
        self.assertEqual(report.headteacher_comment, 'Excellent improvement in reading.')

    def test_configurable_thresholds_and_published_history(self):
        report = self.published()
        original = deepcopy(report.snapshot)
        comment = report.headteacher_comment
        form = SchoolForm({'name': self.school.name, 'currency_code': 'UGX',
                           'headteacher_outstanding_min': '70', 'headteacher_moderate_min': '60'}, instance=self.school)
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        suggestion = suggest_headteacher_comment(report.snapshot, self.school, assessment_id=report.assessment_id, enrollment_id=report.enrollment_id)
        self.assertEqual(suggestion['band'], 'outstanding')
        report.refresh_from_db()
        self.assertEqual(report.snapshot, original)
        self.assertEqual(report.headteacher_comment, comment)
        with self.assertRaises(ValidationError):
            review_report(report, '', True, self.users[User.Role.HEADTEACHER])

    def test_invalid_thresholds_are_rejected(self):
        for moderate, outstanding in [('80', '80'), ('90', '70'), ('-1', '80'), ('50', '101')]:
            form = SchoolForm({'name': self.school.name, 'currency_code': 'UGX',
                               'headteacher_moderate_min': moderate, 'headteacher_outstanding_min': outstanding}, instance=self.school)
            self.assertFalse(form.is_valid())
