from decimal import Decimal
from copy import deepcopy
from django.core.exceptions import PermissionDenied
from django.urls import reverse
from apps.accounts.models import User
from apps.finance.models import FeeStructure
from apps.finance.services import assign_charge
from apps.reports.pdf import report_pdf
from apps.students.services import set_portal_access
from tests.test_reports import ReportTestCase


class MidTermReportTests(ReportTestCase):
    def setUp(self):
        super().setUp()
        kind = self.assessment.assessment_type
        kind.screen_only_report = True
        kind.save(update_fields=['screen_only_report'])

    def student_login(self):
        student = set_portal_access(self.student, self.password, True, self.actor)
        user = student.portal_user
        user.must_change_password = False
        user.save(update_fields=['must_change_password'])
        self.client.force_login(user)

    def test_screen_layout_and_staff_cannot_export(self):
        report = self.published()
        snapshot = deepcopy(report.snapshot)
        for role in (User.Role.SUPER_ADMIN, User.Role.SCHOOL_ADMIN, User.Role.HEADTEACHER, User.Role.TEACHER):
            self.client.force_login(self.users[role])
            response = self.client.get(reverse('reports:detail', args=[report.pk]))
            self.assertEqual(response.status_code, 200)
            self.assertTemplateUsed(response, 'reports/midterm.html')
            self.assertContains(response, 'Subject results')
            self.assertContains(response, 'Online report')
            self.assertContains(response, snapshot['registration_number'])
            self.assertNotContains(response, 'Download PDF')
            self.assertNotContains(response, 'Print view')
            self.assertNotContains(response, 'Signature')
            self.assertNotContains(response, 'School stamp')
            for output in ('pdf', 'print'):
                self.assertEqual(self.client.get(reverse(f'reports:{output}', args=[report.pk])).status_code, 403)
        report.refresh_from_db()
        self.assertEqual(report.snapshot, snapshot)
        with self.assertRaises(PermissionDenied):
            report_pdf(report)

    def test_student_can_view_published_results_but_cannot_export(self):
        report = self.published()
        self.student_login()
        response = self.client.get(reverse('reports:detail', args=[report.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Good progress.')
        for output in ('pdf', 'print'):
            self.assertEqual(self.client.get(reverse(f'reports:{output}', args=[report.pk])).status_code, 403)

    def test_fee_policy_still_blocks_online_results(self):
        report = self.published()
        structure = FeeStructure.objects.create(term=self.term, academic_class=self.academic_class, name='Tuition', amount=Decimal('100'), due_date=self.assessment.date)
        assign_charge(self.enrollment, structure, self.actor)
        self.school.require_fee_clearance_for_reports = True
        self.school.save()
        self.student_login()
        self.assertEqual(self.client.get(reverse('reports:detail', args=[report.pk])).status_code, 403)

    def test_unpublished_results_stay_hidden_from_student(self):
        report = self.generated()
        self.student_login()
        self.assertEqual(self.client.get(reverse('reports:detail', args=[report.pk])).status_code, 404)

    def test_export_enabled_reports_keep_existing_layout(self):
        kind = self.assessment.assessment_type
        kind.screen_only_report = False
        kind.save()
        report = self.published()
        self.client.force_login(self.actor)
        response = self.client.get(reverse('reports:detail', args=[report.pk]))
        self.assertTemplateUsed(response, 'reports/detail.html')
        self.assertContains(response, 'Download PDF')
        self.assertEqual(self.client.get(reverse('reports:pdf', args=[report.pk])).status_code, 200)
