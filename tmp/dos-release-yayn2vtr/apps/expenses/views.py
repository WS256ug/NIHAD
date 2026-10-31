from config.dialogs import form_redirect
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods
from apps.accounts.permissions import role_required
from apps.finance.forms import ReversalForm
from apps.finance.views import FINANCE_ROLES
from apps.schools.forms import ConfigurationStatusForm
from apps.schools.models import School
from apps.students.views import attempt, form_page
from .forms import CategoryForm, ExpenseForm, IncomeForm
from .models import Expense, ExpenseCategory, OtherIncome
from .services import financial_summary, record_cash, reverse_cash, save_category, set_category_active

KINDS = {'expenses': (Expense, ExpenseForm, 'Expenses'), 'income': (OtherIncome, IncomeForm, 'Other income'), 'categories': (ExpenseCategory, CategoryForm, 'Expense categories')}


def spec(kind):
    if kind not in KINDS:
        raise Http404
    return KINDS[kind]


@role_required(*FINANCE_ROLES)
@never_cache
@require_GET
def overview(request):
    return render(request, 'expenses/overview.html', {'summary': financial_summary(), 'school': School.objects.first()})


@role_required(*FINANCE_ROLES)
@never_cache
@require_GET
def record_list(request, kind):
    model, _, title = spec(kind)
    records = model.objects.filter(school_id=1)
    query = request.GET.get('q', '').strip()
    if query:
        records = records.filter(name__icontains=query) if kind == 'categories' else records.filter(Q(description__icontains=query) | Q(reference__icontains=query))
    if kind != 'categories':
        records = records.select_related('reversal', 'created_by')
    return render(request, 'expenses/list.html', {'kind': kind, 'title': title, 'page_obj': Paginator(records, 30).get_page(request.GET.get('page')), 'query': query})


@role_required(*FINANCE_ROLES)
@never_cache
@require_http_methods(['GET', 'POST'])
def record_form(request, kind, pk=None):
    model, form_type, title = spec(kind)
    if pk and kind != 'categories':
        raise Http404
    record = get_object_or_404(model, pk=pk, school_id=1) if pk else None
    form = form_type(request.POST if request.method == 'POST' else None, instance=record)
    if request.method == 'POST' and form.is_valid():
        if attempt(form, lambda: save_category(form, request.user) if kind == 'categories' else record_cash(form, request.user)):
            messages.success(request, 'Record saved.')
            return form_redirect(request, 'expenses:list', kind=kind)
    return form_page(request, form, title, reverse('expenses:list', args=[kind]), explanation='Financial entries are preserved. Use a reversal to correct an existing transaction.' if kind != 'categories' else '')


@role_required(*FINANCE_ROLES)
@never_cache
@require_http_methods(['GET', 'POST'])
def reverse_record(request, kind, pk):
    model, _, title = spec(kind)
    if kind == 'categories':
        raise Http404
    record = get_object_or_404(model, pk=pk, school_id=1)
    form = ReversalForm(request.POST if request.method == 'POST' else None)
    if request.method == 'POST' and form.is_valid() and attempt(form, lambda: reverse_cash(record, form.cleaned_data['reason'], request.user)):
        return form_redirect(request, 'expenses:list', kind=kind)
    return form_page(request, form, 'Reverse transaction', reverse('expenses:list', args=[kind]), explanation=str(record))


@role_required(*FINANCE_ROLES)
@never_cache
@require_http_methods(['GET', 'POST'])
def category_status(request, pk, active):
    record = get_object_or_404(ExpenseCategory, pk=pk, school_id=1)
    form = ConfigurationStatusForm(request.POST if request.method == 'POST' else None)
    if request.method == 'POST' and form.is_valid() and attempt(form, lambda: set_category_active(record, active, request.user)):
        return form_redirect(request, 'expenses:list', kind='categories')
    return form_page(request, form, 'Activate category' if active else 'Deactivate category', reverse('expenses:list', args=['categories']), explanation=str(record))
