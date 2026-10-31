from uuid import uuid4
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models.functions import Lower
from django.utils import timezone
from apps.finance.models import ImmutableRecord, MONEY_MIN, PaymentMethod
from apps.schools.models import AuditedModel
from apps.students.models import preserve_fields


class ExpenseCategory(AuditedModel):
    school = models.ForeignKey('schools.School', on_delete=models.PROTECT, related_name='expense_categories')
    name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ('name', 'pk')
        constraints = [models.UniqueConstraint(Lower('name'), 'school', name='expenses_category_name_unique')]

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        preserve_fields(self, ('school_id',))
        self.name = self.name.strip()
        if not self.name:
            raise ValidationError({'name': 'Enter a category name.'})


class CashRecord(ImmutableRecord):
    school = models.ForeignKey('schools.School', on_delete=models.PROTECT, related_name='%(class)s_records')
    description = models.CharField(max_length=200)
    amount = models.DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(MONEY_MIN)])
    currency = models.CharField(max_length=3, editable=False)
    date = models.DateField(default=timezone.localdate)
    method = models.CharField(max_length=10, choices=PaymentMethod.choices)
    reference = models.CharField(max_length=100, blank=True)
    request_key = models.UUIDField(default=uuid4, unique=True, editable=False)

    class Meta:
        abstract = True
        ordering = ('-date', '-pk')
        constraints = [models.CheckConstraint(condition=models.Q(amount__gt=0), name='%(app_label)s_%(class)s_positive'), models.UniqueConstraint(Lower('reference'), 'school', condition=~models.Q(reference=''), name='%(app_label)s_%(class)s_reference')]

    def __str__(self):
        return f'{self.description} / {self.currency} {self.amount}'

    def clean(self):
        super().clean()
        if self.date and self.date > timezone.localdate():
            raise ValidationError({'date': 'Transaction date cannot be in the future.'})
        if self.method in ('bank', 'mobile') and not self.reference.strip():
            raise ValidationError({'reference': 'Enter a bank or mobile transaction reference.'})


class Expense(CashRecord):
    category = models.ForeignKey(ExpenseCategory, on_delete=models.PROTECT, related_name='expenses')
    category_name = models.CharField(max_length=100, editable=False)

    def clean(self):
        super().clean()
        if self.category_id and (self.category.school_id != self.school_id or (self._state.adding and not self.category.is_active)):
            raise ValidationError('Select an active expense category from this school.')


class OtherIncome(CashRecord):
    source = models.CharField(max_length=100)


class ExpenseReversal(ImmutableRecord):
    expense = models.OneToOneField(Expense, on_delete=models.PROTECT, related_name='reversal')
    reason = models.CharField(max_length=500)

    def __str__(self):
        return f'Expense reversal {self.expense_id}'


class IncomeReversal(ImmutableRecord):
    income = models.OneToOneField(OtherIncome, on_delete=models.PROTECT, related_name='reversal')
    reason = models.CharField(max_length=500)

    def __str__(self):
        return f'Income reversal {self.income_id}'
