from config.dialogs import form_redirect
from django import forms
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
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
from .grading import grade_score
from .mark_sheets import (SheetControlForm, SheetReviewForm, SheetRowForm, review_sheet,
                         require_approved_sheets, all_sheet_assignments, roster_token, save_sheet, sheet_assignments, sheet_enrollments)


def available_subjects(assessment, actor):
    subjects = Subject.objects.filter(section_id=assessment.academic_class.section_id)
    if has_role(actor, User.Role.SCHOOL_ADMIN, User.Role.HEADTEACHER) or assessment_assignments(assessment, actor, ClassTeacherAssignment).exists():
        return subjects
    return subjects.filter(pk__in=assessment_assignments(assessment, actor).values("subject_id"))


@role_required(User.Role.SCHOOL_ADMIN, User.Role.HEADTEACHER, User.Role.TEACHER)
@never_cache
@require_http_methods(["GET", "POST"])
def roster(request, pk):
    assessment = get_object_or_404(visible_assessments(request.user).prefetch_related("grading_scheme__rules"), pk=pk)
    assignments = sheet_assignments(assessment, request.user)
    candidates = assignments
    if request.GET.get("subject") and not request.GET.get("assignment"):
        candidates = candidates.filter(subject_id=selected_pk(request.GET["subject"]))
    assignment = get_object_or_404(candidates, pk=selected_pk(request.GET["assignment"])) if request.GET.get("assignment") else candidates.first()
    if request.GET.get("subject") and assignment is None:
        raise PermissionDenied
    enrollments = list(sheet_enrollments(assessment, assignment)) if assignment else []
    marks = {mark.enrollment_id: mark for mark in Mark.objects.filter(assessment=assessment, subject=assignment.subject, enrollment__in=enrollments).select_related("level")} if assignment else {}
    submission = assessment.mark_submissions.filter(assignment=assignment).first() if assignment else None
    reviewer = has_role(request.user, User.Role.SCHOOL_ADMIN, User.Role.HEADTEACHER)
    editable = bool(assignment and assessment.status == "open" and has_role(request.user, User.Role.SCHOOL_ADMIN, User.Role.TEACHER) and (not assessment.requires_mark_review or not submission or submission.status in ("draft", "returned")))
    reviewing = request.method == "POST" and "review-action" in request.POST
    if request.method == "POST" and (not assignment or (reviewing and (not reviewer or not assessment.requires_mark_review)) or (not reviewing and not editable)):
        raise PermissionDenied
    rows = [SheetRowForm(request.POST if request.method == "POST" and not reviewing else None,
                         assessment=assessment, enrollment=enrollment, mark=marks.get(enrollment.pk)) for enrollment in enrollments]
    initial = {"revision": submission.revision if submission else 0,
               "roster": roster_token(assessment, assignment, enrollments, request.user) if assignment else ""}
    control = SheetControlForm(request.POST if request.method == "POST" and not reviewing else None, initial=initial)
    review = SheetReviewForm(request.POST if reviewing else None, prefix="review", initial={"revision": initial["revision"]})
    if request.method == "POST":
        saved = None
        if reviewing:
            if review.is_valid():
                saved = attempt(review, lambda: review_sheet(assessment, assignment, review, request.user))
        else:
            valid = control.is_valid()
            for row in rows:
                valid = row.is_valid() and valid
                if control.cleaned_data.get("action") == "submit" and not row.errors and not row.has_result():
                    row.add_error(None, "Enter a result or mark this student absent before submitting.")
                    valid = False
            if valid:
                saved = attempt(control, lambda: save_sheet(assessment, assignment, rows, control, request.user))
        if saved:
            messages.success(request, "Marks sheet approved." if reviewing and saved.status == "approved" else "Sheet returned for correction." if reviewing else "Marks submitted for review." if saved.status == "submitted" else "Progress saved. You can continue later.")
            return redirect(reverse("academics:marks", args=[assessment.pk]) + f"?assignment={assignment.pk}")
    rules = list(assessment.grading_scheme.rules.all()) if assessment.grading_scheme_id else []
    for row in rows:
        row.saved_grade = ""
        if row.mark:
            if row.mark.is_absent:
                row.saved_grade = "Absent"
            elif row.mark.level_id:
                row.saved_grade = row.mark.level.label
            elif rules:
                try:
                    row.saved_grade = grade_score(row.mark.score, assessment.maximum_score, rules)[1].label
                except ValidationError:
                    row.saved_grade = "Grades not ready"
    can_close_marks = False
    if can_manage_academics(request.user) and assessment.status == "open":
        try:
            require_approved_sheets(assessment)
            can_close_marks = True
        except ValidationError:
            pass
    return render(request, "academics/marks.html", {
        "can_close_marks": can_close_marks,
        "assessment": assessment, "assignments": assignments, "assignment": assignment,
        "rows": rows, "control": control, "review_form": review, "submission": submission,
        "can_edit": editable, "can_review": assessment.requires_mark_review and reviewer and assessment.status == "open" and submission and submission.status in ("submitted", "approved"),
        "can_manage_academics": can_manage_academics(request.user),
        "unassigned_subjects": Subject.objects.filter(section_id=assessment.academic_class.section_id).exclude(pk__in=all_sheet_assignments(assessment).values("subject_id")) if reviewer else Subject.objects.none(),
        "completed": len(marks), "total": len(enrollments),
        "sheet_unsaved": request.method == "POST" and not reviewing,
        "descriptive": assessment.grading_scheme_id and assessment.grading_scheme.mode == "descriptive",
    })


@role_required(User.Role.SCHOOL_ADMIN, User.Role.HEADTEACHER, User.Role.TEACHER)
@never_cache
@require_GET
def entry(request):
    records = visible_assessments(request.user).filter(status="open")
    if has_role(request.user, User.Role.TEACHER) and not has_role(request.user, User.Role.SCHOOL_ADMIN, User.Role.HEADTEACHER):
        records = [assessment for assessment in records if sheet_assignments(assessment, request.user).exists()]
    return render(request, "academics/marks_entry.html", {"assessments": records})


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
            return form_redirect(request, reverse("academics:marks", args=[pk]) + f"?subject={subject.pk}")
    return form_page(request, form, f"{enrollment.student.full_name} / {subject.name}", reverse("academics:marks", args=[pk]) + f"?subject={subject.pk}", explanation=f"{assessment}. Maximum score: {assessment.maximum_score}.")


@role_required(User.Role.SCHOOL_ADMIN)
@never_cache
@require_http_methods(["GET", "POST"])
def assessment_status(request, pk, status):
    assessment = get_object_or_404(visible_assessments(request.user), pk=pk)
    form = (forms.Form if status == "closed" else ConfigurationStatusForm)(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        def change_status():
            if status == "closed":
                require_approved_sheets(assessment)
            return set_assessment_status(assessment, status, request.user)
        if attempt(form, change_status):
            messages.success(request, "Assessment status updated.")
            return form_redirect(request, "academics:marks", pk=pk)
    return form_page(request, form, "Close marks entry?" if status == "closed" else f"Open marks: {assessment}", reverse("academics:marks", args=[pk]),
                     submit_label="Close marks entry" if status == "closed" else "Open marks entry",
                     explanation=(f"{assessment}. " + ("All subject sheets must be approved. " if assessment.requires_mark_review else "Complete all subject sheets. ") + "Marks will be locked for this assessment.") if status == "closed" else "")
