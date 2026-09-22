from decimal import Decimal
from uuid import uuid4
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models.functions import Lower, Round
from django.utils import timezone
from apps.schools.models import AuditedModel
from apps.students.models import preserve_fields

MONEY_MIN = Decimal('0.01')


class PaymentMethod(models.TextChoices):
    CASH = 'cash', 'Cash'
    BANK = 'bank', 'Bank transfer / deposit'
    MOBILE = 'mobile', 'Mobile money'
    OTHER = 'other', 'Other'


class ImmutableRecord(AuditedModel):
    class Meta:
        abstract = True

    def clean(self):
        super().clean()
        fields = [field.attname for field in self._meta.concrete_fields if field.name not in ('created_at', 'updated_at', 'created_by', 'updated_by')]
        preserve_fields(self, fields)


class FeeStructure(AuditedModel):
    term = models.ForeignKey('schools.Term', on_delete=models.PROTECT, related_name='fee_structures')
    academic_class = models.ForeignKey('schools.AcademicClass', on_delete=models.PROTECT, related_name='fee_structures')
    stream = models.ForeignKey('schools.Stream', on_delete=models.PROTECT, null=True, blank=True, related_name='fee_structures')
    name = models.CharField(max_length=100)
    category = models.CharField(max_length=80, default='General', help_text='For example, General, Day or Boarding.')
    amount = models.DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(MONEY_MIN)])
    due_date = models.DateField()
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ('-term__academic_year__start_date', 'term__start_date', 'academic_class__sort_order', 'name')
        constraints = [
            models.CheckConstraint(condition=models.Q(amount__gt=0), name='finance_structure_amount_positive'),
            models.UniqueConstraint('term', 'academic_class', 'stream', Lower('name'), Lower('category'), condition=models.Q(stream__isnull=False), name='finance_structure_stream_unique'),
            models.UniqueConstraint('term', 'academic_class', Lower('name'), Lower('category'), condition=models.Q(stream__isnull=True), name='finance_structure_class_unique'),
        ]

    def __str__(self):
        return f'{self.term} / {self.academic_class.name} / {self.name} ({self.category}) / {self.amount}'

    def clean(self):
        super().clean()
        preserve_fields(self, ('term_id', 'academic_class_id', 'stream_id'))
        if self.pk and self.charges.exists():
            preserve_fields(self, ('name', 'category', 'amount', 'due_date'))
        if not (self.term_id and self.academic_class_id):
            return
        if self.term.academic_year.school_id != self.academic_class.section.school_id or (self.stream_id and self.stream.academic_class_id != self.academic_class_id):
            raise ValidationError('Fee structure school, class and stream must match.')
        if self.is_active and (not (self.term.is_active and self.term.academic_year.is_active and self.academic_class.is_active and self.academic_class.section.is_active) or (self.stream_id and not self.stream.is_active)):
            raise ValidationError('Choose an active academic period and class.')
        if self.due_date and not self.term.start_date <= self.due_date <= self.term.end_date:
            raise ValidationError({'due_date': 'Due date must fall within the selected term.'})


class FeeCharge(ImmutableRecord):
    enrollment = models.ForeignKey('students.Enrollment', on_delete=models.PROTECT, related_name='fee_charges')
    structure = models.ForeignKey(FeeStructure, on_delete=models.PROTECT, related_name='charges')
    description = models.CharField(max_length=200)
    amount = models.DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(MONEY_MIN)])
    currency = models.CharField(max_length=3)
    due_date = models.DateField()

    class Meta:
        ordering = ('due_date', 'pk')
        constraints = [models.UniqueConstraint(fields=('enrollment', 'structure'), name='finance_charge_assignment_unique'), models.CheckConstraint(condition=models.Q(amount__gt=0), name='finance_charge_amount_positive')]

    def __str__(self):
        return f'{self.enrollment.student.student_id} / {self.description} / {self.amount}'

    def clean(self):
        super().clean()
        if self.enrollment_id and self.structure_id:
            template = self.structure
            if self.enrollment.academic_year_id != template.term.academic_year_id or self.enrollment.academic_class_id != template.academic_class_id or (template.stream_id and self.enrollment.stream_id != template.stream_id):
                raise ValidationError('The student enrollment must match the fee structure period, class and stream.')
            if self._state.adding and not template.is_active:
                raise ValidationError('Select an active fee structure.')
            if self.enrollment.enrollment_date > template.term.end_date or (self.enrollment.completion_date and self.enrollment.completion_date < template.term.start_date):
                raise ValidationError('The student must have an enrollment covering the fee term.')


class ChargeCancellation(ImmutableRecord):
    charge = models.OneToOneField(FeeCharge, on_delete=models.PROTECT, related_name='cancellation')
    reason = models.CharField(max_length=500)

    def __str__(self):
        return f'Cancelled charge {self.charge_id}'


class ReceiptNumber(models.Model):
    school = models.OneToOneField('schools.School', on_delete=models.PROTECT, primary_key=True)
    last_value = models.PositiveBigIntegerField(default=0)


class Payment(ImmutableRecord):
    charge = models.ForeignKey(FeeCharge, on_delete=models.PROTECT, related_name='payments')
    amount = models.DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(MONEY_MIN)])
    date = models.DateField(default=timezone.localdate)
    method = models.CharField(max_length=10, choices=PaymentMethod.choices)
    reference = models.CharField(max_length=100, blank=True)
    notes = models.TextField(max_length=2000, blank=True)
    receipt_number = models.CharField(max_length=30, unique=True)
    request_key = models.UUIDField(default=uuid4, unique=True, editable=False)
    previous_balance = models.DecimalField(max_digits=16, decimal_places=2)
    new_balance = models.DecimalField(max_digits=16, decimal_places=2)
    receipt = models.JSONField(default=dict)

    class Meta:
        ordering = ('-date', '-pk')
        constraints = [
            models.CheckConstraint(condition=models.Q(amount__gt=0), name='finance_payment_amount_positive'),
            models.CheckConstraint(condition=models.Q(new_balance=Round(models.F('previous_balance') - models.F('amount'), precision=2)), name='finance_payment_balance_math'),
            models.UniqueConstraint(Lower('reference'), condition=~models.Q(reference=''), name='finance_payment_reference_unique'),
        ]

    def __str__(self):
        return self.receipt_number

    def clean(self):
        super().clean()
        if self.date and self.date > timezone.localdate():
            raise ValidationError({'date': 'Payment date cannot be in the future.'})
        if all(value is not None for value in (self.previous_balance, self.amount, self.new_balance)) and self.new_balance != self.previous_balance - self.amount:
            raise ValidationError('Payment balances must agree with the recorded amount.')
        self.reference = self.reference.strip()
        if self.method in ('bank', 'mobile') and not self.reference:
            raise ValidationError({'reference': 'Enter the bank or mobile transaction reference.'})


class PaymentReversal(ImmutableRecord):
    payment = models.OneToOneField(Payment, on_delete=models.PROTECT, related_name='reversal')
    reason = models.CharField(max_length=500)
    previous_balance = models.DecimalField(max_digits=16, decimal_places=2)
    new_balance = models.DecimalField(max_digits=16, decimal_places=2)

    def __str__(self):
        return f'Reversal / {self.payment.receipt_number}'
