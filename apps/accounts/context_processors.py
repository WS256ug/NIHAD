from django.urls import reverse

from .permissions import can_manage_accounts, dashboard_url, effective_role


def account_navigation(request):
    role = effective_role(request.user)
    if role is None:
        return {}
    labels = {
        "super_admin": "Super Admin workspace", "school_admin": "School Admin workspace",
        "headteacher": "Headteacher workspace", "teacher": "Teacher workspace",
        "bursar": "Finance workspace", "guardian": "Guardian workspace",
    }
    links = [{"label": labels[role], "url": dashboard_url(request.user)}]
    if can_manage_accounts(request.user):
        links.append({"label": "Accounts", "url": reverse("accounts:user_list")})
    links.append({"label": "My account", "url": reverse("accounts:profile")})
    if request.user.is_superuser:
        links.append({"label": "Administration", "url": reverse("admin:index")})
    for link in links:
        link["active"] = request.path == link["url"]
    return {"account_navigation": links, "can_manage_accounts": can_manage_accounts(request.user)}
