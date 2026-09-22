from apps.accounts.models import User
from apps.accounts.permissions import has_role
from .models import Guardian, Student


def can_manage_students(user):
    return has_role(user, User.Role.SCHOOL_ADMIN)


def can_view_students(user):
    return has_role(user, User.Role.SCHOOL_ADMIN, User.Role.HEADTEACHER, User.Role.TEACHER)


def visible_students(user):
    if not can_view_students(user):
        return Student.objects.none()
    if not has_role(user, User.Role.SCHOOL_ADMIN, User.Role.HEADTEACHER):
        from apps.academics.permissions import visible_enrollments
        return Student.objects.filter(school_id=1, enrollments__in=visible_enrollments(user)).distinct()
    return Student.objects.filter(school_id=1)


def manageable_guardians(user):
    if not can_manage_students(user):
        return Guardian.objects.none()
    return Guardian.objects.filter(school_id=1)
