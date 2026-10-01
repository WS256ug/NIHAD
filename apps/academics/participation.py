"""Assessment rosters, retaining participation for historical corrections."""
from django.db.models import Q
from apps.students.models import Enrollment, Student
from .models import ReportGroup


def eligible_enrollments(assessment):
    records = Enrollment.objects.filter(
        student__school_id=assessment.term.academic_year.school_id,
        academic_year_id=assessment.term.academic_year_id,
        academic_class_id=assessment.academic_class_id,
        enrollment_date__lte=assessment.date,
    ).filter(Q(completion_date__isnull=True) | Q(completion_date__gte=assessment.date))
    if assessment.stream_id:
        records = records.filter(stream_id=assessment.stream_id)
    if assessment.report_group == ReportGroup.ISLAMIC:
        # A later religion edit must not erase existing academic history.
        records = records.filter(
            Q(student__religion=Student.Religion.MOSLEM)
            | Q(pk__in=assessment.marks.values("enrollment_id"))
            | Q(pk__in=assessment.reports.values("enrollment_id"))
        )
    return records
