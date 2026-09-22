"""Shared role checks and account scope; hiding navigation is never authorization."""
from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.urls import reverse

from .models import User

STANDARD_ROLES = (User.Role.HEADTEACHER, User.Role.TEACHER, User.Role.BURSAR, User.Role.GUARDIAN)


def effective_role(user):
    if not user.is_authenticated or not user.is_active:
        return None
    if user.is_superuser:
        return User.Role.SUPER_ADMIN
    if user.role in User.Role.values and user.role != User.Role.SUPER_ADMIN:
        return user.role
    return None


def has_role(user, *roles):
    role = effective_role(user)
    return bool(role and roles and (role == User.Role.SUPER_ADMIN or role in roles))


def role_required(*roles):
    def decorator(view):
        @login_required
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if not has_role(request.user, *roles):
                raise PermissionDenied
            return view(request, *args, **kwargs)
        return wrapped
    return decorator


def dashboard_url(user):
    role = effective_role(user)
    if role is None:
        raise PermissionDenied
    if role == User.Role.STUDENT:
        return reverse("students:portal_home")
    if role == User.Role.GUARDIAN:
        return reverse("students:family_home")
    return reverse(f"dashboard:{role}")


def can_manage_accounts(user):
    return has_role(user, User.Role.SCHOOL_ADMIN)


def can_manage_school(user):
    return has_role(user, User.Role.SCHOOL_ADMIN)


def assignable_roles(user):
    if not can_manage_accounts(user):
        return ()
    return (User.Role.SCHOOL_ADMIN, *STANDARD_ROLES) if user.is_superuser else STANDARD_ROLES


def manageable_accounts(user):
    """Privileged accounts are managed only by superusers through Django admin."""
    if not can_manage_accounts(user):
        return User.objects.none()
    return User.objects.filter(
        role__in=assignable_roles(user), is_staff=False, is_superuser=False,
    ).exclude(groups__isnull=False).exclude(user_permissions__isnull=False).exclude(pk=user.pk)
