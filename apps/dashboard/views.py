from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from apps.accounts.models import User
from apps.accounts.permissions import dashboard_url, has_role

WORKSPACES = {
    User.Role.SUPER_ADMIN: ("Super Admin workspace", "Manage access across your school.", "Manage school accounts and administration from one place."),
    User.Role.SCHOOL_ADMIN: ("School Admin workspace", "Keep your school connected.", "Create and manage accounts for your school's staff and guardians."),
    User.Role.HEADTEACHER: ("Headteacher workspace", "A clear view of your school.", "Your account is ready. Academic review and report approval will appear as those features become available."),
    User.Role.TEACHER: ("Teacher workspace", "More time for teaching.", "Your account is ready. Assigned classes, marks and comments will appear as those features become available."),
    User.Role.BURSAR: ("Finance workspace", "Your school's finance workspace.", "Your account is ready. Fees, payments and expenses will appear as those features become available."),
    User.Role.GUARDIAN: ("Guardian workspace", "Stay connected to your child's school.", "Your account is ready. Linked children and their school information will appear as those features become available."),
}


@login_required
@never_cache
@require_GET
def home(request):
    return redirect(dashboard_url(request.user))


@login_required
@never_cache
@require_GET
def workspace(request, role):
    if not has_role(request.user, role):
        raise PermissionDenied
    title, heading, description = WORKSPACES[role]
    return render(request, "dashboard/home.html", {
        "workspace_title": title, "workspace_heading": heading, "workspace_description": description,
    })
