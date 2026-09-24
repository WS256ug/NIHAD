from config.dialogs import form_redirect
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import IntegrityError, OperationalError
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods

from apps.accounts.models import User
from apps.accounts.permissions import role_required

from .catalog import CONFIGURATION_TYPES
from .forms import ConfigurationStatusForm, CurrentPeriodForm, SchoolForm
from .models import School
from .services import save_configuration, set_current_period, set_record_active


def get_configuration_type(kind):
    try:
        return CONFIGURATION_TYPES[kind]
    except KeyError:
        raise Http404 from None


def save_or_show_errors(form, operation):
    """Keep submitted data on validation failures or concurrent edits."""
    try:
        operation()
    except ValidationError as error:
        form.add_error(None, error.messages)
    except (IntegrityError, OperationalError):
        form.add_error(None, "The configuration changed or is busy. Reload the page and try again.")
    else:
        return True
    return False


@role_required(User.Role.SCHOOL_ADMIN)
@never_cache
@require_GET
def overview(request):
    school = School.objects.select_related("current_academic_year", "current_term").first()
    cards = [
        {"label": spec.label, "url": reverse("schools:record_list", args=[kind]), "count": spec.queryset(school).count() if school else 0}
        for kind, spec in CONFIGURATION_TYPES.items()
    ]
    return render(request, "schools/overview.html", {"school": school, "cards": cards})


@role_required(User.Role.SCHOOL_ADMIN)
@never_cache
@require_http_methods(["GET", "POST"])
def profile(request):
    school = School.objects.first()
    form = SchoolForm(request.POST if request.method == "POST" else None, instance=school)
    if request.method == "POST" and form.is_valid():
        if save_or_show_errors(form, lambda: save_configuration(form, request.user)):
            messages.success(request, "School profile saved.")
            return form_redirect(request, "schools:overview")
    return render(request, "schools/form.html", {"form": form, "page_title": "School profile", "cancel_url": reverse("schools:overview")})


@role_required(User.Role.SCHOOL_ADMIN)
@never_cache
@require_GET
def record_list(request, kind):
    spec = get_configuration_type(kind)
    school = School.objects.first()
    if school is None:
        return redirect("schools:profile")
    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "")
    records = spec.queryset(school)
    if query:
        records = records.filter(name__icontains=query)
    if status in ("active", "inactive"):
        records = records.filter(is_active=status == "active")
    page = Paginator(records, 20).get_page(request.GET.get("page"))
    rows = []
    for record in page:
        current = (kind == "years" and record.pk == school.current_academic_year_id) or (kind == "terms" and record.pk == school.current_term_id)
        rows.append({"record": record, "parent": getattr(record, spec.parent) if spec.parent else school.name, "current": current})
    return render(request, "schools/record_list.html", {
        "kind": kind, "spec": spec, "rows": rows, "page_obj": page,
        "query": query, "selected_status": status,
    })


@role_required(User.Role.SCHOOL_ADMIN)
@never_cache
@require_http_methods(["GET", "POST"])
def record_form(request, kind, pk=None):
    dialog = request.headers.get("HX-Request") == "true" and request.headers.get("HX-Target") == "configuration-dialog-content"
    spec = get_configuration_type(kind)
    school = School.objects.first()
    if school is None:
        return redirect("schools:profile")
    record = get_object_or_404(spec.queryset(school), pk=pk) if pk is not None else None
    form = spec.form(request.POST if request.method == "POST" else None, school=school, instance=record)
    if request.method == "POST" and form.is_valid():
        if save_or_show_errors(form, lambda: save_configuration(form, request.user)):
            if dialog:
                return HttpResponse(status=204, headers={"HX-Trigger": "configurationSaved"})
            messages.success(request, "Configuration saved.")
            return form_redirect(request, "schools:record_list", kind=kind)
    return render(request, "schools/dialog_form.html" if dialog else "schools/form.html", {
        "form": form, "page_title": f"{'Edit' if pk is not None else 'Create'} {spec.singular}",
        "cancel_url": reverse("schools:record_list", args=[kind]),
    })


@role_required(User.Role.SCHOOL_ADMIN)
@never_cache
@require_http_methods(["GET", "POST"])
def record_status(request, kind, pk, activate):
    spec = get_configuration_type(kind)
    school = get_object_or_404(School, pk=1)
    record = get_object_or_404(spec.queryset(school), pk=pk)
    form = ConfigurationStatusForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        if save_or_show_errors(form, lambda: set_record_active(record, activate, request.user)):
            messages.success(request, "Configuration activated." if activate else "Configuration deactivated.")
            return form_redirect(request, "schools:record_list", kind=kind)
    return render(request, "schools/status.html", {"form": form, "record": record, "kind": kind, "activate": activate})


@role_required(User.Role.SCHOOL_ADMIN)
@never_cache
@require_http_methods(["GET", "POST"])
def current_period(request):
    school = School.objects.first()
    if school is None:
        return redirect("schools:profile")
    form = CurrentPeriodForm(request.POST if request.method == "POST" else None, school=school)
    form.fields["academic_year"].widget.attrs.update({
        "hx-get": reverse("schools:term_options"), "hx-target": "#id_term",
        "hx-swap": "innerHTML", "hx-indicator": "#term-loading", "hx-disabled-elt": "#id_term",
    })
    if request.method == "POST" and form.is_valid():
        if save_or_show_errors(form, lambda: set_current_period(request.user, form.cleaned_data["academic_year"], form.cleaned_data["term"])):
            messages.success(request, "Current academic period updated.")
            return form_redirect(request, "schools:overview")
    return render(request, "schools/current_period.html", {"form": form})


@role_required(User.Role.SCHOOL_ADMIN)
@never_cache
@require_GET
def term_options(request):
    school = get_object_or_404(School, pk=1)
    form = CurrentPeriodForm(request.GET, school=school)
    return render(request, "schools/term_options.html", {"terms": form.fields["term"].queryset})
