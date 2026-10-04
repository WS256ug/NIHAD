from datetime import date
from decimal import Decimal
from unittest.mock import patch
from uuid import uuid4

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import Client
from django.urls import reverse

from apps.accounts.models import User
from apps.finance.models import FeeConcession, FeeStructure
from apps.finance.queries import balance_summary, charge_balance, finance_totals, student_balances
from apps.finance.services import agree_fee, assign_charge, cancel_charge, record_payment, reverse_concession, reverse_payment
from apps.students.services import set_portal_access
from tests.test_finance import FinanceTestCase
from tests.test_reports import ReportTestCase


class FeeAgreementTests(FinanceTestCase):
    def test_portal_statement_shows_only_applicable_fees(self):
        account = set_portal_access(self.student, self.password, True, self.actor).portal_user
        account.must_change_password = False
        account.save()
        self.client.force_login(account)
        url = reverse('students:family_fees', args=[self.student.pk])
        self.assertContains(self.client.get(url), '400.3')
        agree_fee(self.charge, '300', 'Private negotiation reason', self.actor)
        self.pay(amount=Decimal('100'))
        response = self.client.get(url)
        self.assertContains(response, '<strong>Charged:</strong> 300', html=False)
        self.assertContains(response, '<strong>Paid:</strong> 100', html=False)
        self.assertContains(response, '<strong>Balance:</strong> 200', html=False)
        for hidden in ('400.3', 'Original fee', 'Agreed fee', 'concession', 'Private negotiation reason', 'Set agreed fee'):
            self.assertNotContains(response, hidden)
        self.assertContains(response, 'Payments')
        self.assertContains(response, reverse('students:family_receipt', args=[self.charge.payments.get().pk]))
        self.client.force_login(self.actor)
        response = self.client.get(reverse('finance:statement', args=[self.student.pk]))
        for visible in ('Original fee', 'Agreed fee', 'Fee concessions', 'Private negotiation reason'):
            self.assertContains(response, visible)

    def test_net_balances_receipts_and_payment_limit(self):
        concession = agree_fee(self.charge, Decimal('300'), 'Negotiated tuition', self.actor)
        self.assertEqual(concession.amount, Decimal('100.30'))
        self.assertEqual(concession.created_by, self.actor)
        self.assertEqual(charge_balance(self.charge), Decimal('300'))
        with self.assertRaises(ValidationError):
            self.pay(amount=Decimal('300.01'))
        payment = self.pay(amount=Decimal('300'))
        self.assertEqual(payment.previous_balance, Decimal('300'))
        self.assertEqual(payment.new_balance, 0)
        self.assertEqual(balance_summary(self.student)['balance'], 0)
        self.assertEqual(finance_totals()['balance'], 0)
        self.assertEqual(student_balances().get(pk=self.student.pk).balance, 0)
        self.charge.refresh_from_db()
        self.assertEqual(self.charge.amount, Decimal('400.30'))
        reverse_payment(payment, 'Returned', self.actor)
        self.assertEqual(balance_summary(self.student)['balance'], Decimal('300'))

    def test_invalid_duplicate_and_below_paid_agreements(self):
        for amount in ('-1', '401', '400.30', '1.001', 'NaN', 'Infinity'):
            with self.subTest(amount=amount), self.assertRaises(ValidationError):
                agree_fee(self.charge, amount, 'Reason', self.actor)
        with self.assertRaises(ValidationError):
            agree_fee(self.charge, '300', ' ', self.actor)
        self.pay(amount=Decimal('200'))
        with self.assertRaises(ValidationError):
            agree_fee(self.charge, '199', 'Reason', self.actor)
        agree_fee(self.charge, '300', 'Reason', self.actor)
        with self.assertRaises(ValidationError):
            agree_fee(self.charge, '300', 'Duplicate', self.actor)

    def test_reversal_replacement_and_charge_cancellation(self):
        concession = agree_fee(self.charge, '300', 'Reason', self.actor)
        reverse_concession(concession, 'Correction', self.actor)
        self.assertEqual(charge_balance(self.charge), Decimal('400.30'))
        with self.assertRaises(ValidationError):
            reverse_concession(concession, 'Again', self.actor)
        agree_fee(self.charge, '200', 'Revised agreement', self.actor)
        self.assertEqual(charge_balance(self.charge), Decimal('200'))
        cancel_charge(self.charge, 'Wrong charge', self.actor)
        self.assertEqual(balance_summary(self.student)['balance'], 0)
        self.assertEqual(student_balances().get(pk=self.student.pk).balance, 0)
        self.assertEqual(finance_totals()['balance'], 0)
        with self.assertRaises(ValidationError):
            agree_fee(self.charge, '100', 'Cancelled', self.actor)

    def test_audit_failure_rolls_back(self):
        with patch('apps.schools.services.LogEntry.objects.create', side_effect=RuntimeError('audit')):
            with self.assertRaises(RuntimeError):
                agree_fee(self.charge, '300', 'Reason', self.actor)
        self.assertFalse(FeeConcession.objects.exists())

    def test_permissions_form_history_and_csrf(self):
        url = reverse('finance:fee_agreement', args=[self.charge.pk])
        for role, user in self.users.items():
            allowed = role in (User.Role.SUPER_ADMIN, User.Role.SCHOOL_ADMIN, User.Role.BURSAR)
            self.client.force_login(user)
            self.assertEqual(self.client.get(url).status_code, 200 if allowed else 403)
            if not allowed:
                self.assertEqual(self.client.post(url, {'agreed_amount': '300', 'reason': 'Reason', 'confirm': 'on'}).status_code, 403)
                with self.assertRaises(PermissionDenied):
                    agree_fee(self.charge, '300', 'Reason', user)
        self.client.force_login(self.actor)
        response = self.client.post(url, {'agreed_amount': '300', 'reason': 'Approved agreement', 'confirm': 'on'}, follow=True)
        self.assertContains(response, 'Approved agreement')
        self.assertContains(response, '100.3')
        self.assertTrue(self.client.get(reverse('finance:statement_pdf', args=[self.student.pk])).content.startswith(b'%PDF'))
        concession = FeeConcession.objects.get()
        reverse_url = reverse('finance:concession_reverse', args=[concession.pk])
        teacher = self.users[User.Role.TEACHER]
        self.client.force_login(teacher)
        self.assertEqual(self.client.post(reverse_url, {'reason': 'No', 'confirm': 'on'}).status_code, 403)
        with self.assertRaises(PermissionDenied):
            reverse_concession(concession, 'No', teacher)
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.actor)
        self.assertEqual(csrf_client.post(reverse_url, {'reason': 'Correction', 'confirm': 'on'}).status_code, 403)
        self.client.force_login(self.actor)
        self.assertEqual(self.client.post(reverse_url, {'reason': 'Correction', 'confirm': 'on'}).status_code, 302)


class NegotiatedReportAccessTests(ReportTestCase):
    def test_student_report_routes_follow_agreement_and_reversals(self):
        report = self.published()
        structure = FeeStructure.objects.create(term=self.term, academic_class=self.academic_class, name='Tuition', amount=Decimal('800000'), due_date=date(2026, 3, 1))
        charge = assign_charge(self.enrollment, structure, self.actor)
        concession = agree_fee(charge, '600000', 'Negotiated fee', self.actor)
        account = set_portal_access(self.student, self.password, True, self.actor).portal_user
        account.must_change_password = False
        account.save()
        self.client.force_login(account)
        data = {'amount': Decimal('500000'), 'date': date(2026, 3, 1), 'method': 'cash', 'notes': '', 'request_key': uuid4()}
        record_payment(charge, data, self.actor)
        blocked = self.client.get(reverse('reports:list'))
        self.assertContains(blocked, 'Fee clearance required')
        self.assertContains(blocked, reverse('students:family_fees', args=[self.student.pk]))
        self.assertNotContains(blocked, reverse('reports:detail', args=[report.pk]))
        for name in ('detail', 'print', 'pdf'):
            self.assertEqual(self.client.get(reverse('reports:' + name, args=[report.pk])).status_code, 403)
        record_payment(charge, {**data, 'amount': Decimal('100000'), 'request_key': uuid4()}, self.actor)
        for name in ('detail', 'print', 'pdf'):
            self.assertEqual(self.client.get(reverse('reports:' + name, args=[report.pk])).status_code, 200)
        report_url = reverse('reports:detail', args=[report.pk])
        listing = self.client.get(reverse('reports:list'))
        self.assertTemplateUsed(listing, 'reports/portal_list.html')
        self.assertContains(listing, report_url)
        self.assertContains(listing, reverse('reports:pdf', args=[report.pk]))
        self.assertContains(listing, reverse('reports:print', args=[report.pk]))
        self.assertNotContains(listing, 'Version')
        self.assertNotContains(listing, 'name="status"')
        detail = self.client.get(report_url)
        self.assertNotContains(detail, 'Version')
        self.assertNotContains(detail, 'Report versions')
        self.assertContains(self.client.get(reverse('students:portal_home')), '1 report available.')
        reverse_concession(concession, 'Agreement withdrawn', self.actor)
        self.assertNotContains(self.client.get(reverse('reports:list')), report_url)
        for name in ('detail', 'print', 'pdf'):
            self.assertEqual(self.client.get(reverse('reports:' + name, args=[report.pk])).status_code, 403)
