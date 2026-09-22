from django.urls import reverse

from .permissions import can_manage_accounts, can_manage_school, dashboard_url, effective_role
from apps.students.permissions import can_manage_students, can_view_students
from apps.academics.permissions import can_view_academics
from apps.finance.permissions import can_manage_finance
from apps.promotions.services import can_manage_promotions


def account_navigation(request):
    role = effective_role(request.user)
    if role is None:
        return {}
    labels = {
        "super_admin": "Super Admin workspace", "school_admin": "School Admin workspace",
        "headteacher": "Headteacher workspace", "teacher": "Teacher workspace",
        "bursar": "Finance workspace", "student": "Student portal", "guardian": "Guardian portal",
    }
    links = [{"label": labels[role], "url": dashboard_url(request.user)}]
    if can_manage_accounts(request.user):
        links.append({"label": "Accounts", "url": reverse("accounts:user_list")})
    if can_manage_school(request.user):
        links.append({"label": "School setup", "url": reverse("schools:overview")})
    if can_view_students(request.user):
        student_link = {"label": "Students", "url": reverse("students:list")}
        if can_manage_students(request.user):
            student_link["children"] = [
                {"label": "All students", "url": reverse("students:list")},
                {"label": "Guardians", "url": reverse("students:guardian_list")},
            ]
        links.append(student_link)
    if can_view_academics(request.user):
        academic_children = [
            {"label": "Overview", "url": reverse("academics:overview")},
            {"label": "Reports", "url": reverse("reports:list")},
        ]
        if can_manage_promotions(request.user):
            academic_children.append({"label": "Promotions", "url": reverse("promotions:list")})
        links.append({"label": "Academics", "url": reverse("academics:overview"), "children": academic_children})
    if can_manage_finance(request.user):
        links.append({"label": "Finance", "url": reverse("expenses:overview")})
    if request.user.is_superuser:
        links.append({"label": "Administration", "url": reverse("admin:index")})
    for link in links:
        link["active"] = request.path == link["url"] or (link["label"] == "School setup" and request.path.startswith(link["url"]))
        if link["label"] == "Students":
            link["active"] = request.path.startswith(link["url"])
            for child in link.get("children", []):
                guardian_page = request.path.startswith(reverse("students:guardian_list"))
                child["active"] = link["active"] and (guardian_page if child["label"] == "Guardians" else not guardian_page)
        if link["label"] == "Finance":
            link["active"] = request.path.startswith((reverse("finance:overview"), reverse("expenses:overview")))
        if link["label"] == "Academics":
            for child in link["children"]:
                child["active"] = request.path.startswith(child["url"])
            link["active"] = any(child["active"] for child in link["children"])
    return {"account_navigation": links, "can_manage_accounts": can_manage_accounts(request.user), "can_manage_school": can_manage_school(request.user), "can_view_students": can_view_students(request.user), "can_manage_students": can_manage_students(request.user)}
