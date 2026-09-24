from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from apps.accounts.models import User
from apps.accounts.permissions import has_role
from apps.academics.grading import calculate_results, competition_positions
from apps.academics.models import Assessment, TeachingAssignment
from apps.academics.permissions import assessment_enrollments
from apps.academics.services import require_manager
from apps.schools.services import lock_school, write_record
from .models import StudentReport
from .permissions import can_comment


def expected_subjects(assessment, enrollment):
    # Include historical assignments so deactivating an assignment cannot hide a missing result.
    return set(TeachingAssignment.objects.filter(academic_year_id=enrollment.academic_year_id, academic_class_id=enrollment.academic_class_id).filter(Q(term__isnull=True) | Q(term_id=assessment.term_id)).filter(Q(stream__isnull=True) | Q(stream_id=enrollment.stream_id)).values_list('subject_id', flat=True))


@transaction.atomic
def generate_reports(assessment, actor):
    require_manager(actor)
    school = lock_school()
    assessment = Assessment.objects.select_for_update().get(pk=assessment.pk)
    if assessment.status != 'closed':
        raise ValidationError('Close marks entry before generating reports.')
    if assessment.requires_mark_review:
        from apps.academics.mark_sheets import require_approved_sheets
        require_approved_sheets(assessment)
    if not assessment.grading_scheme_id:
        from apps.academics.section_grades import assessment_grades
        assessment.grading_scheme = assessment_grades(assessment.academic_class.section, actor)
        assessment = write_record(assessment, actor, 'Automatically selected section grades.', update_fields=['grading_scheme'])
    if assessment.reports.filter(is_current=True).exclude(status='draft').exists():
        raise ValidationError('Reports are under review or published. Use the assessment correction workflow.')
    enrollments = list(assessment_enrollments(assessment, actor))
    if not enrollments:
        raise ValidationError('There are no eligible students for this assessment.')
    results = {}
    for enrollment in enrollments:
        marks = list(assessment.marks.filter(enrollment=enrollment).select_related('subject', 'level'))
        expected = expected_subjects(assessment, enrollment)
        if not expected or {mark.subject_id for mark in marks} != expected:
            raise ValidationError(f'Complete all assigned subject marks for {enrollment.student.student_id} before generating reports.')
        results[enrollment.pk] = calculate_results(assessment.grading_scheme, marks, assessment.maximum_score)
    rank = school.enable_ranking and assessment.grading_scheme.mode == 'numeric'
    positions = competition_positions(results) if rank else {}
    reports = []
    for enrollment in enrollments:
        result = results[enrollment.pk]
        snapshot = {
            'schema_version': 1, 'school': school.name, 'motto': school.motto,
            'school_address': school.address, 'school_phone': school.phone,
            'student': enrollment.student.full_name, 'registration_number': enrollment.student.student_id,
            'section': enrollment.section.name, 'class': enrollment.academic_class.name,
            'stream': enrollment.stream.name if enrollment.stream_id else '',
            'year': assessment.term.academic_year.name, 'term': assessment.term.name,
            'assessment': assessment.assessment_type.name, 'date': assessment.date.isoformat(),
            'maximum_score': str(assessment.maximum_score), 'generated_at': timezone.now().isoformat(),
            'position': positions.get(enrollment.pk), 'cohort_size': len(positions) if rank else None,
            **result,
        }
        report = assessment.reports.filter(enrollment=enrollment, is_current=True).first() or StudentReport(assessment=assessment, enrollment=enrollment)
        report.snapshot = snapshot
        report.teacher_comment = report.headteacher_comment = ''
        reports.append(write_record(report, actor, 'Generated report snapshot from completed marks.'))
    return reports


def current_report(report):
    report = StudentReport.objects.select_for_update().get(pk=report.pk)
    if not report.is_current:
        raise ValidationError('This report has a newer revision. Open the current report.')
    if report.assessment.status != 'closed':
        raise ValidationError('Close the assessment before continuing report review.')
    return report


@transaction.atomic
def teacher_comment(report, comment, actor):
    lock_school()
    report = current_report(report)
    if not can_comment(actor, report):
        raise PermissionDenied
    report.teacher_comment = comment.strip()
    report.status = 'review'
    return write_record(report, actor, 'Submitted class-teacher comment for headteacher review.')


@transaction.atomic
def review_report(report, comment, approve, actor):
    if not has_role(actor, User.Role.HEADTEACHER):
        raise PermissionDenied
    lock_school()
    report = current_report(report)
    if report.status != 'review' or not comment.strip():
        raise ValidationError('Review requires a submitted report and a headteacher comment.')
    report.headteacher_comment = comment.strip()
    report.status = 'approved' if approve else 'draft'
    return write_record(report, actor, 'Approved report.' if approve else 'Returned report for correction.')


@transaction.atomic
def publish_report(report, actor):
    require_manager(actor)
    lock_school()
    report = current_report(report)
    if report.status != 'approved':
        raise ValidationError('Only an approved report can be published.')
    report.status = 'published'
    report.published_at = timezone.now()
    return write_record(report, actor, 'Published approved report.')


@transaction.atomic
def begin_correction(assessment, reason, actor):
    require_manager(actor)
    lock_school()
    assessment = Assessment.objects.select_for_update().get(pk=assessment.pk)
    reports = list(assessment.reports.filter(is_current=True))
    if assessment.status != 'closed' or not reports or not reason.strip():
        raise ValidationError('A closed assessment, existing reports and a correction reason are required.')
    for previous in reports:
        previous.is_current = False
        write_record(previous, actor, 'Opened a new correction revision.', update_fields=['is_current'])
        write_record(StudentReport(assessment=assessment, enrollment=previous.enrollment, version=previous.version + 1, previous=previous, correction_reason=reason.strip()), actor, 'Created report correction revision.')
    assessment.status = 'open'
    write_record(assessment, actor, 'Reopened assessment for an audited report correction.', update_fields=['status'])
    from apps.academics.mark_sheets import return_sheets_for_correction
    return_sheets_for_correction(assessment, reason.strip(), actor)
    return assessment
