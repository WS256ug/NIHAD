from decimal import Decimal, InvalidOperation
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from apps.schools.services import lock_school, write_record
from apps.students.models import Enrollment
from .models import ChargeCancellation, ConcessionReversal, FeeCharge, FeeConcession, FeeStructure, Payment, PaymentReversal, ReceiptNumber
from .permissions import can_manage_finance
from .queries import balance_summary, charge_balance


@transaction.atomic
def agree_fee(charge, agreed_amount, reason, actor):
    require_finance(actor)
    school = lock_school()
    charge = FeeCharge.objects.select_for_update().get(pk=charge.pk, enrollment__student__school=school)
    try:
        agreed_amount = Decimal(str(agreed_amount))
        valid = agreed_amount.is_finite() and agreed_amount >= 0 and agreed_amount < charge.amount and agreed_amount == agreed_amount.quantize(Decimal('.01'))
    except (InvalidOperation, ValueError, TypeError):
        valid = False
    if not valid:
        raise ValidationError('Enter an agreed fee from zero up to, but below, the original charge, with at most two decimal places.')
    if hasattr(charge, 'cancellation') or charge.concessions.filter(reversal__isnull=True).exists():
        raise ValidationError('Choose an active charge without an existing agreement. Reverse the previous concession before replacing it.')
    if charge.amount - agreed_amount > charge_balance(charge):
        raise ValidationError('The agreed fee cannot be less than payments already received. A credit/refund workflow is required.')
    return write_record(FeeConcession(charge=charge, amount=charge.amount-agreed_amount, reason=reason.strip()), actor, 'Approved individual fee agreement.')


@transaction.atomic
def reverse_concession(concession, reason, actor):
    require_finance(actor)
    school = lock_school()
    concession = FeeConcession.objects.select_for_update().get(pk=concession.pk, charge__enrollment__student__school=school)
    if hasattr(concession, 'reversal'):
        raise ValidationError('This concession has already been reversed.')
    return write_record(ConcessionReversal(concession=concession, reason=reason.strip()), actor, 'Reversed fee concession; original agreement preserved.')


def require_finance(actor):
    if not can_manage_finance(actor):
        raise PermissionDenied


@transaction.atomic
def save_structure(form, actor):
    require_finance(actor)
    lock_school()
    record = form.save(commit=False)
    if record.pk:
        record.is_active = FeeStructure.objects.get(pk=record.pk).is_active
    return write_record(record, actor, 'Saved fee structure.', update_fields=form._meta.fields)


@transaction.atomic
def set_structure_active(record, active, actor):
    require_finance(actor)
    lock_school()
    record = FeeStructure.objects.select_for_update().get(pk=record.pk)
    record.is_active = active
    return write_record(record, actor, 'Changed fee structure availability.', update_fields=['is_active'])


@transaction.atomic
def assign_charge(enrollment, structure, actor):
    require_finance(actor)
    school = lock_school()
    enrollment = Enrollment.objects.select_for_update().get(pk=enrollment.pk, student__school=school)
    structure = FeeStructure.objects.get(pk=structure.pk, term__academic_year__school=school)
    if FeeCharge.objects.filter(enrollment=enrollment, structure=structure).exists():
        raise ValidationError('This fee has already been assigned to this enrollment.')
    charge = FeeCharge(enrollment=enrollment, structure=structure, description=f'{structure.name} ({structure.category})', amount=structure.amount, currency=school.currency_code, due_date=structure.due_date)
    return write_record(charge, actor, 'Assigned student fee charge.')


@transaction.atomic
def assign_class_charges(structure, actor):
    require_finance(actor)
    school = lock_school()
    structure = FeeStructure.objects.select_related('term').get(pk=structure.pk, term__academic_year__school=school)
    if not structure.is_active:
        raise ValidationError('Select an active fee structure.')
    enrollments = Enrollment.objects.filter(
        student__school=school, academic_year=structure.term.academic_year, programme=Enrollment.Programme.MAIN,
        academic_class=structure.academic_class, status=Enrollment.Status.CURRENT,
        enrollment_date__lte=structure.term.end_date,
    )
    if structure.stream_id:
        enrollments = enrollments.filter(stream_id=structure.stream_id)
    enrollments = list(enrollments.select_for_update())
    if not enrollments:
        raise ValidationError('No matching current enrollments were found for this fee structure.')
    existing = set(FeeCharge.objects.filter(structure=structure).values_list('enrollment_id', flat=True))
    created = skipped = 0
    for enrollment in enrollments:
        if enrollment.pk in existing:
            skipped += 1
            continue
        assign_charge(enrollment, structure, actor)
        created += 1
    return created, skipped


@transaction.atomic
def record_payment(charge, data, actor):
    require_finance(actor)
    school = lock_school()
    charge = FeeCharge.objects.select_for_update().get(pk=charge.pk, enrollment__student__school=school)
    existing = Payment.objects.filter(request_key=data['request_key']).first()
    if existing:
        same = existing.created_by_id == actor.pk and existing.charge_id == charge.pk and all(getattr(existing, field) == data[field] for field in ('amount', 'date', 'method', 'notes'))
        if not same:
            raise ValidationError('This payment request was already used with different details. Reload the form.')
        return existing
    if hasattr(charge, 'cancellation') or data['amount'] > charge_balance(charge):
        raise ValidationError('The payment exceeds the remaining amount on this active charge.')
    balance = balance_summary(charge.enrollment.student)['balance']
    counter, _ = ReceiptNumber.objects.get_or_create(school=school)
    counter.last_value += 1
    counter.save(update_fields=['last_value'])
    receipt_number = f"REC-{data['date'].year}-{counter.last_value:06d}"
    enrollment = charge.enrollment
    snapshot = {'school': school.name, 'student': enrollment.student.full_name, 'registration_number': enrollment.student.student_id, 'class': enrollment.academic_class.name, 'stream': enrollment.stream.name if enrollment.stream_id else '', 'year': enrollment.academic_year.name, 'term': charge.structure.term.name, 'description': charge.description, 'currency': charge.currency, 'recorded_by': actor.get_full_name() or actor.username}
    record = Payment(charge=charge, **{field: data[field] for field in ('amount', 'date', 'method', 'notes', 'request_key')}, reference=f"PAY-{data['date'].year}-{counter.last_value:06d}", receipt_number=receipt_number, previous_balance=balance, new_balance=balance-data['amount'], receipt=snapshot)
    return write_record(record, actor, 'Recorded payment and issued receipt.')


@transaction.atomic
def reverse_payment(payment, reason, actor):
    require_finance(actor)
    lock_school()
    payment = Payment.objects.select_for_update().get(pk=payment.pk, charge__enrollment__student__school_id=1)
    if hasattr(payment, 'reversal'):
        raise ValidationError('This payment has already been reversed.')
    balance = balance_summary(payment.charge.enrollment.student)['balance']
    return write_record(PaymentReversal(payment=payment, reason=reason.strip(), previous_balance=balance, new_balance=balance+payment.amount), actor, 'Reversed payment without altering the original receipt.')


@transaction.atomic
def cancel_charge(charge, reason, actor):
    require_finance(actor)
    lock_school()
    charge = FeeCharge.objects.select_for_update().get(pk=charge.pk, enrollment__student__school_id=1)
    if hasattr(charge, 'cancellation'):
        raise ValidationError('This charge has already been cancelled.')
    if charge.payments.filter(reversal__isnull=True).exists():
        raise ValidationError('Reverse payments on this charge before cancelling it.')
    return write_record(ChargeCancellation(charge=charge, reason=reason.strip()), actor, 'Cancelled fee charge without deleting its history.')
