from config.dialogs import form_redirect
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Max, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods
from apps.accounts.models import User
from apps.accounts.permissions import has_role, role_required
from apps.academics.permissions import visible_assessments
from apps.schools.forms import ConfigurationStatusForm
from apps.students.views import attempt, form_page
from . import services
from .forms import CorrectionForm, ReviewForm, TeacherCommentForm
from .models import StudentReport
from .pdf import report_pdf
from .permissions import can_comment, visible_reports

READ_ROLES = (User.Role.SCHOOL_ADMIN, User.Role.HEADTEACHER, User.Role.TEACHER)
REPORT_READ_ROLES = (*READ_ROLES, User.Role.GUARDIAN, User.Role.STUDENT)


@role_required(*REPORT_READ_ROLES)
@never_cache
@require_GET
def report_list(request):
    records = visible_reports(request.user)
    if request.user.role in (User.Role.GUARDIAN, User.Role.STUDENT):
        from apps.finance.queries import student_balances
        from apps.schools.models import School
        school = School.objects.first()
        if school and school.require_fee_clearance_for_reports:
            records = records.filter(enrollment__student__in=student_balances().filter(balance__lte=0))
        latest = records.order_by().values('assessment_id', 'enrollment_id').annotate(latest=Max('pk')).values('latest')
        records = records.filter(pk__in=latest)
    else:
        records = records.filter(is_current=True)
    status = request.GET.get('status', '')
    if status in StudentReport.Status.values:
        records = records.filter(status=status)
    query = request.GET.get('q', '').strip()
    for token in query.split()[:10]:
        records = records.filter(Q(enrollment__student__student_id__icontains=token) | Q(enrollment__student__first_name__icontains=token) | Q(enrollment__student__last_name__icontains=token))
    return render(request, 'reports/list.html', {'page_obj': Paginator(records, 30).get_page(request.GET.get('page')), 'query': query, 'selected_status': status, 'statuses': StudentReport.Status.choices})


@role_required(*REPORT_READ_ROLES)
@never_cache
@require_GET
def detail(request, pk, output='html'):
    report = get_object_or_404(visible_reports(request.user), pk=pk)
    portal = request.user.role in (User.Role.GUARDIAN, User.Role.STUDENT)
    if portal:
        from apps.students.family import report_access_allowed
        if not report_access_allowed(report.enrollment.student):
            raise PermissionDenied('Fee clearance is required to view this report. Fees and payment history remain available in your portal.')
    if output == 'pdf':
        if not report.snapshot:
            return HttpResponse('Generate this revision before downloading it.', status=409)
        response = HttpResponse(report_pdf(report), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="report-{report.enrollment.student.student_id}-v{report.version}.pdf"'
        return response
    return render(request, 'reports/detail.html', {
        'report': report, 'data': report.snapshot, 'print_view': output == 'print',
        'can_comment': can_comment(request.user, report),
        'can_review': has_role(request.user, User.Role.HEADTEACHER) and report.is_current and report.status == 'review',
        'can_publish': has_role(request.user, User.Role.SCHOOL_ADMIN) and report.is_current and report.status == 'approved',
        'versions': visible_reports(request.user).filter(assessment=report.assessment, enrollment=report.enrollment),
        'portal_view': portal,
    })


@role_required(User.Role.SCHOOL_ADMIN)
@never_cache
@require_http_methods(['GET', 'POST'])
def assessment_action(request, pk, action):
    assessment = get_object_or_404(visible_assessments(request.user), pk=pk)
    form = (CorrectionForm if action == 'correct' else ConfigurationStatusForm)(request.POST if request.method == 'POST' else None)
    if request.method == 'POST' and form.is_valid():
        operation = (lambda: services.begin_correction(assessment, form.cleaned_data['reason'], request.user)) if action == 'correct' else (lambda: services.generate_reports(assessment, request.user))
        if attempt(form, operation):
            messages.success(request, 'Correction revision opened.' if action == 'correct' else 'Reports generated. Class teachers can now add comments.')
            return form_redirect(request, 'academics:marks', pk=pk) if action == 'correct' else form_redirect(request, 'reports:list')
    title = 'Open report correction' if action == 'correct' else 'Generate assessment reports'
    return form_page(request, form, title, reverse('academics:marks', args=[pk]), explanation=f'{assessment}. All assigned subject marks must be complete. Published versions are preserved.')


@role_required(*READ_ROLES)
@never_cache
@require_http_methods(['GET', 'POST'])
def report_action(request, pk, action):
    report = get_object_or_404(visible_reports(request.user), pk=pk)
    if action == 'comment':
        if not can_comment(request.user, report):
            raise PermissionDenied
        form_type, title = TeacherCommentForm, 'Class-teacher comment'
    elif action == 'review':
        if not has_role(request.user, User.Role.HEADTEACHER):
            raise PermissionDenied
        form_type, title = ReviewForm, 'Headteacher review'
    else:
        if not has_role(request.user, User.Role.SCHOOL_ADMIN):
            raise PermissionDenied
        form_type, title = ConfigurationStatusForm, 'Publish approved report'
    form = form_type(request.POST if request.method == 'POST' else None)
    if request.method == 'POST' and form.is_valid():
        if action == 'comment':
            operation = lambda: services.teacher_comment(report, form.cleaned_data['comment'], request.user)
        elif action == 'review':
            operation = lambda: services.review_report(report, form.cleaned_data['comment'], form.cleaned_data['decision'] == 'approve', request.user)
        else:
            operation = lambda: services.publish_report(report, request.user)
        if attempt(form, operation):
            messages.success(request, 'Report updated.')
            return form_redirect(request, 'reports:detail', pk=pk)
    return form_page(request, form, title, reverse('reports:detail', args=[pk]), explanation=str(report))
