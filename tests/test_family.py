from datetime import date
from decimal import Decimal
from uuid import uuid4
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import Client
from django.urls import reverse
from apps.accounts.models import User
from apps.finance.models import FeeStructure
from apps.finance.services import assign_charge, record_payment, reverse_payment
from apps.students.models import Guardian, Student
from apps.students.services import set_guardian_access, set_link_active
from apps.reports.services import begin_correction
from tests.test_reports import ReportTestCase


class FamilyPortalTests(ReportTestCase):
    def setUp(self):
        super().setUp()
        self.guardian.user = self.users[User.Role.GUARDIAN]
        self.guardian.save()
        self.guardian_link = self.link()

    def charge_fees(self):
        structure = FeeStructure.objects.create(term=self.term, academic_class=self.academic_class, name='Tuition', amount=Decimal('100'), due_date=date(2026, 3, 1))
        return assign_charge(self.enrollment, structure, self.actor)

    def payment(self, charge, amount):
        return record_payment(charge, {'amount': Decimal(amount), 'date': date(2026, 3, 1), 'method': 'cash', 'reference': '', 'notes': '', 'request_key': uuid4()}, self.actor)

    def test_independent_guardian_login_and_linked_child_home(self):
        response = self.client.post(reverse('accounts:login'), {'username': self.guardian.user.username, 'password': self.password}, follow=True)
        self.assertContains(response, 'Guardian portal')
        self.assertContains(response, self.student.student_id)
        self.assertContains(self.client.get(reverse('students:family_child', args=[self.student.pk])), 'Fees and payments')
        self.assertEqual(self.client.get(reverse('finance:overview')).status_code, 403)
        self.assertEqual(self.client.get(reverse('students:list')).status_code, 403)

    def test_fee_clearance_is_checked_for_html_print_pdf_and_reversal(self):
        report = self.published()
        charge = self.charge_fees()
        self.client.force_login(self.guardian.user)
        for name in ('detail', 'print', 'pdf'):
            self.assertEqual(self.client.get(reverse('reports:' + name, args=[report.pk])).status_code, 403)
        response = self.client.get(reverse('students:family_child', args=[self.student.pk]))
        self.assertContains(response, 'requires fee clearance')
        self.assertNotContains(response, reverse('reports:detail', args=[report.pk]))
        self.assertEqual(self.client.get(reverse('students:family_fees', args=[self.student.pk])).status_code, 200)
        partial = self.payment(charge, '60')
        self.assertEqual(self.client.get(reverse('reports:pdf', args=[report.pk])).status_code, 403)
        final = self.payment(charge, '40')
        for name in ('detail', 'print', 'pdf'):
            self.assertEqual(self.client.get(reverse('reports:' + name, args=[report.pk])).status_code, 200)
        reverse_payment(final, 'Returned payment', self.actor)
        self.assertEqual(self.client.get(reverse('reports:pdf', args=[report.pk])).status_code, 403)
        self.assertEqual(self.client.get(reverse('students:family_receipt_pdf', args=[partial.pk])).status_code, 200)

    def test_disabled_fee_policy_allows_published_reports_but_not_drafts(self):
        report = self.generated()
        self.charge_fees()
        self.school.require_fee_clearance_for_reports = False
        self.school.save()
        self.client.force_login(self.guardian.user)
        self.assertEqual(self.client.get(reverse('reports:detail', args=[report.pk])).status_code, 404)
        from apps.reports.services import teacher_comment, review_report, publish_report
        report = teacher_comment(report, 'Good.', self.teacher.user)
        report = review_report(report, 'Approved.', True, self.users[User.Role.HEADTEACHER])
        report = publish_report(report, self.actor)
        self.assertEqual(self.client.get(reverse('reports:detail', args=[report.pk])).status_code, 200)

    def test_another_guardian_cannot_guess_child_report_or_receipt_ids(self):
        report = self.published()
        charge = self.charge_fees()
        payment = self.payment(charge, '100')
        other = User.objects.create_user('unlinked-guardian', role=User.Role.GUARDIAN, password=self.password)
        self.client.force_login(other)
        paths = [reverse('students:family_child', args=[self.student.pk]), reverse('students:family_fees', args=[self.student.pk]), reverse('students:family_photo', args=[self.student.pk]), reverse('students:family_receipt_pdf', args=[payment.pk]), reverse('reports:detail', args=[report.pk]), reverse('reports:pdf', args=[report.pk])]
        for path in paths:
            self.assertEqual(self.client.get(path).status_code, 404)

    def test_deactivated_link_removes_child_and_report_access_immediately(self):
        report = self.published()
        self.client.force_login(self.guardian.user)
        self.assertEqual(self.client.get(reverse('reports:pdf', args=[report.pk])).status_code, 200)
        set_link_active(self.guardian_link, False, self.actor)
        self.assertEqual(self.client.get(reverse('reports:pdf', args=[report.pk])).status_code, 404)
        self.assertNotContains(self.client.get(reverse('students:family_home')), self.student.student_id)

    def test_published_version_remains_available_during_correction(self):
        report = self.published()
        begin_correction(self.assessment, 'Correct an entry.', self.actor)
        self.client.force_login(self.guardian.user)
        self.assertContains(self.client.get(reverse('students:family_child', args=[self.student.pk])), reverse('reports:detail', args=[report.pk]))
        self.assertEqual(self.client.get(reverse('reports:pdf', args=[report.pk])).status_code, 200)

    def test_guardian_provisioning_first_password_change_and_role_integrity(self):
        self.client.force_login(self.actor)
        response = self.client.post(reverse('students:guardian_access', args=[self.guardian.pk]), {'username': 'ignored', 'new_password1': self.new_password, 'new_password2': self.new_password, 'is_active': 'on', 'confirm': 'on'}, follow=True)
        self.assertContains(response, 'Guardian account saved')
        self.guardian.user.refresh_from_db()
        self.assertTrue(self.guardian.user.must_change_password)
        self.client.logout()
        response = self.client.post(reverse('accounts:login'), {'username': self.guardian.user.username, 'password': self.new_password}, follow=True)
        self.assertEqual(response.request['PATH_INFO'], reverse('accounts:password_change'))
        user = self.guardian.user
        user.role = User.Role.TEACHER
        with self.assertRaises(ValidationError):
            user.full_clean()
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.filter(pk=user.pk).update(is_staff=True)

    def test_no_shared_accounts_required_for_staff_roles(self):
        for role in (User.Role.SUPER_ADMIN, User.Role.SCHOOL_ADMIN, User.Role.HEADTEACHER, User.Role.TEACHER, User.Role.BURSAR, User.Role.GUARDIAN):
            creator = User.objects.create_superuser if role == User.Role.SUPER_ADMIN else User.objects.create_user
            second = creator('another-' + role, role=role, password=self.new_password)
            self.assertNotEqual(second.pk, self.users[role].pk)
            self.assertTrue(second.check_password(self.new_password))
