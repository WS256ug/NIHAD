from datetime import date
from decimal import Decimal
from uuid import uuid4
from unittest.mock import patch
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.test import Client
from django.urls import reverse
from apps.accounts.models import User
from apps.finance.forms import PaymentForm
from apps.finance.models import FeeCharge, FeeStructure, Payment, ReceiptNumber
from apps.finance.queries import balance_summary, finance_totals, student_balances
from apps.finance.services import assign_charge, cancel_charge, record_payment, reverse_payment
from tests.test_students import StudentTestCase


class FinanceTestCase(StudentTestCase):
    def setUp(self):
        super().setUp()
        self.enrollment = self.enroll()
        self.structure = FeeStructure.objects.create(term=self.term, academic_class=self.academic_class, name='Tuition', amount=Decimal('400.30'), due_date=date(2026, 3, 1))
        self.charge = assign_charge(self.enrollment, self.structure, self.users[User.Role.BURSAR])

    def payment_data(self, **changes):
        return {'amount': Decimal('100.10'), 'date': date(2026, 3, 1), 'method': 'cash', 'reference': '', 'notes': '', 'request_key': uuid4(), **changes}

    def pay(self, **changes):
        return record_payment(self.charge, self.payment_data(**changes), self.users[User.Role.BURSAR])


class FinanceTests(FinanceTestCase):
    def test_decimal_partial_payments_and_balances_are_exact(self):
        first = self.pay(amount=Decimal('0.10'))
        second = self.pay(amount=Decimal('0.20'))
        self.assertEqual(first.new_balance, Decimal('400.20'))
        self.assertEqual(second.new_balance, Decimal('400.00'))
        self.assertEqual(balance_summary(self.student), {'charged': Decimal('400.30'), 'paid': Decimal('0.30'), 'balance': Decimal('400.00')})
        self.assertEqual(finance_totals()['balance'], Decimal('400.00'))
        self.assertEqual(student_balances().get(pk=self.student.pk).balance, Decimal('400.00'))

    def test_duplicate_submission_is_idempotent_but_changed_payload_is_rejected(self):
        data = self.payment_data()
        first = record_payment(self.charge, data, self.actor)
        second = record_payment(self.charge, data, self.actor)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(Payment.objects.count(), 1)
        with self.assertRaisesMessage(ValidationError, 'different details'):
            record_payment(self.charge, {**data, 'amount': Decimal('10')}, self.actor)
        self.assertEqual(ReceiptNumber.objects.get(pk=1).last_value, 1)

    def test_overpayment_zero_negative_future_and_missing_reference_are_rejected(self):
        for changes in ({'amount': Decimal('401')}, {'amount': Decimal('0')}, {'amount': Decimal('-1')}, {'date': date(2999, 1, 1)}, {'method': 'bank'}):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                self.pay(**changes)
        self.assertFalse(Payment.objects.exists())

    def test_reversal_restores_balance_preserves_receipt_and_is_once_only(self):
        payment = self.pay()
        snapshot = payment.receipt.copy()
        reversal = reverse_payment(payment, 'Duplicate bank entry.', self.actor)
        self.assertEqual(reversal.new_balance, Decimal('400.30'))
        payment.refresh_from_db()
        self.assertEqual(payment.receipt, snapshot)
        self.assertEqual(payment.amount, Decimal('100.10'))
        with self.assertRaises(ValidationError):
            reverse_payment(payment, 'Again', self.actor)
        payment.amount = Decimal('1')
        with self.assertRaises(ValidationError):
            payment.full_clean()

    def test_charge_cancellation_requires_payment_reversal(self):
        payment = self.pay()
        with self.assertRaisesMessage(ValidationError, 'Reverse payments'):
            cancel_charge(self.charge, 'Incorrect fee', self.actor)
        reverse_payment(payment, 'Incorrect fee', self.actor)
        cancel_charge(self.charge, 'Incorrect fee', self.actor)
        self.assertEqual(balance_summary(self.student)['balance'], Decimal('0'))
        self.assertTrue(FeeCharge.objects.filter(pk=self.charge.pk).exists())
        with self.assertRaises(ValidationError):
            self.pay()

    def test_fee_assignment_unique_context_and_history(self):
        with self.assertRaises(ValidationError):
            assign_charge(self.enrollment, self.structure, self.actor)
        self.structure.amount = Decimal('900')
        with self.assertRaises(ValidationError):
            self.structure.full_clean()
        self.school.currency_code = 'USD'
        with self.assertRaisesMessage(ValidationError, 'Currency cannot change'):
            self.school.full_clean()

    def test_receipt_audit_failure_rolls_back_payment_and_counter(self):
        with patch('apps.schools.services.LogEntry.objects.create', side_effect=RuntimeError('audit')):
            with self.assertRaises(RuntimeError):
                self.pay()
        self.assertFalse(Payment.objects.exists())
        self.assertFalse(ReceiptNumber.objects.exists())

    def test_bank_reference_unique_case_insensitive(self):
        self.pay(method='bank', reference='BANK-1')
        with self.assertRaises(ValidationError):
            self.pay(method='bank', reference='bank-1')

    def test_financial_roles_and_service_authorization(self):
        payment = self.pay()
        for role, user in self.users.items():
            self.client.force_login(user)
            allowed = role in (User.Role.SUPER_ADMIN, User.Role.SCHOOL_ADMIN, User.Role.BURSAR)
            urls = [reverse('finance:overview'), reverse('finance:structures'), reverse('finance:payments'), reverse('finance:statement', args=[self.student.pk]), reverse('finance:receipt_pdf', args=[payment.pk]), reverse('finance:payment_create', args=[self.charge.pk])]
            for url in urls:
                self.assertEqual(self.client.get(url).status_code, 200 if allowed else 403)
            if not allowed:
                with self.assertRaises(PermissionDenied):
                    record_payment(self.charge, self.payment_data(), user)

    def test_payment_form_csrf_and_receipt_http(self):
        self.client.force_login(self.users[User.Role.BURSAR])
        data = self.payment_data()
        data['confirm'] = 'on'
        response = self.client.post(reverse('finance:payment_create', args=[self.charge.pk]), data, follow=True)
        self.assertContains(response, 'Payment receipt')
        self.assertContains(response, '300.20')
        payment = Payment.objects.get()
        response = self.client.get(reverse('finance:receipt_pdf', args=[payment.pk]))
        self.assertTrue(response.content.startswith(b'%PDF'))
        self.assertIn('no-store', response['Cache-Control'])
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.actor)
        self.assertEqual(client.post(reverse('finance:payment_reverse', args=[payment.pk]), {'reason': 'bad', 'confirm': 'on'}).status_code, 403)
