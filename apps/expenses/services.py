from django.core.exceptions import ValidationError
from django.db import transaction
from apps.finance.queries import amount_sum, finance_totals
from apps.finance.services import require_finance
from apps.schools.services import lock_school, write_record
from .models import Expense, ExpenseCategory, ExpenseReversal, IncomeReversal, OtherIncome


@transaction.atomic
def save_category(form, actor):
    require_finance(actor)
    school = lock_school()
    record = form.save(commit=False)
    record.school = school
    if record.pk:
        record.is_active = ExpenseCategory.objects.get(pk=record.pk).is_active
    return write_record(record, actor, 'Saved expense category.', update_fields=['name'])


@transaction.atomic
def set_category_active(category, active, actor):
    require_finance(actor)
    lock_school()
    category = ExpenseCategory.objects.select_for_update().get(pk=category.pk, school_id=1)
    category.is_active = active
    return write_record(category, actor, 'Changed expense category availability.', update_fields=['is_active'])


@transaction.atomic
def record_cash(form, actor):
    require_finance(actor)
    school = lock_school()
    record = form.save(commit=False)
    if type(record) not in (Expense, OtherIncome):
        raise ValidationError('Unknown cash record.')
    record.school = school
    record.currency = school.currency_code
    record.request_key = form.cleaned_data['request_key']
    previous = type(record).objects.filter(request_key=record.request_key).first()
    if previous:
        fields = [record._meta.get_field(name).attname for name in form._meta.fields]
        if previous.created_by_id == actor.pk and all(getattr(previous, field) == getattr(record, field) for field in fields):
            return previous
        raise ValidationError('This request was already used with different details. Reload the form.')
    if isinstance(record, Expense):
        record.category_name = ExpenseCategory.objects.get(pk=record.category_id).name
    return write_record(record, actor, 'Recorded school expense.' if isinstance(record, Expense) else 'Recorded other school income.')


@transaction.atomic
def reverse_cash(record, reason, actor):
    require_finance(actor)
    lock_school()
    if type(record) not in (Expense, OtherIncome):
        raise ValidationError('Unknown cash record.')
    record = type(record).objects.select_for_update().get(pk=record.pk, school_id=1)
    if hasattr(record, 'reversal'):
        raise ValidationError('This transaction has already been reversed.')
    reversal = ExpenseReversal(expense=record, reason=reason.strip()) if isinstance(record, Expense) else IncomeReversal(income=record, reason=reason.strip())
    return write_record(reversal, actor, 'Reversed cash record; original history preserved.')


def financial_summary():
    fees = finance_totals()
    income = amount_sum(OtherIncome.objects.filter(school_id=1, reversal__isnull=True))
    expenses = amount_sum(Expense.objects.filter(school_id=1, reversal__isnull=True))
    return {**fees, 'other_income': income, 'expenses': expenses, 'total_income': fees['paid'] + income, 'net': fees['paid'] + income - expenses}
