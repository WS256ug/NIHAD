from decimal import Decimal
from django.db.models import DecimalField, F, OuterRef, Subquery, Sum, Value
from django.db.models.functions import Coalesce
from apps.students.models import Student
from .models import FeeCharge, Payment

ZERO = Decimal('0.00')


def amount_sum(records):
    return (records.aggregate(total=Sum('amount'))['total'] or ZERO).quantize(Decimal('.01'))


def balance_summary(student):
    charges = amount_sum(FeeCharge.objects.filter(enrollment__student=student, cancellation__isnull=True))
    paid = amount_sum(Payment.objects.filter(charge__enrollment__student=student, reversal__isnull=True))
    return {'charged': charges, 'paid': paid, 'balance': charges - paid}


def charge_balance(charge):
    return charge.amount - amount_sum(charge.payments.filter(reversal__isnull=True))


def student_balances():
    money = DecimalField(max_digits=16, decimal_places=2)
    charges = FeeCharge.objects.filter(enrollment__student_id=OuterRef('pk'), cancellation__isnull=True).order_by().values('enrollment__student_id').annotate(total=Sum('amount')).values('total')
    payments = Payment.objects.filter(charge__enrollment__student_id=OuterRef('pk'), reversal__isnull=True).order_by().values('charge__enrollment__student_id').annotate(total=Sum('amount')).values('total')
    return Student.objects.filter(school_id=1).annotate(charged=Coalesce(Subquery(charges, output_field=money), Value(ZERO), output_field=money), paid=Coalesce(Subquery(payments, output_field=money), Value(ZERO), output_field=money)).annotate(balance=F('charged') - F('paid'))


def finance_totals():
    charged = amount_sum(FeeCharge.objects.filter(enrollment__student__school_id=1, cancellation__isnull=True))
    paid = amount_sum(Payment.objects.filter(charge__enrollment__student__school_id=1, reversal__isnull=True))
    return {'charged': charged, 'paid': paid, 'balance': charged - paid}
