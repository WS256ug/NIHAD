from django.core.exceptions import PermissionDenied, ValidationError
from django.urls import reverse

from apps.accounts.models import User
from apps.reports.forms import TeacherCommentForm
from apps.reports.services import publish_report, review_report, teacher_comment
from tests.test_reports import ReportTestCase


class AutomaticTeacherCommentTests(ReportTestCase):
    def test_generated_comment_is_prefilled_and_submission_still_required(self):
        report = self.generated()
        self.assertTrue(report.teacher_comment)
        self.assertEqual(report.teacher_comment, report.headteacher_comment)
        self.assertEqual(report.snapshot['teacher_comment_suggestion']['comment'], report.teacher_comment)
        self.assertEqual(report.status, 'draft')
        self.assertNotIn('teacher_name', report.snapshot)
        self.client.force_login(self.teacher.user)
        url = reverse('reports:comment', args=[report.pk])
        self.assertEqual(self.client.get(url).context['form'].initial['comment'], report.teacher_comment)
        expected = report.teacher_comment
        self.assertEqual(self.client.post(url, {'comment': ''}).status_code, 302)
        report.refresh_from_db()
        self.assertEqual(report.status, 'review')
        self.assertEqual(report.teacher_comment, expected)
        self.assertIn('teacher_name', report.snapshot)

    def test_teacher_can_override_without_changing_headteacher_comment(self):
        report = self.generated()
        expected = report.headteacher_comment
        self.client.force_login(self.teacher.user)
        self.client.post(reverse('reports:comment', args=[report.pk]), {'comment': 'Reading has improved.'})
        report.refresh_from_db()
        self.assertEqual(report.teacher_comment, 'Reading has improved.')
        self.assertEqual(report.headteacher_comment, expected)

    def test_old_draft_gets_suggestion_without_writing_on_get(self):
        report = self.generated()
        expected = report.teacher_comment
        report.teacher_comment = ''
        report.snapshot.pop('teacher_comment_suggestion')
        report.save()
        self.client.force_login(self.teacher.user)
        response = self.client.get(reverse('reports:comment', args=[report.pk]))
        self.assertEqual(response.context['form'].initial['comment'], expected)
        report.refresh_from_db()
        self.assertEqual(report.teacher_comment, '')
        report = teacher_comment(report, '', self.teacher.user)
        self.assertEqual(report.teacher_comment, expected)
        self.assertEqual(report.snapshot['teacher_comment_suggestion']['comment'], expected)

    def test_missing_average_needs_manual_comment(self):
        report = self.generated()
        report.teacher_comment = ''
        report.snapshot['average'] = None
        report.snapshot['has_absences'] = True
        report.snapshot.pop('teacher_comment_suggestion')
        report.save()
        self.assertFalse(TeacherCommentForm({'comment': ''}).is_valid())
        with self.assertRaises(ValidationError):
            teacher_comment(report, '', self.teacher.user)
        report.refresh_from_db()
        self.assertEqual(report.status, 'draft')

    def test_automatic_comment_does_not_bypass_permissions_or_publication_lock(self):
        report = self.generated()
        self.class_teacher.is_active = False
        self.class_teacher.save()
        with self.assertRaises(PermissionDenied):
            teacher_comment(report, '', self.teacher.user)
        self.class_teacher.is_active = True
        self.class_teacher.save()
        report = teacher_comment(report, '', self.teacher.user)
        report = review_report(report, '', True, self.users[User.Role.HEADTEACHER])
        report = publish_report(report, self.actor)
        expected = report.teacher_comment
        with self.assertRaises(PermissionDenied):
            teacher_comment(report, '', self.teacher.user)
        report.refresh_from_db()
        self.assertEqual(report.teacher_comment, expected)
