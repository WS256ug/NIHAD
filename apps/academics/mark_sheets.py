"""Atomic marks-sheet saves and audited subject/assignment review."""
from django import forms
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.accounts.models import User
from apps.accounts.permissions import has_role
from apps.schools.services import lock_school, write_record
from apps.students.models import Enrollment
from .forms import MarkForm
from .models import Assessment, GradeRule, Mark, MarkSubmission, TeachingAssignment


def all_sheet_assignments(assessment):
    records = TeachingAssignment.objects.filter(
        academic_year_id=assessment.term.academic_year_id, academic_class_id=assessment.academic_class_id,
        is_active=True, teacher__employment_status="active", teacher__user__is_active=True,
    ).filter(Q(term__isnull=True) | Q(term_id=assessment.term_id))
    if assessment.stream_id:
        records = records.filter(Q(stream__isnull=True) | Q(stream_id=assessment.stream_id))
    return records.select_related("subject", "stream", "teacher__user").order_by("subject__name", "stream__name", "pk")


def sheet_assignments(assessment, actor):
    records = all_sheet_assignments(assessment)
    if has_role(actor, User.Role.SCHOOL_ADMIN, User.Role.HEADTEACHER):
        return records
    return records.filter(teacher__user=actor) if has_role(actor, User.Role.TEACHER) else records.none()


def sheet_enrollments(assessment, assignment):
    records = Enrollment.objects.filter(
        student__school_id=assessment.term.academic_year.school_id,
        academic_year_id=assessment.term.academic_year_id, academic_class_id=assessment.academic_class_id,
        enrollment_date__lte=assessment.date,
    ).filter(Q(completion_date__isnull=True) | Q(completion_date__gte=assessment.date))
    if assessment.stream_id:
        records = records.filter(stream_id=assessment.stream_id)
    if assignment.stream_id:
        records = records.filter(stream_id=assignment.stream_id)
    return records.select_related("student", "stream").order_by("student__last_name", "student__first_name", "pk")


def roster_token(assessment, assignment, enrollments, actor):
    return signing.dumps([assessment.pk, assignment.pk, actor.pk, [row.pk for row in enrollments]], salt="mark-sheet")


class SheetControlForm(forms.Form):
    roster = forms.CharField(widget=forms.HiddenInput)
    revision = forms.IntegerField(min_value=0, widget=forms.HiddenInput)
    action = forms.ChoiceField(choices=[("save", "Save progress"), ("submit", "Submit for review")], widget=forms.HiddenInput)


class SheetRowForm(forms.Form):
    score = forms.DecimalField(required=False, min_value=0, max_digits=7, decimal_places=2)
    level = forms.ModelChoiceField(required=False, queryset=GradeRule.objects.none())
    is_absent = forms.BooleanField(required=False, label="Absent")
    expected_revision = forms.IntegerField(min_value=0, widget=forms.HiddenInput)

    def __init__(self, *args, assessment, enrollment, mark, **kwargs):
        self.enrollment, self.mark = enrollment, mark
        kwargs["prefix"] = f"mark-{enrollment.pk}"
        kwargs["initial"] = {"score": mark.score if mark else None, "level": mark.level_id if mark else None,
                             "is_absent": mark.is_absent if mark else False, "expected_revision": mark.revision if mark else 0}
        super().__init__(*args, **kwargs)
        if assessment.grading_scheme_id and assessment.grading_scheme.mode == "descriptive":
            self.fields.pop("score")
            self.fields["level"].queryset = assessment.grading_scheme.rules.all()
            self.fields["level"].choices = [("", "Choose level")] + [(level.pk, level.label) for level in assessment.grading_scheme.rules.all()]
            field = self.fields["level"]
        else:
            self.fields.pop("level")
            field = self.fields["score"]
            field.max_value = assessment.maximum_score
            field.widget.attrs.update(min=0, max=assessment.maximum_score, step="0.01", inputmode="decimal")
        field.widget.attrs.update({"data-mark-value": "", "aria-label": f"Result for {enrollment.student.full_name}"})
        self.fields["is_absent"].widget.attrs.update({"aria-label": f"Absent: {enrollment.student.full_name}"})
        self.maximum = assessment.maximum_score

    def clean(self):
        data = super().clean()
        score, level = data.get("score"), data.get("level")
        if data.get("is_absent") and (score is not None or level is not None):
            raise ValidationError("Clear the result before marking this student absent.")
        if score is not None and score > self.maximum:
            self.add_error("score", f"Enter a mark from 0 to {self.maximum}.")
        if self.mark and not data.get("is_absent") and score is None and level is None:
            raise ValidationError("Enter a result or mark the student absent. A saved result cannot be cleared.")
        return data

    def has_result(self):
        data = self.cleaned_data
        return data.get("is_absent") or data.get("score") is not None or data.get("level") is not None


class SheetReviewForm(forms.Form):
    action = forms.ChoiceField(choices=[("approve", "Approve sheet"), ("return", "Return for correction")])
    note = forms.CharField(required=False, max_length=2000, widget=forms.Textarea(attrs={"rows": 2}), label="Review note")
    revision = forms.IntegerField(min_value=0, widget=forms.HiddenInput)

    def clean(self):
        data = super().clean()
        if data.get("action") == "return" and not data.get("note"):
            self.add_error("note", "Explain what needs correcting.")
        return data


def sheet_snapshot(assessment, assignment):
    ids = list(sheet_enrollments(assessment, assignment).values_list("pk", flat=True))
    marks = dict(Mark.objects.filter(assessment=assessment, subject=assignment.subject, enrollment_id__in=ids).values_list("enrollment_id", "revision"))
    if not ids or len(marks) != len(ids):
        raise ValidationError("Every student needs a result or an Absent status before this sheet can be submitted or approved.")
    return [[pk, marks[pk]] for pk in ids]


@transaction.atomic
def save_sheet(assessment, assignment, row_forms, control, actor):
    from .services import save_mark

    if not has_role(actor, User.Role.SCHOOL_ADMIN, User.Role.TEACHER):
        raise PermissionDenied
    lock_school()
    assessment = Assessment.objects.select_for_update().get(pk=assessment.pk)
    if assessment.status != "open":
        raise ValidationError("This assessment is not open for marks.")
    assignment = sheet_assignments(assessment, actor).filter(pk=assignment.pk).first()
    if assignment is None:
        raise PermissionDenied
    ids = list(sheet_enrollments(assessment, assignment).values_list("pk", flat=True))
    try:
        token = signing.loads(control.cleaned_data["roster"], salt="mark-sheet", max_age=86400)
    except signing.BadSignature:
        raise ValidationError("This sheet has expired or changed. Reload before saving.") from None
    if token != [assessment.pk, assignment.pk, actor.pk, ids] or [form.enrollment.pk for form in row_forms] != ids:
        raise ValidationError("The student list has changed. Reload the sheet before saving.")
    submission = MarkSubmission.objects.select_for_update().filter(assessment=assessment, assignment=assignment).first()
    if (submission.revision if submission else 0) != control.cleaned_data["revision"]:
        raise ValidationError("This sheet changed in another request. Reload before saving.")
    if submission and submission.status in ("submitted", "approved"):
        raise ValidationError("This sheet is locked. Ask a reviewer to return it for correction.")
    if not ids:
        raise ValidationError("There are no eligible students in this sheet.")
    for row in row_forms:
        current = Mark.objects.filter(assessment=assessment, subject=assignment.subject, enrollment_id=row.enrollment.pk).first()
        if (current.revision if current else 0) != row.cleaned_data["expected_revision"]:
            raise ValidationError(f"The result for {row.enrollment.student.full_name} changed. Reload before saving.")
        if not row.has_result():
            if control.cleaned_data["action"] == "submit":
                raise ValidationError("Complete every row or mark the student absent before submitting.")
            continue
        data = row.cleaned_data.copy()
        data["level"] = data["level"].pk if data.get("level") else ""
        previous_value = (current.score, current.level_id, current.is_absent) if current else None
        form = MarkForm(data, instance=current, assessment=assessment, enrollment=row.enrollment, subject=assignment.subject, assignment=assignment)
        if not form.is_valid():
            raise ValidationError([f"{row.enrollment.student.full_name}: {error}" for errors in form.errors.values() for error in errors])
        if previous_value == (form.cleaned_data.get("score"), form.cleaned_data.get("level").pk if form.cleaned_data.get("level") else None, form.cleaned_data["is_absent"]):
            continue
        save_mark(form, actor)
    submission = submission or MarkSubmission(assessment=assessment, assignment=assignment)
    submission.revision += 1
    if control.cleaned_data["action"] == "submit":
        submission.snapshot = sheet_snapshot(assessment, assignment)
        submission.status = "submitted"
        submission.submitted_at, submission.submitted_by = timezone.now(), actor
        submission.reviewed_at, submission.reviewed_by = None, None
    write_record(submission, actor, "Submitted marks for review." if submission.status == "submitted" else "Saved marks sheet progress.")
    if not assessment.requires_mark_review:
        assessment.requires_mark_review = True
        write_record(assessment, actor, "Enabled marks sheet review.", update_fields=["requires_mark_review"])
    return submission


@transaction.atomic
def review_sheet(assessment, assignment, form, actor):
    if not has_role(actor, User.Role.SCHOOL_ADMIN, User.Role.HEADTEACHER):
        raise PermissionDenied
    lock_school()
    assessment = Assessment.objects.select_for_update().get(pk=assessment.pk)
    if assessment.status != "open" or not all_sheet_assignments(assessment).filter(pk=assignment.pk).exists():
        raise ValidationError("Only active sheets in an open assessment can be reviewed.")
    submission = MarkSubmission.objects.select_for_update().filter(assessment=assessment, assignment=assignment).first()
    if not submission or submission.revision != form.cleaned_data["revision"]:
        raise ValidationError("This sheet has changed. Reload before reviewing it.")
    action = form.cleaned_data["action"]
    if submission.status != "submitted" and not (action == "return" and submission.status == "approved"):
        raise ValidationError("Submit the sheet before reviewing it.")
    if action == "approve" and submission.snapshot != sheet_snapshot(assessment, assignment):
        raise ValidationError("The results or student list changed. Return the sheet for correction.")
    submission.status = "approved" if action == "approve" else "returned"
    submission.review_note = form.cleaned_data["note"]
    submission.reviewed_at, submission.reviewed_by = timezone.now(), actor
    submission.revision += 1
    return write_record(submission, actor, "Reviewed marks sheet: " + submission.get_status_display())


def require_approved_sheets(assessment):
    sheets = 0
    for assignment in all_sheet_assignments(assessment):
        if not sheet_enrollments(assessment, assignment).exists():
            continue
        sheets += 1
        submission = MarkSubmission.objects.filter(assessment=assessment, assignment=assignment, status="approved").first()
        if not submission or submission.snapshot != sheet_snapshot(assessment, assignment):
            raise ValidationError(f"Approve the complete marks sheet for {assignment.subject.name} / {assignment.stream or 'All streams'} before closing or generating reports.")
    if not sheets:
        raise ValidationError("Assign teachers and enroll students before closing marks entry.")


def return_sheets_for_correction(assessment, reason, actor):
    for submission in assessment.mark_submissions.filter(status__in=["submitted", "approved"]):
        submission.status = "returned"
        submission.review_note = reason
        submission.reviewed_by, submission.reviewed_at = actor, timezone.now()
        submission.revision += 1
        write_record(submission, actor, "Returned marks for report correction.")
