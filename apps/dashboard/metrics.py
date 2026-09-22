from decimal import Decimal
from django.db.models import Count, Q
from django.urls import reverse
from apps.accounts.models import User
from apps.academics.models import Assessment, ClassTeacherAssignment, Mark, Teacher
from apps.academics.permissions import assessment_assignments, assessment_enrollments, teacher_assignments, visible_assessments, visible_enrollments
from apps.expenses.services import financial_summary
from apps.finance.models import Payment
from apps.promotions.models import PromotionBatch
from apps.reports.models import StudentReport
from apps.schools.models import AcademicClass, School
from apps.students.models import Enrollment, Student


def pending_comments(user):
    scope = Q(pk__in=[])
    for assignment in teacher_assignments(user, ClassTeacherAssignment):
        match = Q(assessment__academic_class_id=assignment.academic_class_id, assessment__term__academic_year_id=assignment.academic_year_id)
        if assignment.term_id:
            match &= Q(assessment__term_id=assignment.term_id)
        if assignment.stream_id:
            match &= Q(enrollment__stream_id=assignment.stream_id)
        scope |= match
    return StudentReport.objects.filter(scope, is_current=True, status='draft').exclude(snapshot={})


def dashboard_metrics(user, role):
    school = School.objects.select_related('current_academic_year', 'current_term').first()
    result = {'school_period': school, 'metrics': [], 'tasks': []}
    cards = result['metrics']
    def card(label, value, url, description='Current records', progress=None):
        cards.append({'label': label, 'value': value, 'url': url, 'description': description, 'progress': progress})
    if role in (User.Role.SUPER_ADMIN, User.Role.SCHOOL_ADMIN, User.Role.HEADTEACHER):
        card('Students', Student.objects.filter(school_id=1).count(), reverse('students:list'))
        card('Active classes', AcademicClass.objects.filter(section__school_id=1, is_active=True).count(), reverse('academics:overview'))
        card('Active teachers', Teacher.objects.filter(school_id=1, employment_status='active', user__is_active=True).count(), reverse('academics:record_list', args=['teachers']))
        reports = StudentReport.objects.filter(enrollment__student__school_id=1, is_current=True)
        card('Reports awaiting review', reports.filter(status='review').count(), reverse('reports:list') + '?status=review')
        card('Approved reports', reports.filter(status='approved').count(), reverse('reports:list') + '?status=approved')
        card('Draft promotion batches', PromotionBatch.objects.filter(source_year__school_id=1, status='draft').count(), reverse('promotions:list'))
        enrollments = Enrollment.objects.filter(student__school_id=1, status='current')
        if school and school.current_academic_year_id:
            enrollments = enrollments.filter(academic_year_id=school.current_academic_year_id)
        result['section_counts'] = enrollments.values('section__name').annotate(total=Count('student_id', distinct=True)).order_by('section__name')
        published = reports.filter(status='published')
        if school and school.current_term_id:
            published = published.filter(assessment__term_id=school.current_term_id)
        averages = [Decimal(snapshot['average']) for snapshot in published.values_list('snapshot', flat=True).iterator() if snapshot.get('average') is not None]
        if averages:
            average = sum(averages) / len(averages)
            card('Mean published report average', f'{average:.2f}%', reverse('reports:list') + '?status=published', description='Current term' if school and school.current_term_id else 'All published periods', progress=f'{average:.2f}')
    if role == User.Role.TEACHER:
        assignments = teacher_assignments(user)
        card('Assigned classes', assignments.values('academic_class_id', 'stream_id').distinct().count(), reverse('academics:record_list', args=['teaching']))
        card('Assigned subjects', assignments.values('subject_id').distinct().count(), reverse('academics:record_list', args=['subjects']))
        card('Assigned students', visible_enrollments(user).values('student_id').distinct().count(), reverse('students:list'))
        open_assessments = visible_assessments(user).filter(status='open')
        card('Open assessments', open_assessments.count(), reverse('academics:record_list', args=['assessments']))
        pending = 0
        for assessment in open_assessments:
            missing = 0
            for assignment in assessment_assignments(assessment, user):
                enrollments = assessment_enrollments(assessment, user, assignment.subject)
                if assignment.stream_id:
                    enrollments = enrollments.filter(stream_id=assignment.stream_id)
                entered = Mark.objects.filter(assessment=assessment, subject=assignment.subject).values('enrollment_id')
                missing += enrollments.exclude(pk__in=entered).count()
            pending += missing
            if missing:
                result['tasks'].append({'label': f'{assessment}: {missing} marks to enter', 'url': reverse('academics:marks', args=[assessment.pk])})
        card('Marks to enter', pending, reverse('academics:record_list', args=['assessments']))
        comments = pending_comments(user)
        card('Class-teacher comments due', comments.count(), reverse('reports:list') + '?status=draft')
        for report in comments.select_related('enrollment__student', 'assessment__assessment_type')[:8]:
            result['tasks'].append({'label': f'Comment: {report.enrollment.student.full_name}', 'url': reverse('reports:comment', args=[report.pk])})
    if role in (User.Role.SUPER_ADMIN, User.Role.SCHOOL_ADMIN, User.Role.BURSAR):
        result['finance_summary'] = financial_summary()
        currency = school.currency_code if school else ''
        for label, key in [('Fees collected', 'paid'), ('Outstanding fees', 'balance'), ('Expenses', 'expenses'), ('Surplus / deficit', 'net')]:
            card(label, f"{currency} {result['finance_summary'][key]:,.2f}", reverse('expenses:overview'), description='All recorded periods')
        result['recent_payments'] = Payment.objects.filter(charge__enrollment__student__school_id=1).select_related('reversal').order_by('-created_at')[:8]
    return result
