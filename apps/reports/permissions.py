from django.db.models import Q
from apps.accounts.models import User
from apps.accounts.permissions import has_role
from apps.academics.models import ClassTeacherAssignment, TeachingAssignment
from apps.academics.permissions import assessment_assignments, enrollment_scope, teacher_assignments
from .models import StudentReport


def visible_reports(user):
    records = StudentReport.objects.filter(enrollment__student__school_id=1).select_related('assessment__assessment_type', 'assessment__term__academic_year', 'assessment__academic_class__section', 'enrollment__student', 'enrollment__stream')
    if has_role(user, User.Role.SCHOOL_ADMIN, User.Role.HEADTEACHER):
        return records
    if has_role(user, User.Role.TEACHER):
        scope = Q(pk__in=[])
        for model in (TeachingAssignment, ClassTeacherAssignment):
            for assignment in teacher_assignments(user, model):
                match = Q(assessment__academic_class_id=assignment.academic_class_id, assessment__term__academic_year_id=assignment.academic_year_id)
                if assignment.term_id:
                    match &= Q(assessment__term_id=assignment.term_id)
                if assignment.stream_id:
                    match &= Q(enrollment__stream_id=assignment.stream_id)
                scope |= match
        return records.filter(scope)
    return records.none()


def can_comment(user, report):
    if not report.is_current or report.status != 'draft' or not report.snapshot:
        return False
    if has_role(user, User.Role.SCHOOL_ADMIN):
        return True
    return has_role(user, User.Role.TEACHER) and assessment_assignments(report.assessment, user, ClassTeacherAssignment).filter(Q(stream__isnull=True) | Q(stream_id=report.enrollment.stream_id)).exists()
