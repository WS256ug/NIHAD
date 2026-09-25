from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone
from apps.accounts.models import User
from apps.accounts.permissions import has_role
from apps.schools.services import lock_school, write_record
from apps.students.models import Enrollment, Student
from .models import PromotionBatch, PromotionDecision, higher_classes


def can_manage_promotions(actor):
    return has_role(actor, User.Role.SCHOOL_ADMIN, User.Role.HEADTEACHER)


def require_manager(actor):
    if not can_manage_promotions(actor):
        raise PermissionDenied


def eligible_enrollments(batch):
    records = Enrollment.objects.filter(student__school_id=1, academic_year_id=batch.source_year_id, academic_class_id=batch.source_class_id, status='current')
    if batch.source_stream_id:
        records = records.filter(stream_id=batch.source_stream_id)
    return records.select_related('student', 'academic_year', 'academic_class__section', 'stream')


def destination(batch, enrollment, decision):
    if decision in ('promoted', 'probation', 'repeating'):
        if not batch.destination_year_id or not batch.enrollment_date:
            raise ValidationError('Promotion and repetition require a destination year and enrollment date.')
        classroom = enrollment.academic_class if decision == 'repeating' else batch.destination_class
        stream = enrollment.stream if decision == 'repeating' else batch.destination_stream
        if batch.destination_year.start_date <= enrollment.academic_year.end_date:
            raise ValidationError('Choose a destination year after the source year.')
        if classroom is None or (decision in ('promoted', 'probation') and not type(classroom).objects.filter(pk=classroom.pk).filter(higher_classes(enrollment.academic_class)).exists()):
            raise ValidationError('Choose a higher destination class for promotion, or choose Try Again.')
        return classroom, stream
    return None, None


@transaction.atomic
def create_batch(form, actor):
    require_manager(actor)
    lock_school()
    return write_record(form.save(commit=False), actor, 'Created draft promotion batch.')


@transaction.atomic
def save_decisions(batch, rows, revision, actor):
    require_manager(actor)
    lock_school()
    batch = PromotionBatch.objects.select_for_update().get(pk=batch.pk)
    if batch.status != 'draft' or batch.revision != revision:
        raise ValidationError('This batch changed in another request. Reload it before editing.')
    eligible = {row.pk: row for row in eligible_enrollments(batch)}
    seen = set()
    for row in rows:
        enrollment_id = row['enrollment'].pk
        if enrollment_id not in eligible or enrollment_id in seen:
            raise ValidationError('One or more student selections are invalid or no longer current.')
        seen.add(enrollment_id)
        enrollment = eligible[enrollment_id]
        if row.get('selected'):
            destination(batch, enrollment, row['decision'])
        record = batch.decisions.filter(enrollment=enrollment).first() or PromotionDecision(batch=batch, enrollment=enrollment)
        record.selected = row.get('selected', False)
        record.decision = row['decision']
        record.notes = row.get('notes', '')
        write_record(record, actor, 'Saved draft promotion decision.')
    # Omitted rows cannot remain silently selected after a forged/truncated formset.
    for record in batch.decisions.filter(selected=True).exclude(enrollment_id__in=seen):
        record.selected = False
        write_record(record, actor, 'Removed omitted draft selection.', update_fields=['selected'])
    batch.revision += 1
    return write_record(batch, actor, 'Saved batch selections for preview.', update_fields=['revision'])


@transaction.atomic
def confirm_batch(batch, revision, actor):
    require_manager(actor)
    lock_school()
    batch = PromotionBatch.objects.select_for_update().get(pk=batch.pk)
    if batch.status == 'confirmed':
        return batch
    if batch.revision != revision:
        raise ValidationError('This batch changed after the preview. Review the latest decisions before confirming.')
    batch.full_clean()
    decisions = list(batch.decisions.filter(selected=True).select_related('enrollment__student', 'enrollment__academic_class__section', 'enrollment__stream'))
    if not decisions:
        raise ValidationError('Select at least one student before confirming.')
    eligible = {row.pk: row for row in eligible_enrollments(batch)}
    for decision in decisions:
        source = eligible.get(decision.enrollment_id)
        if source is None:
            raise ValidationError('An enrollment is no longer current. No decisions were applied.')
        classroom, stream = destination(batch, source, decision.decision)
        student = Student.objects.select_for_update().get(pk=source.student_id)
        status = 'promoted' if decision.decision == 'probation' else decision.decision
        source.status, source.completion_date = status, batch.completion_date
        write_record(source, actor, 'Closed source enrollment through promotion batch.', update_fields=['status', 'completion_date'])
        student.status = status
        write_record(student, actor, 'Updated student status through promotion batch.', update_fields=['status'])
        if classroom:
            created = Enrollment(student=student, academic_year=batch.destination_year, section=classroom.section, academic_class=classroom, stream=stream, enrollment_date=batch.enrollment_date)
            decision.new_enrollment = write_record(created, actor, 'Created next-year enrollment; source history retained.')
        decision.snapshot = {'student': student.full_name, 'registration_number': student.student_id, 'source_year': source.academic_year.name, 'source_class': source.academic_class.name, 'source_stream': source.stream.name if source.stream_id else '', 'decision': decision.get_decision_display(), 'destination_year': batch.destination_year.name if classroom else '', 'destination_class': classroom.name if classroom else '', 'destination_stream': stream.name if stream else ''}
        write_record(decision, actor, 'Applied promotion decision and stored history snapshot.', update_fields=['new_enrollment', 'snapshot'])
    batch.status, batch.confirmed_at = 'confirmed', timezone.now()
    return write_record(batch, actor, 'Confirmed promotion batch atomically.', update_fields=['status', 'confirmed_at'])
