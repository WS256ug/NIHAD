from django.contrib import messages
from django.contrib.admin.models import ADDITION, CHANGE, LogEntry
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.contrib.contenttypes.models import ContentType
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods
from django.views.decorators.debug import sensitive_post_parameters

from .forms import AccountStatusForm, ManagedAccountChangeForm, ManagedAccountCreationForm
from .models import User
from .permissions import assignable_roles, dashboard_url, manageable_accounts, role_required


class SignInView(LoginView):
    template_name = "registration/login.html"

    def get_default_redirect_url(self):
        return dashboard_url(self.request.user)

    def form_valid(self, form):
        response = super().form_valid(form)
        if self.request.headers.get("HX-Request") == "true":
            # Reload after authentication so the browser receives the rotated CSRF token.
            return HttpResponse(headers={"HX-Redirect": response.url})
        return response


def record_account_change(actor, target, action, message):
    LogEntry.objects.create(
        user=actor, content_type=ContentType.objects.get_for_model(User),
        object_id=str(target.pk), object_repr=str(target), action_flag=action,
        change_message=message,
    )


@login_required
@never_cache
@require_GET
def profile(request):
    return render(request, "accounts/profile.html")


@role_required(User.Role.SCHOOL_ADMIN)
@never_cache
@require_GET
def user_list(request):
    query = request.GET.get("q", "").strip()
    role = request.GET.get("role", "")
    users = manageable_accounts(request.user).order_by("username")
    if query:
        users = users.filter(
            Q(username__icontains=query) | Q(first_name__icontains=query)
            | Q(last_name__icontains=query) | Q(email__icontains=query)
        )
    if role:
        users = users.filter(role=role)
    return render(request, "accounts/user_list.html", {
        "page_obj": Paginator(users, 20).get_page(request.GET.get("page")),
        "query": query, "selected_role": role,
        "role_choices": [(value, label) for value, label in User.Role.choices if value in assignable_roles(request.user)],
    })


@role_required(User.Role.SCHOOL_ADMIN)
@never_cache
@require_http_methods(["GET", "POST"])
@sensitive_post_parameters("password1", "password2")
def user_create(request):
    form = ManagedAccountCreationForm(request.POST if request.method == "POST" else None, actor=request.user)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            user = form.save()
            record_account_change(request.user, user, ADDITION, "Created school account.")
        messages.success(request, "Account created. Share the initial password with the account holder securely.")
        return redirect("accounts:user_list")
    return render(request, "accounts/user_form.html", {"form": form, "page_title": "Create account"})


@role_required(User.Role.SCHOOL_ADMIN)
@never_cache
@require_http_methods(["GET", "POST"])
def user_edit(request, pk):
    with transaction.atomic():
        users = manageable_accounts(request.user)
        if request.method == "POST":
            users = users.select_for_update()
        target = get_object_or_404(users, pk=pk)
        form = ManagedAccountChangeForm(
            request.POST if request.method == "POST" else None, instance=target, actor=request.user,
        )
        if request.method == "POST" and form.is_valid():
            user = form.save()
            record_account_change(request.user, user, CHANGE, "Updated account fields: " + ", ".join(form.changed_data))
            messages.success(request, "Account updated.")
            return redirect("accounts:user_list")
    return render(request, "accounts/user_form.html", {"form": form, "page_title": "Edit account", "account": target})


@role_required(User.Role.SCHOOL_ADMIN)
@never_cache
@require_http_methods(["GET", "POST"])
def user_status(request, pk, activate):
    with transaction.atomic():
        users = manageable_accounts(request.user)
        if request.method == "POST":
            users = users.select_for_update()
        target = get_object_or_404(users, pk=pk)
        form = AccountStatusForm(request.POST if request.method == "POST" else None)
        if request.method == "POST" and form.is_valid():
            target.is_active = activate
            target.save(update_fields=["is_active", "updated_at"])
            record_account_change(request.user, target, CHANGE, "Activated account." if activate else "Deactivated account.")
            messages.success(request, "Account activated." if activate else "Account deactivated.")
            return redirect("accounts:user_list")
    return render(request, "accounts/user_status.html", {"form": form, "account": target, "activate": activate})
