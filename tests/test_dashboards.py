from django.urls import reverse
from apps.accounts.models import User
from apps.dashboard.metrics import dashboard_metrics
from apps.academics.services import set_assessment_status
from apps.reports.services import generate_reports
from tests.test_reports import ReportTestCase


class DashboardTests(ReportTestCase):
    def test_teacher_pending_marks_and_comments_follow_assignments(self):
        result = dashboard_metrics(self.teacher.user, User.Role.TEACHER)
        values = {card['label']: card['value'] for card in result['metrics']}
        self.assertEqual(values['Marks to enter'], 1)
        self.assertEqual(values['Assigned students'], 1)
        self.assertNotIn('finance_summary', result)
        self.mark()
        self.assessment = set_assessment_status(self.assessment, 'closed', self.actor)
        generate_reports(self.assessment, self.actor)
        result = dashboard_metrics(self.teacher.user, User.Role.TEACHER)
        self.assertEqual({card['label']: card['value'] for card in result['metrics']}['Class-teacher comments due'], 1)

    def test_teacher_and_headteacher_never_receive_financial_context(self):
        for role in (User.Role.TEACHER, User.Role.HEADTEACHER):
            self.client.force_login(self.users[role])
            response = self.client.get(reverse('dashboard:' + role))
            self.assertEqual(response.status_code, 200)
            self.assertNotIn('finance_summary', response.context)
            self.assertNotContains(response, 'Fees collected')
            self.assertNotContains(response, 'Surplus / deficit')

    def test_finance_dashboard_and_admin_have_real_totals(self):
        for role in (User.Role.SCHOOL_ADMIN, User.Role.BURSAR, User.Role.SUPER_ADMIN):
            self.client.force_login(self.users[role])
            response = self.client.get(reverse('dashboard:' + role))
            self.assertContains(response, 'Fees collected')
            self.assertContains(response, 'Outstanding fees')
            self.assertIn('finance_summary', response.context)
        self.assertNotContains(response, 'will appear')
