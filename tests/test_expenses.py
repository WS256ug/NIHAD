from decimal import Decimal
from uuid import uuid4
from unittest.mock import patch
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import Client
from django.urls import reverse
from apps.accounts.models import User
from apps.expenses.forms import ExpenseForm, IncomeForm
from apps.expenses.models import Expense, ExpenseCategory
from apps.expenses.services import financial_summary, record_cash, reverse_cash, set_category_active
from tests.test_finance import FinanceTestCase


class ExpenseTests(FinanceTestCase):
    def setUp(self):
        super().setUp()
        self.category = ExpenseCategory.objects.create(school=self.school, name='Stationery')

    def data(self, **changes):
        return {'category': self.category.pk, 'description': 'Exercise books', 'amount': '20.15', 'date': '2026-03-01', 'method': 'cash', 'reference': '', 'request_key': uuid4(), 'confirm': 'on', **changes}

    def expense(self):
        form = ExpenseForm(self.data())
        self.assertTrue(form.is_valid(), form.errors)
        return record_cash(form, self.users[User.Role.BURSAR])

    def test_financial_summary_and_reversals_use_exact_decimal(self):
        self.pay()
        expense = self.expense()
        form = IncomeForm(self.data(source='School donation', amount='10.05'))
        self.assertTrue(form.is_valid(), form.errors)
        income = record_cash(form, self.actor)
        summary = financial_summary()
        self.assertEqual(summary['total_income'], Decimal('110.15'))
        self.assertEqual(summary['net'], Decimal('90.00'))
        reverse_cash(expense, 'Refunded', self.actor)
        self.assertEqual(financial_summary()['net'], Decimal('110.15'))
        reverse_cash(income, 'Returned donation', self.actor)
        self.assertEqual(financial_summary()['net'], Decimal('100.10'))

    def test_duplicate_submission_is_idempotent_and_entries_are_immutable(self):
        data = self.data()
        form = ExpenseForm(data)
        self.assertTrue(form.is_valid(), form.errors)
        first = record_cash(form, self.actor)
        second_form = ExpenseForm(data)
        self.assertTrue(second_form.is_valid(), second_form.errors)
        self.assertEqual(record_cash(second_form, self.actor).pk, first.pk)
        first.amount = Decimal('50')
        with self.assertRaises(ValidationError):
            first.full_clean()
        self.assertEqual(Expense.objects.count(), 1)

    def test_inactive_category_and_invalid_values_are_rejected(self):
        for values in ({'amount': '-1'}, {'amount': '0'}, {'date': '2999-01-01'}, {'method': 'bank'}):
            self.assertFalse(ExpenseForm(self.data(**values)).is_valid())
        set_category_active(self.category, False, self.actor)
        self.assertFalse(ExpenseForm(self.data()).is_valid())

    def test_history_keeps_category_name_and_audit_failure_rolls_back(self):
        expense = self.expense()
        self.category.name = 'Books'
        self.category.save()
        expense.refresh_from_db()
        self.assertEqual(expense.category_name, 'Stationery')
        form = ExpenseForm(self.data())
        self.assertTrue(form.is_valid(), form.errors)
        with patch('apps.schools.services.LogEntry.objects.create', side_effect=RuntimeError('audit')):
            with self.assertRaises(RuntimeError):
                record_cash(form, self.actor)
        self.assertEqual(Expense.objects.count(), 1)

    def test_roles_ui_csrf_and_unauthorized_service(self):
        for role, user in self.users.items():
            self.client.force_login(user)
            allowed = role in (User.Role.SUPER_ADMIN, User.Role.SCHOOL_ADMIN, User.Role.BURSAR)
            for url in (reverse('expenses:overview'), reverse('expenses:list', args=['expenses']), reverse('expenses:create', args=['expenses']), reverse('expenses:create', args=['income']), reverse('expenses:create', args=['categories'])):
                self.assertEqual(self.client.get(url).status_code, 200 if allowed else 403)
            if not allowed:
                form = ExpenseForm(self.data())
                self.assertTrue(form.is_valid())
                with self.assertRaises(PermissionDenied):
                    record_cash(form, user)
        self.client.force_login(self.actor)
        self.assertContains(self.client.post(reverse('expenses:create', args=['expenses']), self.data(), follow=True), 'Exercise books')
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.actor)
        self.assertEqual(client.post(reverse('expenses:create', args=['expenses']), self.data()).status_code, 403)
