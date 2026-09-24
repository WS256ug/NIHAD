from config.dialogs import form_redirect
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import IntegrityError, OperationalError
from django.db.models import Prefetch, Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods

from apps.accounts.models import User
from apps.accounts.permissions import role_required
from apps.academics.permissions import visible_enrollments
from apps.schools.models import AcademicClass, AcademicYear, School, Section, Stream
from . import services
from .forms import AddGuardianContactForm, CloseEnrollmentForm, EnrollmentForm, GuardianForm, GuardianLinkForm, LinkStatusForm, StudentForm, StudentRegistrationForm, StudentStatusForm, selected_pk
from .models import Enrollment, Student
from .permissions import can_manage_students, manageable_guardians, visible_students


def attempt(form, operation):
    try:
        return operation()
    except ValidationError as error:
        form.add_error(None, error.messages)
    except (IntegrityError, OperationalError):
        form.add_error(None, "A record changed or the database is busy. Review your entries and try again.")
    return None


def form_page(request, form, title, cancel_url, **context):
    return render(request, "students/form.html", {"form": form, "page_title": title, "cancel_url": cancel_url, **context})


@role_required(User.Role.SCHOOL_ADMIN, User.Role.HEADTEACHER, User.Role.TEACHER)
@never_cache
@require_GET
def student_list(request):
    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "")
    records = visible_students(request.user)
    if query:
        # Every name token must match, so searching a full name works too.
        for token in query.split()[:10]:
            records = records.filter(Q(student_id__icontains=token) | Q(first_name__icontains=token) | Q(middle_name__icontains=token) | Q(last_name__icontains=token) | Q(admission_number__icontains=token))
    if status:
        records = records.filter(status=status)
    enrollment_filters = {}
    for parameter, field in (("year", "academic_year_id"), ("section", "section_id"), ("class", "academic_class_id"), ("stream", "stream_id")):
        value = request.GET.get(parameter, "")
        if value:
            enrollment_filters[field] = selected_pk(value) or 0
    if enrollment_filters:
        records = records.filter(enrollments__in=visible_enrollments(request.user).filter(**enrollment_filters)).distinct()
    enrollment_rows = visible_enrollments(request.user).filter(**enrollment_filters).select_related("academic_year", "academic_class", "stream")
    records = records.prefetch_related(Prefetch("enrollments", queryset=enrollment_rows, to_attr="listed_enrollments"))
    filters = request.GET.copy()
    filters.pop("page", None)
    return render(request, "students/student_list.html", {
        "page_obj": Paginator(records, 20).get_page(request.GET.get("page")), "query": query,
        "status_choices": Student.Status.choices,
        "selected_status": status, "filter_query": filters.urlencode(),
        "years": AcademicYear.objects.filter(school_id=1), "sections": Section.objects.filter(school_id=1),
        "classes": AcademicClass.objects.filter(section__school_id=1).select_related("section"),
        "streams": Stream.objects.filter(academic_class__section__school_id=1).select_related("academic_class__section"),
        "can_manage_students": can_manage_students(request.user),
    })


@role_required(User.Role.SCHOOL_ADMIN, User.Role.HEADTEACHER, User.Role.TEACHER)
@never_cache
@require_GET
def student_detail(request, pk):
    student = get_object_or_404(visible_students(request.user).select_related("school"), pk=pk)
    return render(request, "students/student_detail.html", {
        "student": student, "can_manage_students": can_manage_students(request.user),
        "enrollments": visible_enrollments(request.user).filter(student=student).select_related("academic_year", "section", "academic_class", "stream"),
        "guardian_links": student.guardian_links.select_related("guardian") if request.user.role != User.Role.TEACHER else [],
    })


@role_required(User.Role.SCHOOL_ADMIN, User.Role.HEADTEACHER, User.Role.TEACHER)
@never_cache
@require_GET
def student_photo(request, pk):
    student = get_object_or_404(visible_students(request.user), pk=pk)
    if not student.photo:
        raise Http404
    try:
        photo = student.photo.open("rb")
    except FileNotFoundError:
        raise Http404 from None
    response = FileResponse(photo, content_type="image/jpeg", filename=f"{student.student_id}.jpg")
    response["X-Content-Type-Options"] = "nosniff"
    return response


@role_required(User.Role.SCHOOL_ADMIN)
@never_cache
@require_http_methods(["GET", "POST"])
def student_form(request, pk=None):
    school = School.objects.first()
    if school is None:
        return redirect("schools:profile")
    student = get_object_or_404(visible_students(request.user), pk=pk) if pk else None
    form_class = StudentForm if student else StudentRegistrationForm
    form = form_class(request.POST if request.method == "POST" else None, request.FILES or None, school=school, instance=student)
    if request.method == "POST" and form.is_valid():
        saved = attempt(form, lambda: services.save_student(form, request.user))
        if saved:
            messages.success(request, "Student profile saved.")
            return form_redirect(request, "students:detail", pk=saved.pk)
    cancel = reverse("students:detail", args=[pk]) if pk else reverse("students:list")
    return form_page(request, form, "Edit student" if pk else "Register student", cancel)


@role_required(User.Role.SCHOOL_ADMIN)
@never_cache
@require_http_methods(["GET", "POST"])
def student_status(request, pk):
    student = get_object_or_404(visible_students(request.user), pk=pk)
    form = StudentStatusForm(request.POST if request.method == "POST" else None, initial={"status": student.status})
    if request.method == "POST" and form.is_valid():
        if attempt(form, lambda: services.set_student_status(student, form.cleaned_data["status"], request.user)):
            messages.success(request, "Student status updated. History is preserved.")
            return form_redirect(request, "students:detail", pk=pk)
    return form_page(request, form, f"Change status: {student.full_name}", reverse("students:detail", args=[pk]))


@role_required(User.Role.SCHOOL_ADMIN)
@never_cache
@require_GET
def guardian_list(request):
    records = manageable_guardians(request.user)
    query = request.GET.get("q", "").strip()
    for token in query.split()[:10]:
        records = records.filter(Q(first_name__icontains=token) | Q(last_name__icontains=token) | Q(email__icontains=token) | Q(phone__icontains=token))
    return render(request, "students/guardian_list.html", {"page_obj": Paginator(records, 20).get_page(request.GET.get("page")), "query": query})


@role_required(User.Role.SCHOOL_ADMIN)
@never_cache
@require_GET
def guardian_detail(request, pk):
    guardian = get_object_or_404(manageable_guardians(request.user), pk=pk)
    return render(request, "students/guardian_detail.html", {
        "guardian": guardian,
        "links": guardian.student_links.filter(student__school_id=guardian.school_id).select_related("student"),
    })


@role_required(User.Role.SCHOOL_ADMIN)
@never_cache
@require_http_methods(["GET", "POST"])
def guardian_add(request, student_pk):
    student = get_object_or_404(visible_students(request.user), pk=student_pk)
    form = AddGuardianContactForm(request.POST if request.method == "POST" else None, student=student)
    if request.method == "POST" and form.is_valid():
        if attempt(form, lambda: services.add_guardian_contact(student, form.cleaned_data, request.user)):
            messages.success(request, "Guardian contact added.")
            return form_redirect(request, "students:detail", pk=student_pk)
    return form_page(request, form, f"Add guardian contact: {student.full_name}", reverse("students:detail", args=[student_pk]))


@role_required(User.Role.SCHOOL_ADMIN)
@never_cache
@require_http_methods(["GET", "POST"])
def guardian_form(request, pk):
    school = School.objects.first()
    if school is None:
        return redirect("schools:profile")
    guardian = get_object_or_404(manageable_guardians(request.user), pk=pk)
    form = GuardianForm(request.POST if request.method == "POST" else None, school=school, instance=guardian)
    if request.method == "POST" and form.is_valid():
        saved = attempt(form, lambda: services.save_guardian(form, request.user))
        if saved:
            messages.success(request, "Guardian contact details saved.")
            return form_redirect(request, "students:guardian_detail", pk=saved.pk)
    cancel = reverse("students:guardian_detail", args=[pk]) if pk else reverse("students:guardian_list")
    return form_page(request, form, "Edit guardian contacts", cancel)


@role_required(User.Role.SCHOOL_ADMIN)
@never_cache
@require_http_methods(["GET", "POST"])
def guardian_link(request, student_pk, pk=None):
    student = get_object_or_404(visible_students(request.user), pk=student_pk)
    link = get_object_or_404(student.guardian_links, pk=pk) if pk else None
    form = GuardianLinkForm(request.POST if request.method == "POST" else None, student=student, instance=link)
    if request.method == "POST" and form.is_valid():
        if attempt(form, lambda: services.save_link(form, request.user)):
            messages.success(request, "Guardian relationship saved.")
            return form_redirect(request, "students:detail", pk=student_pk)
    return form_page(request, form, f"Guardian link: {student.full_name}", reverse("students:detail", args=[student_pk]))


@role_required(User.Role.SCHOOL_ADMIN)
@never_cache
@require_http_methods(["GET", "POST"])
def link_status(request, student_pk, pk, active):
    student = get_object_or_404(visible_students(request.user), pk=student_pk)
    link = get_object_or_404(student.guardian_links, pk=pk)
    form = LinkStatusForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        if attempt(form, lambda: services.set_link_active(link, active, request.user)):
            messages.success(request, "Guardian link activated." if active else "Guardian link deactivated.")
            return form_redirect(request, "students:detail", pk=student_pk)
    title = f"{'Activate' if active else 'Deactivate'} guardian link: {link.guardian} / {student.full_name}"
    return form_page(request, form, title, reverse("students:detail", args=[student_pk]), explanation="Deactivating a link also clears its primary and emergency contact flags. The relationship record is retained.")


@role_required(User.Role.SCHOOL_ADMIN)
@never_cache
@require_http_methods(["GET", "POST"])
def enrollment_create(request, student_pk):
    student = get_object_or_404(visible_students(request.user).select_related("school"), pk=student_pk)
    form = EnrollmentForm(request.POST if request.method == "POST" else None, student=student)
    form.fields["academic_class"].widget.attrs.update({"hx-get": reverse("students:stream_options"), "hx-target": "#id_stream", "hx-swap": "innerHTML", "hx-indicator": "#form-loading", "hx-disabled-elt": "#id_stream"})
    if request.method == "POST" and form.is_valid():
        if attempt(form, lambda: services.enroll_student(form, request.user)):
            messages.success(request, "Enrollment added. Earlier records are preserved.")
            return form_redirect(request, "students:detail", pk=student_pk)
    return form_page(request, form, f"Enroll {student.full_name}", reverse("students:detail", args=[student_pk]), explanation="The year, class, stream and enrollment date are permanent once saved. Close an enrollment before recording a later placement in the same year.")


@role_required(User.Role.SCHOOL_ADMIN)
@never_cache
@require_GET
def stream_options(request):
    streams = Stream.objects.filter(academic_class_id=selected_pk(request.GET.get("academic_class")), academic_class__section__school_id=1, academic_class__section__is_active=True, academic_class__is_active=True, is_active=True)
    return render(request, "students/stream_options.html", {"streams": streams})


@role_required(User.Role.SCHOOL_ADMIN)
@never_cache
@require_http_methods(["GET", "POST"])
def enrollment_close(request, student_pk, pk):
    student = get_object_or_404(visible_students(request.user), pk=student_pk)
    enrollment = get_object_or_404(student.enrollments.select_related("academic_year", "academic_class__section"), pk=pk)
    form = CloseEnrollmentForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        if attempt(form, lambda: services.close_enrollment(enrollment, form.cleaned_data["status"], form.cleaned_data["completion_date"], request.user)):
            messages.success(request, "Enrollment closed. History is preserved.")
            return form_redirect(request, "students:detail", pk=student_pk)
    return form_page(request, form, f"Close enrollment: {student.full_name}", reverse("students:detail", args=[student_pk]), explanation=f"{enrollment.academic_year} / {enrollment.academic_class}. Completed records cannot be reopened or reassigned.")
