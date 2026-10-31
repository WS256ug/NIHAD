from django.core.exceptions import PermissionDenied
from django.urls import reverse
from apps.accounts.models import User
from apps.accounts.permissions import assignable_roles
from apps.academics.catalog import RESOURCES
from apps.academics.services import save_mark, set_assessment_status
from apps.finance.services import require_finance
from apps.reports.services import generate_reports, teacher_comment, review_report, publish_report, begin_correction
from apps.schools.catalog import CONFIGURATION_TYPES
from apps.schools.forms import SchoolForm
from apps.schools.services import save_configuration, set_current_period
from tests.test_reports import ReportTestCase


class DirectorOfStudiesTests(ReportTestCase):
    def setUp(self):
        super().setUp()
        self.dos = self.users[User.Role.DOS]
        self.client.force_login(self.dos)

    def test_academic_pages_and_navigation(self):
        urls = [reverse(name) for name in ('dashboard:dos', 'schools:overview', 'schools:current_period', 'students:list', 'academics:overview', 'academics:marks_entry', 'reports:list', 'promotions:list')]
        urls += [reverse('schools:record_create', args=[kind]) for kind in CONFIGURATION_TYPES]
        urls += [reverse('academics:record_create', args=[kind]) for kind in RESOURCES]
        urls += [self.mark_url()]
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)
        home = self.client.get(reverse('dashboard:dos'))
        self.assertNotIn('finance_summary', home.context)
        self.assertNotContains(home, reverse('accounts:user_list'))
        self.assertNotContains(home, reverse('expenses:overview'))
        self.assertContains(home, reverse('schools:overview'))
        self.assertIn(User.Role.DOS, assignable_roles(self.actor))
        self.assertEqual(assignable_roles(self.dos), ())

    def test_finance_accounts_and_school_policy_are_denied(self):
        for name in ('finance:overview', 'finance:structures', 'finance:charge_create', 'expenses:overview', 'accounts:user_list', 'schools:profile'):
            url = reverse(name)
            for method in ('get', 'post'):
                with self.subTest(url=url, method=method):
                    self.assertEqual(getattr(self.client, method)(url).status_code, 403)
        with self.assertRaises(PermissionDenied):
            require_finance(self.dos)
        form = SchoolForm(instance=self.school)
        # Even a caller bypassing the view cannot change fee policy.
        form.save = lambda commit: self.school
        with self.assertRaises(PermissionDenied):
            save_configuration(form, self.dos)

    def test_structure_write_and_full_report_lifecycle(self):
        response = self.client.post(reverse('schools:record_create', args=['sections']), {'name': 'New section', 'sort_order': 3})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(self.school.sections.filter(name='New section').exists())
        set_current_period(self.dos, self.year, self.term)
        form = self.mark_form('82')
        self.assertTrue(form.is_valid(), form.errors)
        save_mark(form, self.dos)
        self.assessment = set_assessment_status(self.assessment, 'closed', self.dos)
        report = generate_reports(self.assessment, self.dos)[0]
        report = teacher_comment(report, 'Good progress.', self.dos)
        self.assertEqual(self.client.get(reverse('reports:review', args=[report.pk])).status_code, 200)
        report = review_report(report, 'Keep working hard.', True, self.dos)
        report = publish_report(report, self.dos)
        self.assertEqual(report.status, 'published')
        begin_correction(self.assessment, 'Correct an entry.', self.dos)
        report.refresh_from_db()
        self.assertFalse(report.is_current)

    def test_dos_can_confirm_promotions_preserving_history(self):
        from apps.promotions.forms import BatchForm
        from apps.promotions.services import create_batch, save_decisions, confirm_batch
        from apps.schools.models import AcademicClass
        destination = AcademicClass.objects.create(section=self.primary, name='Next class', sort_order=6)
        form = BatchForm({'source_year': self.year.pk, 'source_class': self.academic_class.pk,
            'source_stream': '', 'completion_date': '2026-12-31',
            'destination_year': self.next_year.pk, 'destination_class': destination.pk,
            'destination_stream': '', 'enrollment_date': '2027-01-02'})
        self.assertTrue(form.is_valid(), form.errors)
        batch = create_batch(form, self.dos)
        batch = save_decisions(batch, [{'enrollment': self.enrollment, 'selected': True,
            'decision': 'repeating', 'notes': ''}], 0, self.dos)
        confirm_batch(batch, batch.revision, self.dos)
        self.enrollment.refresh_from_db()
        self.assertEqual(self.enrollment.status, 'repeating')
        self.assertTrue(self.student.enrollments.filter(academic_year=self.next_year).exists())
