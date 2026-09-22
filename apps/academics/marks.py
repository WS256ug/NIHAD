from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods
from apps.accounts.models import User
from apps.accounts.permissions import has_role, role_required
from apps.schools.forms import ConfigurationStatusForm
from apps.students.forms import selected_pk
from apps.students.views import attempt, form_page
from .forms import MarkForm
from .models import ClassTeacherAssignment, Mark, Subject
from .permissions import assessment_assignments, assessment_enrollments, can_manage_academics, mark_assignment, visible_assessments
from .services import save_mark, set_assessment_status


def available_subjects(assessment, actor):
    subjects = Subject.objects.filter(section_id=assessment.academic_class.section_id)
    if has_role(actor, User.Role.SCHOOL_ADMIN, User.Role.HEADTEACHER) or assessment_assignments(assessment, actor, ClassTeacherAssignment).exists():
        return subjects
    return subjects.filter(pk__in=assessment_assignments(assessment, actor).values("subject_id"))


@role_required(User.Role.SCHOOL_ADMIN, User.Role.HEADTEACHER, User.Role.TEACHER)
@never_cache
@require_GET
def roster(request, pk):
    assessment = get_object_or_404(visible_assessments(request.user), pk=pk)
    subjects = available_subjects(assessment, request.user)
    selected = selected_pk(request.GET.get("subject"))
    subject = get_object_or_404(subjects, pk=selected) if request.GET.get("subject") else subjects.first()
    enrollments = assessment_enrollments(assessment, request.user, subject)
    page = Paginator(enrollments, 30).get_page(request.GET.get("page"))
    marks = {mark.enrollment_id: mark for mark in Mark.objects.filter(assessment=assessment, subject=subject, enrollment__in=page.object_list)} if subject else {}
    rows = [{"enrollment": enrollment, "mark": marks.get(enrollment.pk), "can_edit": assessment.status == "open" and subject and mark_assignment(assessment, enrollment, subject, request.user) is not None} for enrollment in page]
    return render(request, "academics/marks.html", {"assessment": assessment, "subjects": subjects, "subject": subject, "rows": rows, "page_obj": page, "can_manage_academics": can_manage_academics(request.user)})


@role_required(User.Role.SCHOOL_ADMIN, User.Role.TEACHER)
@never_cache
@require_http_methods(["GET", "POST"])
def mark_form(request, pk, subject_pk, enrollment_pk):
    assessment = get_object_or_404(visible_assessments(request.user), pk=pk)
    subject = get_object_or_404(available_subjects(assessment, request.user), pk=subject_pk)
    enrollment = get_object_or_404(assessment_enrollments(assessment, request.user, subject), pk=enrollment_pk)
    assignment = mark_assignment(assessment, enrollment, subject, request.user)
    if assignment is None:
        raise PermissionDenied
    mark = Mark.objects.filter(assessment=assessment, subject=subject, enrollment=enrollment).first()
    form = MarkForm(request.POST if request.method == "POST" else None, instance=mark, assessment=assessment, enrollment=enrollment, subject=subject, assignment=assignment)
    if request.method == "POST" and form.is_valid():
        if attempt(form, lambda: save_mark(form, request.user)):
            messages.success(request, "Mark saved.")
            return redirect(reverse("academics:marks", args=[pk]) + f"?subject={subject.pk}")
    return form_page(request, form, f"{enrollment.student.full_name} / {subject.name}", reverse("academics:marks", args=[pk]) + f"?subject={subject.pk}", explanation=f"{assessment}. Maximum score: {assessment.maximum_score}.")


@role_required(User.Role.SCHOOL_ADMIN)
@never_cache
@require_http_methods(["GET", "POST"])
def assessment_status(request, pk, status):
    assessment = get_object_or_404(visible_assessments(request.user), pk=pk)
    form = ConfigurationStatusForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        if attempt(form, lambda: set_assessment_status(assessment, status, request.user)):
            messages.success(request, "Assessment status updated.")
            return redirect("academics:marks", pk=pk)
    return form_page(request, form, f"{'Open marks' if status == 'open' else 'Close marks'}: {assessment}", reverse("academics:marks", args=[pk]))
