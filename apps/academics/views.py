from config.dialogs import form_redirect
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods
from apps.accounts.models import User
from apps.accounts.permissions import has_role, role_required
from apps.schools.forms import ConfigurationStatusForm
from apps.schools.models import School
from apps.students.views import attempt, form_page
from .catalog import RESOURCES
from .permissions import can_manage_academics, teacher_assignments, visible_assessments
from .services import save_academic, set_academic_active
from .section_grades import current_rules, save_section_rule


def resource(kind):
    if kind not in RESOURCES:
        raise Http404
    return RESOURCES[kind]


def scoped_records(spec, user):
    records = spec.model.objects.filter(**{spec.scope + "_id": 1}).select_related(*spec.related)
    if spec.model._meta.model_name in ("graderule", "divisionrule"):
        records = current_rules(records)
    if has_role(user, User.Role.SCHOOL_ADMIN, User.Role.HEADTEACHER):
        return records
    if spec.model._meta.model_name == "assessment":
        return visible_assessments(user)
    if spec.model._meta.model_name == "assessmenttype":
        return records.filter(is_active=True)
    if spec.model._meta.model_name in ("gradingscheme", "graderule", "divisionrule"):
        return records
    if spec.model._meta.model_name == "teacher":
        return records.filter(user=user)
    if spec.model._meta.model_name == "subject":
        return records.filter(pk__in=teacher_assignments(user).values("subject_id"))
    return records.filter(teacher__user=user, is_active=True)


@role_required(User.Role.SCHOOL_ADMIN, User.Role.HEADTEACHER, User.Role.TEACHER)
@never_cache
@require_GET
def overview(request):
    return render(request, "academics/overview.html", {"resources": RESOURCES, "can_manage_academics": can_manage_academics(request.user)})


@role_required(User.Role.SCHOOL_ADMIN, User.Role.HEADTEACHER, User.Role.TEACHER)
@never_cache
@require_GET
def record_list(request, kind):
    if kind == "grading-schemes":
        return redirect("academics:record_list", kind="grade-rules")
    spec = resource(kind)
    records = scoped_records(spec, request.user)
    query = request.GET.get("q", "").strip()
    for token in query.split()[:10]:
        search = Q()
        for field in spec.search:
            search |= Q(**{field + "__icontains": token})
        records = records.filter(search)
    status = request.GET.get("status", "")
    if spec.status and status in ("active", "inactive"):
        records = records.filter(is_active=status == "active")
    grades = kind in ("grade-rules", "division-rules")
    return render(request, "academics/grades.html" if grades else "academics/record_list.html", {"spec": spec, "kind": kind, "query": query, "selected_status": status, "page_obj": Paginator(records, 20).get_page(request.GET.get("page")), "can_manage_academics": can_manage_academics(request.user)})


@role_required(User.Role.SCHOOL_ADMIN)
@never_cache
@require_http_methods(["GET", "POST"])
def record_form(request, kind, pk=None):
    if kind == "grading-schemes":
        return redirect("academics:record_list", kind="grade-rules")
    spec = resource(kind)
    school = School.objects.first()
    if school is None:
        return redirect("schools:profile")
    record = get_object_or_404(scoped_records(spec, request.user), pk=pk) if pk else None
    form = spec.form(request.POST if request.method == "POST" else None, instance=record, school=school, actor=request.user)
    if request.method == "POST" and form.is_valid():
        save = save_section_rule if kind in ("grade-rules", "division-rules") else save_academic
        if attempt(form, lambda: save(form, request.user)):
            messages.success(request, "Academic record saved.")
            return form_redirect(request, "academics:record_list", kind=kind)
    explanations = {
        "teachers": "Create the Teacher account in Accounts first, then select it here.",
        "assessment-types": "Define the school's assessment types, such as Mid-Term and End-Term.",
        "assessments": "Create the assessment, then open it for marks from its marks page.",
        "subjects": "Subjects and learning areas belong to a section.",
        "grade-rules": "Choose a section and add its grade. Numeric ranges must cover 0–100 with no gaps or overlaps. For descriptive learning levels, leave percentages and points blank. Existing assessments keep their original grades.",
        "division-rules": "Choose a section and the aggregate range for this division. Both endpoints are included. Add points to every grade first; new sections use the total points from all subjects.",
    }
    explanation = explanations.get(kind, "Assignments keep their original academic context. Deactivate an old assignment before replacing it.")
    return form_page(request, form, f"{'Edit' if pk else 'Create'} {spec.singular}", reverse("academics:record_list", args=[kind]), explanation=explanation if kind != "subjects" else None)


@role_required(User.Role.SCHOOL_ADMIN)
@never_cache
@require_http_methods(["GET", "POST"])
def record_status(request, kind, pk, active):
    spec = resource(kind)
    if not spec.status:
        raise Http404
    record = get_object_or_404(scoped_records(spec, request.user), pk=pk)
    form = ConfigurationStatusForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        if attempt(form, lambda: set_academic_active(record, active, request.user)):
            messages.success(request, "Academic record activated." if active else "Academic record deactivated.")
            return form_redirect(request, "academics:record_list", kind=kind)
    return form_page(request, form, f"{'Activate' if active else 'Deactivate'} {record}", reverse("academics:record_list", args=[kind]))
