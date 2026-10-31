from django.urls import reverse
from apps.accounts.models import User
from apps.reports.services import teacher_comment, review_report
from tests.test_reports import ReportTestCase


class EndTermLayoutTests(ReportTestCase):
    def test_printable_layout_and_optional_fields(self):
        report = self.generated()
        self.client.force_login(self.actor)
        response = self.client.get(reverse('reports:print', args=[report.pk]))
        self.assertTemplateUsed(response, 'reports/endterm.html')
        self.assertContains(response, 'Student information')
        self.assertContains(response, 'School stamp')
        self.assertContains(response, 'Grading key')
        self.assertContains(response, '0-&lt;50')
        self.assertNotContains(response, 'Promotion decision:')
        self.assertContains(response, 'Next term begins:')
        self.assertContains(response, report.snapshot['next_term_start'])
        self.assertEqual(report.snapshot['date_of_birth'], self.student.date_of_birth.isoformat())
        self.assertEqual(report.snapshot['gender'], self.student.get_gender_display())

    def test_comment_authors_are_captured_before_approval(self):
        report = self.generated()
        teacher = self.teacher.user
        report = teacher_comment(report, 'Good progress.', teacher)
        head = self.users[User.Role.HEADTEACHER]
        report = review_report(report, 'Keep working.', True, head)
        self.assertEqual(report.snapshot['teacher_name'], teacher.get_full_name() or teacher.username)
        self.assertEqual(report.snapshot['headteacher_name'], head.get_full_name() or head.username)
        teacher.first_name = 'Changed'
        teacher.save()
        report.refresh_from_db()
        self.assertNotEqual(report.snapshot['teacher_name'], teacher.get_full_name())
        self.assertTrue(report.snapshot['teacher_comment_date'])
        self.assertTrue(report.snapshot['headteacher_comment_date'])

    def test_legacy_snapshot_without_new_fields_remains_exportable(self):
        report = self.generated()
        for key in ('gender', 'date_of_birth', 'school_email', 'school_website', 'next_term_start', 'grading_key'):
            report.snapshot.pop(key, None)
        report.save()
        self.client.force_login(self.actor)
        detail = self.client.get(reverse('reports:detail', args=[report.pk]))
        self.assertEqual(detail.status_code, 200)
        self.assertNotContains(detail, 'Next term begins:')
        self.assertNotContains(detail, 'Grading key')
        response = self.client.get(reverse('reports:pdf', args=[report.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content.startswith(b'%PDF'))

    def test_grading_key_keeps_original_ranges_when_rules_change(self):
        report = self.generated()
        expected = [{'grade': 'Excellent', 'range': '50-100'}, {'grade': 'Developing', 'range': '0-<50'}]
        self.assertEqual(report.snapshot['grading_key'], expected)
        # Simulate a subsequent configuration change without modifying the report.
        self.scheme.rules.filter(pk=self.high.pk).update(label='Changed', minimum=60)
        report.refresh_from_db()
        self.assertEqual(report.snapshot['grading_key'], expected)
        self.client.force_login(self.actor)
        response = self.client.get(reverse('reports:print', args=[report.pk]))
        self.assertContains(response, '50-100')
        self.assertNotContains(response, 'Changed')

    def test_grading_key_uses_effective_percentage_boundaries(self):
        from decimal import Decimal
        from apps.reports.grading_key import grading_key_snapshot
        self.low.maximum = Decimal('49')
        self.low.save()
        self.assertEqual(grading_key_snapshot(self.scheme)[1]['range'], '0-<50')
        self.scheme.mode = 'descriptive'
        self.assertEqual(grading_key_snapshot(self.scheme), [])
