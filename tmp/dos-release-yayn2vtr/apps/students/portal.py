from config.dialogs import form_redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_GET, require_http_methods

from apps.accounts.forms import StudentSignInForm
from apps.accounts.models import User
from apps.accounts.permissions import role_required
from apps.accounts.views import SignInView
from .forms import PortalAccessForm
from .models import Student
from .permissions import visible_students
from .services import set_portal_access
from .views import attempt, form_page
from .family import student_context


class PortalSignInView(SignInView):
    authentication_form = StudentSignInForm
    template_name = "students/portal_login.html"


def portal_student(request):
    if request.user.role != User.Role.STUDENT:
        raise PermissionDenied
    return get_object_or_404(Student.objects.select_related("school"), portal_user=request.user, school_id=1)


@login_required(login_url='students:portal_login')
@role_required(User.Role.STUDENT)
@never_cache
@require_GET
def home(request):
    student = portal_student(request)
    return render(request, "students/portal_home.html", student_context(student, request.user))


@role_required(User.Role.STUDENT)
@never_cache
@require_GET
def photo(request):
    student = portal_student(request)
    if not student.photo:
        raise Http404
    try:
        return FileResponse(student.photo.open("rb"), content_type="image/jpeg")
    except FileNotFoundError:
        raise Http404 from None


@role_required(User.Role.SCHOOL_ADMIN)
@never_cache
@require_http_methods(["GET", "POST"])
@sensitive_post_parameters("new_password1", "new_password2")
def access(request, pk):
    student = get_object_or_404(visible_students(request.user).select_related("portal_user"), pk=pk)
    user = student.portal_user or User(username=student.student_id, first_name=student.first_name, last_name=student.last_name, role=User.Role.STUDENT)
    form = PortalAccessForm(user, request.POST if request.method == "POST" else None, initial={"is_active": user.is_active})
    if request.method == "POST" and form.is_valid():
        if attempt(form, lambda: set_portal_access(student, form.cleaned_data["new_password1"], form.cleaned_data["is_active"], request.user)):
            messages.success(request, "Portal access saved. The guardian must change the temporary password on first sign-in.")
            return form_redirect(request, "students:detail", pk=pk)
    return form_page(request, form, f"Student portal access: {student.student_id}", reverse("students:detail", args=[pk]), explanation="The guardian signs in with this student registration number and password. Setting a new password invalidates existing sessions.")
