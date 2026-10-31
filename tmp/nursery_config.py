from pathlib import Path
exec(Path('tmp/implement_nursery.py').read_text().split("m='apps/academics/models.py'")[0])
edit('apps/academics/models.py','class GradingScheme(AuditedModel):','''class GradingScheme(AuditedModel):
    nursery_only = models.BooleanField(default=False, help_text="Available for nursery progress exams without replacing default section grades.")''')
edit('apps/academics/section_grades.py','GradingScheme.objects.filter(section=section).order_by', 'GradingScheme.objects.filter(section=section, nursery_only=False).order_by')
edit('apps/academics/section_grades.py','GradingScheme.objects.filter(section_id=OuterRef("scheme__section_id")).order_by', 'GradingScheme.objects.filter(section_id=OuterRef("scheme__section_id"), nursery_only=False).order_by')
edit('apps/academics/services.py','record.grading_scheme = previous.grading_scheme if previous and previous.grading_scheme_id else (scheme if scheme and scheme.is_active else None)', 'record.grading_scheme = (scheme if scheme and scheme.is_active else None) if record.nursery_progress else (previous.grading_scheme if previous and previous.grading_scheme_id else (scheme if scheme and scheme.is_active else None))')
edit('apps/reports/comments.py',"!= 'numeric'  or", "!= 'numeric' or")
edit('apps/reports/permissions.py',"    if not report.is_current or report.status != 'draft' or not report.snapshot:","    if report.snapshot.get('nursery_progress'):\n        return False\n    if not report.is_current or report.status != 'draft' or not report.snapshot:")
edit('apps/reports/views.py','    if request.method == \'POST\' and form.is_valid():\n        if action == \'comment\':', '''    if action == 'review' and report.snapshot.get('nursery_progress'):
        form.fields['decision'].choices = [('approve', 'Approve report')]
        form.fields['decision'].help_text = 'For observation corrections, ask a School Admin to reopen this exam using report correction.'
    if request.method == 'POST' and form.is_valid():
        if action == 'comment':''')
