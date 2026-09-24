from config.dialogs import form_redirect, is_dialog_request
from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods
from apps.accounts.models import User
from apps.accounts.permissions import role_required
from apps.students.views import attempt, form_page
from .forms import BatchForm, ConfirmBatchForm, DecisionForms, RevisionForm
from .models import PromotionBatch
from .services import confirm_batch, create_batch, eligible_enrollments, save_decisions

ROLES = (User.Role.SCHOOL_ADMIN, User.Role.HEADTEACHER)


def batches():
    return PromotionBatch.objects.filter(source_year__school_id=1).select_related('source_year', 'source_class', 'source_stream', 'destination_year', 'destination_class', 'destination_stream')


@role_required(*ROLES)
@never_cache
@require_GET
def batch_list(request):
    return render(request, 'promotions/list.html', {'page_obj': Paginator(batches(), 30).get_page(request.GET.get('page'))})


@role_required(*ROLES)
@never_cache
@require_http_methods(['GET', 'POST'])
def batch_create(request):
    dialog = is_dialog_request(request) or (request.headers.get('HX-Request') == 'true' and request.GET.get('dialog') == '1')
    form = BatchForm(request.POST if request.method == 'POST' else None, initial=request.GET.dict() if request.method == 'GET' else None, dialog=dialog)
    if request.method == 'POST' and form.is_valid():
        batch = attempt(form, lambda: create_batch(form, request.user))
        if batch:
            return form_redirect(request, 'promotions:edit', pk=batch.pk)
    return form_page(request, form, 'Create promotion batch', reverse('promotions:list'), form_id='promotion-batch-form', is_form_dialog=dialog, form_base_template='includes/dialog_base.html' if dialog else 'base.html', explanation='Choose the source class and year. Set a later destination year for promotion or repetition. Transfer, withdrawal and graduation close the source enrollment without creating a new one.')


@role_required(*ROLES)
@never_cache
@require_http_methods(['GET', 'POST'])
def batch_edit(request, pk):
    batch = get_object_or_404(batches(), pk=pk)
    if batch.status == 'confirmed':
        return form_redirect(request, 'promotions:preview', pk=pk)
    enrollments = eligible_enrollments(batch).order_by('student__last_name', 'student__first_name', 'pk')
    existing = {decision.enrollment_id: decision for decision in batch.decisions.all()}
    initial = [{'enrollment': enrollment.pk, 'selected': existing[enrollment.pk].selected if enrollment.pk in existing else False, 'decision': existing[enrollment.pk].decision if enrollment.pk in existing else 'promoted', 'notes': existing[enrollment.pk].notes if enrollment.pk in existing else ''} for enrollment in enrollments]
    formset = DecisionForms(request.POST if request.method == 'POST' else None, initial=initial, form_kwargs={'enrollments': enrollments})
    revision_form = RevisionForm(request.POST if request.method == 'POST' else None, initial={'revision': batch.revision})
    if request.method == 'POST' and formset.is_valid() and revision_form.is_valid():
        if attempt(revision_form, lambda: save_decisions(batch, [form.cleaned_data for form in formset if form.cleaned_data], revision_form.cleaned_data['revision'], request.user)):
            return form_redirect(request, 'promotions:preview', pk=pk)
    by_pk = {str(enrollment.pk): enrollment for enrollment in enrollments}
    rows = [{'form': form, 'enrollment': by_pk.get(str(form['enrollment'].value()))} for form in formset]
    return render(request, 'promotions/edit.html', {'batch': batch, 'formset': formset, 'rows': rows, 'revision_form': revision_form})


@role_required(*ROLES)
@never_cache
@require_http_methods(['GET', 'POST'])
def preview(request, pk):
    batch = get_object_or_404(batches(), pk=pk)
    decisions = batch.decisions.filter(selected=True).select_related('enrollment__student', 'enrollment__academic_class', 'enrollment__stream', 'new_enrollment__academic_class')
    form = ConfirmBatchForm(request.POST if request.method == 'POST' else None, initial={'revision': batch.revision})
    if request.method == 'POST' and form.is_valid() and attempt(form, lambda: confirm_batch(batch, form.cleaned_data['revision'], request.user)):
        messages.success(request, 'Promotion batch confirmed. Previous enrollment history is preserved.')
        return form_redirect(request, 'promotions:preview', pk=pk)
    return render(request, 'promotions/preview.html', {'batch': batch, 'decisions': decisions, 'form': form})
