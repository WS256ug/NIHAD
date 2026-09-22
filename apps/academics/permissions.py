from django.db.models import Q
from apps.accounts.models import User
from apps.accounts.permissions import has_role
from apps.students.models import Enrollment
from .models import Assessment, ClassTeacherAssignment, TeachingAssignment


def can_manage_academics(user):
    return has_role(user, User.Role.SCHOOL_ADMIN)


def can_view_academics(user):
    return has_role(user, User.Role.SCHOOL_ADMIN, User.Role.HEADTEACHER, User.Role.TEACHER)


def teacher_assignments(user, model=TeachingAssignment):
    return model.objects.filter(teacher__user=user, teacher__employment_status="active", teacher__user__is_active=True, is_active=True, academic_year__school_id=1).select_related("term", "academic_class", "stream", "teacher__user")


def enrollment_scope(assignment):
    scope = Q(academic_year_id=assignment.academic_year_id, academic_class_id=assignment.academic_class_id)
    if assignment.stream_id:
        scope &= Q(stream_id=assignment.stream_id)
    if assignment.term_id:
        scope &= Q(enrollment_date__lte=assignment.term.end_date)
        scope &= Q(completion_date__isnull=True) | Q(completion_date__gte=assignment.term.start_date)
    return scope


def visible_enrollments(user):
    records = Enrollment.objects.filter(student__school_id=1)
    if has_role(user, User.Role.SCHOOL_ADMIN, User.Role.HEADTEACHER):
        return records
    if not has_role(user, User.Role.TEACHER):
        return records.none()
    scope = Q(pk__in=[])
    for model in (TeachingAssignment, ClassTeacherAssignment):
        for assignment in teacher_assignments(user, model):
            scope |= enrollment_scope(assignment)
    return records.filter(scope)


def assessment_assignments(assessment, user, model=TeachingAssignment, subject=None):
    records = model.objects.filter(is_active=True, teacher__employment_status="active", teacher__user__is_active=True, academic_year_id=assessment.term.academic_year_id, academic_class_id=assessment.academic_class_id).filter(Q(term__isnull=True) | Q(term_id=assessment.term_id)).select_related("teacher__user", "term", "subject" if model == TeachingAssignment else "academic_class")
    if assessment.stream_id:
        records = records.filter(Q(stream__isnull=True) | Q(stream_id=assessment.stream_id))
    if not has_role(user, User.Role.SCHOOL_ADMIN, User.Role.HEADTEACHER):
        records = records.filter(teacher__user=user)
    if subject and model == TeachingAssignment:
        records = records.filter(subject=subject)
    return records


def visible_assessments(user):
    records = Assessment.objects.filter(term__academic_year__school_id=1).select_related("term__academic_year", "academic_class__section", "assessment_type", "stream")
    if has_role(user, User.Role.SCHOOL_ADMIN, User.Role.HEADTEACHER):
        return records
    if not has_role(user, User.Role.TEACHER):
        return records.none()
    scope = Q(pk__in=[])
    for model in (TeachingAssignment, ClassTeacherAssignment):
        for assignment in teacher_assignments(user, model):
            match = Q(term__academic_year_id=assignment.academic_year_id, academic_class_id=assignment.academic_class_id)
            if assignment.term_id:
                match &= Q(term_id=assignment.term_id)
            if assignment.stream_id:
                match &= Q(stream__isnull=True) | Q(stream_id=assignment.stream_id)
            scope |= match
    return records.filter(scope)


def assessment_enrollments(assessment, user, subject=None):
    records = Enrollment.objects.filter(student__school_id=1, academic_year_id=assessment.term.academic_year_id, academic_class_id=assessment.academic_class_id, enrollment_date__lte=assessment.date).filter(Q(completion_date__isnull=True) | Q(completion_date__gte=assessment.date))
    if assessment.stream_id:
        records = records.filter(stream_id=assessment.stream_id)
    if not has_role(user, User.Role.SCHOOL_ADMIN, User.Role.HEADTEACHER):
        scope = Q(pk__in=[])
        for model in (TeachingAssignment, ClassTeacherAssignment):
            for assignment in assessment_assignments(assessment, user, model, subject):
                scope |= enrollment_scope(assignment)
        records = records.filter(scope)
    return records.select_related("student", "academic_year", "academic_class__section", "stream").order_by("student__last_name", "student__first_name", "pk")


def mark_assignment(assessment, enrollment, subject, user):
    if not has_role(user, User.Role.SCHOOL_ADMIN, User.Role.TEACHER):
        return None
    return assessment_assignments(assessment, user, subject=subject).filter(Q(stream__isnull=True) | Q(stream_id=enrollment.stream_id)).first()
