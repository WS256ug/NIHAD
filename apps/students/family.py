from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_GET, require_http_methods
from apps.accounts.models import User
from apps.accounts.permissions import role_required
from apps.finance.models import Payment
from apps.finance.queries import balance_summary
from apps.finance.views import receipt_response, statement_context
from .forms import PortalAccessForm
from .models import Guardian, Student
from .services import set_guardian_access
from .views import attempt, form_page

PORTAL_ROLES = (User.Role.GUARDIAN, User.Role.STUDENT)


def portal_students(user):
    students = Student.objects.filter(school_id=1).select_related('school')
    if not user.is_authenticated or not user.is_active:
        return students.none()
    if user.role == User.Role.GUARDIAN:
        return students.filter(guardian_links__guardian__user=user, guardian_links__is_active=True).distinct()
    if user.role == User.Role.STUDENT:
        return students.filter(portal_user=user)
    return students.none()


def report_access_allowed(student):
    return not student.school.require_fee_clearance_for_reports or balance_summary(student)['balance'] <= 0


def student_context(student, user):
    from apps.reports.models import StudentReport
    from django.db.models import Max
    published = StudentReport.objects.filter(enrollment__student=student, status='published')
    latest = published.order_by().values('assessment_id', 'enrollment_id').annotate(latest=Max('pk')).values('latest')
    allowed = report_access_allowed(student)
    return {
        'student': student, 'enrollments': student.enrollments.select_related('academic_year', 'academic_class__section', 'stream'),
        'guardian_links': student.guardian_links.filter(is_active=True).select_related('guardian'),
        'summary': balance_summary(student), 'reports_allowed': allowed,
        'reports': published.filter(pk__in=latest).select_related('assessment__assessment_type', 'assessment__term__academic_year') if allowed else [],
        'photo_url': reverse('students:family_photo', args=[student.pk]),
        'portal_home_url': reverse('students:family_home' if user.role == User.Role.GUARDIAN else 'students:portal_home'),
    }


@role_required(User.Role.GUARDIAN)
@never_cache
@require_GET
def home(request):
    return render(request, 'students/family_home.html', {'children': portal_students(request.user)})


@role_required(*PORTAL_ROLES)
@never_cache
@require_GET
def child(request, pk):
    student = get_object_or_404(portal_students(request.user), pk=pk)
    return render(request, 'students/portal_home.html', student_context(student, request.user))


@role_required(*PORTAL_ROLES)
@never_cache
@require_GET
def fees(request, pk):
    student = get_object_or_404(portal_students(request.user), pk=pk)
    context = statement_context(student)
    context['portal_home_url'] = reverse('students:family_child', args=[pk])
    return render(request, 'finance/statement.html', context)


@role_required(*PORTAL_ROLES)
@never_cache
@require_GET
def receipt(request, pk, output='html'):
    payment = get_object_or_404(Payment.objects.filter(charge__enrollment__student__in=portal_students(request.user)).select_related('reversal', 'charge__enrollment__student'), pk=pk)
    return receipt_response(request, payment, output)


@role_required(*PORTAL_ROLES)
@never_cache
@require_GET
def photo(request, pk):
    student = get_object_or_404(portal_students(request.user), pk=pk)
    if not student.photo:
        raise Http404
    try:
        return FileResponse(student.photo.open('rb'), content_type='image/jpeg')
    except FileNotFoundError:
        raise Http404 from None


class GuardianAccessForm(PortalAccessForm):
    username = forms.CharField(max_length=150, required=False, validators=[UnicodeUsernameValidator()], help_text='Choose an individual login name, or select an existing Guardian account below.')
    existing_account = forms.ModelChoiceField(queryset=User.objects.none(), required=False)

    def __init__(self, user, *args, guardian, **kwargs):
        super().__init__(user, *args, **kwargs)
        self.fields['is_active'].label = 'Enable Guardian account'
        self.fields['existing_account'].queryset = User.objects.filter(role=User.Role.GUARDIAN, guardian_profile__isnull=True, is_staff=False)
        if guardian.user_id:
            self.fields['username'].disabled = True
            self.initial['username'] = guardian.user.username
            self.fields.pop('existing_account')

    def clean(self):
        data = super().clean()
        if not data.get('username') and not data.get('existing_account'):
            raise forms.ValidationError('Enter a new username or select an existing Guardian account.')
        return data


@role_required(User.Role.SCHOOL_ADMIN)
@never_cache
@require_http_methods(['GET', 'POST'])
@sensitive_post_parameters('new_password1', 'new_password2')
def access(request, pk):
    guardian = get_object_or_404(Guardian.objects.select_related('user'), pk=pk, school_id=1)
    user = guardian.user or User(role=User.Role.GUARDIAN, first_name=guardian.first_name, last_name=guardian.last_name)
    form = GuardianAccessForm(user, request.POST if request.method == 'POST' else None, guardian=guardian, initial={'is_active': user.is_active})
    if request.method == 'POST' and form.is_valid() and attempt(form, lambda: set_guardian_access(guardian, form.cleaned_data, request.user)):
        messages.success(request, 'Guardian account saved. Share the individual username and temporary password securely.')
        return redirect('students:guardian_detail', pk=pk)
    return form_page(request, form, f'Guardian account: {guardian}', reverse('students:guardian_detail', args=[pk]), explanation='This guardian uses their own account to see actively linked children. A password change is required at first sign-in.')
