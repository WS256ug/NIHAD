from config.dialogs import form_redirect
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods
from apps.accounts.models import User
from apps.accounts.permissions import role_required
from apps.reports.pdf import document_pdf
from apps.schools.forms import ConfigurationStatusForm
from apps.schools.models import School
from apps.students.models import Student
from apps.students.views import attempt, form_page
from . import services
from .forms import ChargeForm, FeeStructureForm, PaymentForm, ReversalForm
from .models import FeeCharge, FeeStructure, Payment
from .queries import balance_summary, charge_balance, finance_totals, student_balances

FINANCE_ROLES = (User.Role.SCHOOL_ADMIN, User.Role.BURSAR)


def scoped_charges():
    return FeeCharge.objects.filter(enrollment__student__school_id=1).select_related('enrollment__student', 'enrollment__academic_class', 'structure__term__academic_year', 'cancellation')


def scoped_payments():
    return Payment.objects.filter(charge__enrollment__student__school_id=1).select_related('charge__enrollment__student', 'reversal')


def statement_context(student):
    charges = scoped_charges().filter(enrollment__student=student)
    payments = scoped_payments().filter(charge__enrollment__student=student)
    return {'student': student, 'summary': balance_summary(student), 'charges': charges, 'payments': payments, 'school': student.school}


@role_required(*FINANCE_ROLES)
@never_cache
@require_GET
def overview(request):
    records = student_balances()
    query = request.GET.get('q', '').strip()
    for token in query.split()[:10]:
        records = records.filter(Q(student_id__icontains=token) | Q(first_name__icontains=token) | Q(last_name__icontains=token))
    outstanding = request.GET.get('outstanding') == '1'
    if outstanding:
        records = records.filter(balance__gt=0)
    return render(request, 'finance/overview.html', {'summary': finance_totals(), 'page_obj': Paginator(records, 30).get_page(request.GET.get('page')), 'query': query, 'outstanding': outstanding, 'school': School.objects.first()})


@role_required(*FINANCE_ROLES)
@never_cache
@require_GET
def structure_list(request):
    records = FeeStructure.objects.filter(term__academic_year__school_id=1).select_related('term__academic_year', 'academic_class')
    return render(request, 'finance/structures.html', {'page_obj': Paginator(records, 30).get_page(request.GET.get('page'))})


@role_required(*FINANCE_ROLES)
@never_cache
@require_http_methods(['GET', 'POST'])
def structure_form(request, pk=None):
    record = get_object_or_404(FeeStructure, pk=pk, term__academic_year__school_id=1) if pk else None
    form = FeeStructureForm(request.POST if request.method == 'POST' else None, instance=record)
    if request.method == 'POST' and form.is_valid() and attempt(form, lambda: services.save_structure(form, request.user)):
        messages.success(request, 'Fee structure saved.')
        return form_redirect(request, 'finance:structures')
    return form_page(request, form, 'Edit fee structure' if pk else 'Create fee structure', reverse('finance:structures'), explanation='Once assigned to students, the amount and description are preserved. Create a new structure for different fees.')


@role_required(*FINANCE_ROLES)
@never_cache
@require_http_methods(['GET', 'POST'])
def structure_status(request, pk, active):
    record = get_object_or_404(FeeStructure, pk=pk, term__academic_year__school_id=1)
    form = ConfigurationStatusForm(request.POST if request.method == 'POST' else None)
    if request.method == 'POST' and form.is_valid() and attempt(form, lambda: services.set_structure_active(record, active, request.user)):
        return form_redirect(request, 'finance:structures')
    return form_page(request, form, 'Activate fee structure' if active else 'Deactivate fee structure', reverse('finance:structures'), explanation=str(record))


@role_required(*FINANCE_ROLES)
@never_cache
@require_http_methods(['GET', 'POST'])
def charge_form(request):
    form = ChargeForm(request.POST if request.method == 'POST' else None)
    if request.method == 'POST' and form.is_valid():
        charge = attempt(form, lambda: services.assign_charge(form.cleaned_data['enrollment'], form.cleaned_data['structure'], request.user))
        if charge:
            messages.success(request, 'Student fees assigned.')
            return form_redirect(request, 'finance:statement', pk=charge.enrollment.student_id)
    return form_page(request, form, 'Assign student fees', reverse('finance:overview'))


@role_required(*FINANCE_ROLES)
@never_cache
@require_GET
def statement(request, pk, output='html'):
    student = get_object_or_404(Student.objects.select_related('school'), pk=pk, school_id=1)
    context = statement_context(student)
    if output == 'pdf':
        rows = [[charge.description, charge.due_date.isoformat(), str(charge.amount), 'Cancelled' if hasattr(charge, 'cancellation') else 'Charged'] for charge in context['charges']]
        rows += [[payment.receipt_number, payment.date.isoformat(), str(payment.amount), 'Reversed' if hasattr(payment, 'reversal') else 'Paid'] for payment in context['payments']]
        response = HttpResponse(document_pdf(student.school.name, f'{student.full_name} / {student.student_id} / Fee statement ({student.school.currency_code})', ['Record', 'Date', 'Amount', 'Status'], rows, [('Account totals', f"Charged: {context['summary']['charged']} · Paid: {context['summary']['paid']} · Balance: {context['summary']['balance']}")]), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="statement-{student.student_id}.pdf"'
        return response
    context['can_manage_finance'] = True
    return render(request, 'finance/statement.html', context)


@role_required(*FINANCE_ROLES)
@never_cache
@require_http_methods(['GET', 'POST'])
def payment_form(request, pk):
    charge = get_object_or_404(scoped_charges(), pk=pk)
    form = PaymentForm(request.POST if request.method == 'POST' else None, initial={'amount': charge_balance(charge)})
    if request.method == 'POST' and form.is_valid():
        payment = attempt(form, lambda: services.record_payment(charge, form.cleaned_data, request.user))
        if payment:
            messages.success(request, 'Payment recorded and receipt issued.')
            return form_redirect(request, 'finance:receipt', pk=payment.pk)
    return form_page(request, form, 'Record payment', reverse('finance:statement', args=[charge.enrollment.student_id]), explanation=f'{charge.enrollment.student.full_name} / {charge.description}. Remaining on this charge: {charge.currency} {charge_balance(charge)}.')


@role_required(*FINANCE_ROLES)
@never_cache
@require_GET
def payment_list(request):
    records = scoped_payments()
    query = request.GET.get('q', '').strip()
    if query:
        records = records.filter(Q(receipt_number__icontains=query) | Q(reference__icontains=query) | Q(charge__enrollment__student__student_id__icontains=query))
    return render(request, 'finance/payments.html', {'page_obj': Paginator(records, 30).get_page(request.GET.get('page')), 'query': query})


def receipt_response(request, payment, output='html', can_manage=False):
    if output == 'pdf':
        data = payment.receipt
        details = [('Student', f"{data['student']} / {data['registration_number']} / {data['class']} {data['stream']}"), ('Period and fee', f"{data['year']} / {data['term']} / {data['description']}"), ('Balance', f'Previous balance: {payment.previous_balance} · New balance: {payment.new_balance}'), ('Recorded by', data['recorded_by'])]
        if hasattr(payment, 'reversal'):
            details.append(('REVERSED', payment.reversal.reason))
        response = HttpResponse(document_pdf(data['school'], f"Receipt {payment.receipt_number} / {data['currency']}", ['Date', 'Method', 'Reference', 'Amount'], [[payment.date, payment.get_method_display(), payment.reference, payment.amount]], details), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{payment.receipt_number}.pdf"'
        return response
    return render(request, 'finance/receipt.html', {'payment': payment, 'data': payment.receipt, 'can_manage_finance': can_manage, 'print_view': output == 'print'})


@role_required(*FINANCE_ROLES)
@never_cache
@require_GET
def receipt(request, pk, output='html'):
    return receipt_response(request, get_object_or_404(scoped_payments(), pk=pk), output, True)


@role_required(*FINANCE_ROLES)
@never_cache
@require_http_methods(['GET', 'POST'])
def reverse_record(request, pk, kind):
    record = get_object_or_404(scoped_payments() if kind == 'payment' else scoped_charges(), pk=pk)
    student = record.charge.enrollment.student if kind == 'payment' else record.enrollment.student
    form = ReversalForm(request.POST if request.method == 'POST' else None)
    if request.method == 'POST' and form.is_valid():
        service = services.reverse_payment if kind == 'payment' else services.cancel_charge
        if attempt(form, lambda: service(record, form.cleaned_data['reason'], request.user)):
            messages.success(request, 'Reversal recorded. Original history is preserved.')
            return form_redirect(request, 'finance:statement', pk=student.pk)
    return form_page(request, form, 'Reverse payment' if kind == 'payment' else 'Cancel fee charge', reverse('finance:statement', args=[student.pk]), explanation=str(record))
