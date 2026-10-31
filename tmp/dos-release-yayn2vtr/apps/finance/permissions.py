from apps.accounts.models import User
from apps.accounts.permissions import has_role


def can_manage_finance(user):
    return has_role(user, User.Role.SCHOOL_ADMIN, User.Role.BURSAR)
