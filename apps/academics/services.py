from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from apps.accounts.models import User
from apps.schools.services import lock_school, write_record
from .models import Assessment, GradingScheme, Mark, MarkSubmission, Teacher
from .permissions import can_manage_academics, mark_assignment


def require_manager(actor):
    if not can_manage_academics(actor):
        raise PermissionDenied


@transaction.atomic
def save_academic(form, actor):
    require_manager(actor)
    lock_school()
    record = form.save(commit=False)
    if isinstance(record, Teacher):
        User.objects.select_for_update().get(pk=record.user_id)
    if record.pk and not record._state.adding and hasattr(record, "is_active"):
        record.is_active = type(record).objects.get(pk=record.pk).is_active
    if isinstance(record, Assessment) and record.pk:
        record.status = Assessment.objects.get(pk=record.pk).status
    if isinstance(record, Assessment):
        from .section_grades import current_scheme
        previous = Assessment.objects.get(pk=record.pk) if record.pk else None
        scheme = previous.grading_scheme if previous and previous.grading_scheme_id else current_scheme(record.academic_class.section)
        record.grading_scheme = previous.grading_scheme if previous and previous.grading_scheme_id else (scheme if scheme and scheme.is_active else None)
        if previous and previous.marks.exists() and record.grading_scheme and record.grading_scheme.mode == "descriptive" and previous.marks.filter(level__isnull=True).exists():
            raise ValidationError("Existing numeric marks cannot use descriptive learning levels.")
    if isinstance(record, GradingScheme) and (record.in_use() or record.is_active):
        raise ValidationError("Create a new scheme to change grading already in use; deactivate unused schemes before editing.")
    fields = [name for name in form._meta.fields if not record._meta.get_field(name).many_to_many]
    if isinstance(record, Assessment):
        fields.append("grading_scheme")
    record = write_record(record, actor, "Saved academic configuration.", update_fields=fields)
    form.save_m2m()
    return record


@transaction.atomic
def set_academic_active(record, active, actor):
    require_manager(actor)
    lock_school()
    record = type(record).objects.select_for_update().get(pk=record.pk)
    record.is_active = active
    if isinstance(record, GradingScheme) and active:
        record.validate_configuration()
    return write_record(record, actor, "Activated academic record." if active else "Deactivated academic record.", update_fields=["is_active"])


@transaction.atomic
def set_assessment_status(assessment, status, actor):
    require_manager(actor)
    lock_school()
    record = Assessment.objects.select_for_update().get(pk=assessment.pk)
    allowed = {"draft": {"open"}, "open": {"closed"}, "closed": {"open"}}
    if status not in allowed[record.status]:
        raise ValidationError("This assessment status transition is not available.")
    if status == "open" and record.reports.filter(is_current=True).exists():
        raise ValidationError("Use the report correction workflow to reopen an assessment with generated reports.")
    if status == "closed" and record.requires_mark_review:
        from .mark_sheets import require_approved_sheets
        require_approved_sheets(record)
    record.status = status
    if status == "open" and not record.grading_scheme_id:
        from .section_grades import current_scheme
        scheme = current_scheme(record.academic_class.section)
        if scheme and scheme.is_active:
            record.grading_scheme = scheme
    return write_record(record, actor, f"Changed assessment status to {status}.", update_fields=["status", "grading_scheme"])


@transaction.atomic
def save_mark(form, actor):
    lock_school()
    proposed = form.save(commit=False)
    assessment = Assessment.objects.select_for_update().get(pk=proposed.assessment_id)
    assignment = mark_assignment(assessment, proposed.enrollment, proposed.subject, actor)
    if assignment is None:
        raise PermissionDenied
    if assessment.requires_mark_review and MarkSubmission.objects.filter(assessment=assessment, assignment=assignment, status__in=["submitted", "approved"]).exists():
        raise ValidationError("This marks sheet is locked. A reviewer must return it for correction before marks can change.")
    existing = Mark.objects.select_for_update().filter(assessment=assessment, enrollment_id=proposed.enrollment_id, subject_id=proposed.subject_id).first()
    expected = form.cleaned_data["expected_revision"]
    if (existing.revision if existing else 0) != expected:
        raise ValidationError("This mark was changed in another request. Reload before editing it.")
    record = existing or proposed
    record.assessment = assessment
    record.teaching_assignment = assignment
    record.score = proposed.score
    record.level = proposed.level
    record.is_absent = proposed.is_absent
    record.revision = expected + 1
    return write_record(record, actor, "Saved assessment mark.")
