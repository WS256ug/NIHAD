from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from apps.accounts.models import User
from apps.accounts.permissions import dashboard_url, has_role
from .metrics import dashboard_metrics

WORKSPACES = {
    User.Role.SUPER_ADMIN: ("Dashboard", "Manage access across your school.", "Manage school accounts and administration from one place."),
    User.Role.SCHOOL_ADMIN: ("Dashboard", "Keep your school connected.", "Manage student records, guardians, enrollment and school accounts."),
    User.Role.HEADTEACHER: ("Dashboard", "A clear view of your school.", "Review results and reports, approve comments, and manage promotion decisions."),
    User.Role.TEACHER: ("Dashboard", "Your classes and academic tasks.", "Enter marks for assigned subjects and add class-teacher comments where you are assigned."),
    User.Role.BURSAR: ("Dashboard", "Your school's financial records.", "Manage student charges, payments, receipts, expenses and income."),
    User.Role.STUDENT: ("Student portal", "Stay connected to your child's school.", "Use your child's registration number to access their records."),
    User.Role.GUARDIAN: ("Guardian portal", "Stay connected to your children's school.", "View your linked children's records with your own account."),
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
    if role == User.Role.STUDENT and request.user.role == User.Role.STUDENT:
        return redirect("students:portal_home")
    if role == User.Role.GUARDIAN and request.user.role == User.Role.GUARDIAN:
        return redirect("students:family_home")
    title, heading, description = WORKSPACES[role]
    return render(request, "dashboard/home.html", {
        "workspace_title": title, "workspace_heading": heading, "workspace_description": description,
        **dashboard_metrics(request.user, role),
    })
