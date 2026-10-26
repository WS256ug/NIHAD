"""Separate recorded Islamic participation without inventing new class placements."""
from django.db import migrations


def preserve_history(apps, schema_editor):
    db = schema_editor.connection.alias
    Enrollment = apps.get_model('students', 'Enrollment')
    Mark = apps.get_model('academics', 'Mark')
    Report = apps.get_model('reports', 'StudentReport')
    Assignment = apps.get_model('academics', 'ClassTeacherAssignment')
    Submission = apps.get_model('academics', 'MarkSubmission')
    replacements = {}
    ids = set(Mark.objects.using(db).filter(assessment__report_group='islamic').values_list('enrollment_id', flat=True))
    ids.update(Report.objects.using(db).filter(assessment__report_group='islamic').values_list('enrollment_id', flat=True))
    for original in Enrollment.objects.using(db).filter(pk__in=ids, programme='main').iterator():
        fields = {field.attname: getattr(original, field.attname) for field in Enrollment._meta.concrete_fields
                  if not field.primary_key and field.name != 'programme'}
        copied = Enrollment.objects.using(db).create(programme='islamic', **fields)
        replacements[original.pk] = copied.pk
        Enrollment.objects.using(db).filter(pk=copied.pk).update(
            created_at=original.created_at, updated_at=original.updated_at)
        Mark.objects.using(db).filter(enrollment=original, assessment__report_group='islamic').update(enrollment=copied)
        # All revisions move together; stored snapshots and approval data stay untouched.
        Report.objects.using(db).filter(enrollment=original, assessment__report_group='islamic').update(enrollment=copied)
    for submission in Submission.objects.using(db).filter(assessment__report_group='islamic').iterator():
        snapshot = [[replacements.get(pk, pk), revision] for pk, revision in submission.snapshot]
        revisions = dict(snapshot)
        ids = Enrollment.objects.using(db).filter(pk__in=revisions).order_by(
            'student__last_name', 'student__first_name', 'pk').values_list('pk', flat=True)
        Submission.objects.using(db).filter(pk=submission.pk).update(snapshot=[[pk, revisions[pk]] for pk in ids])
    # Previously a class teacher covered both programmes. Preserve that explicit
    # existing access as two assignments; new allocations choose one programme.
    for original in Assignment.objects.using(db).filter(report_group='main').iterator():
        fields = {field.attname: getattr(original, field.attname) for field in Assignment._meta.concrete_fields
                  if not field.primary_key and field.name != 'report_group'}
        copied = Assignment.objects.using(db).create(report_group='islamic', **fields)
        Assignment.objects.using(db).filter(pk=copied.pk).update(
            created_at=original.created_at, updated_at=original.updated_at)


class Migration(migrations.Migration):
    dependencies = [
        ('students', '0010_remove_enrollment_students_current_enrollment_unique_and_more'),
        ('academics', '0009_remove_classteacherassignment_academics_class_teacher_scope_11_and_more'),
        ('reports', '0001_report_snapshots_and_review'),
    ]
    # Reversal cannot safely merge independently advanced programme histories.
    operations = [migrations.RunPython(preserve_history)]
