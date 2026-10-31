from pathlib import Path
exec(Path('tmp/implement_nursery.py').read_text().split("m='apps/academics/models.py'")[0])
edit('apps/academics/grading.py', 'if mark.assessment.nursery_progress:', 'if scheme.mode == "descriptive" and mark.assessment.nursery_progress:')
f='apps/academics/forms.py'
edit(f,'class AssessmentForm(forms.ModelForm):','''class AssessmentForm(forms.ModelForm):
    nursery_scheme = forms.ModelChoiceField(queryset=GradingScheme.objects.none(), required=False, label="Nursery progress levels", help_text="Choose a descriptive grading scheme when enabling nursery progress reports. Other exams keep their section grades.")''')
edit(f,'"nursery_progress", "grading_scheme",','"nursery_progress",')
edit(f,'self.fields["grading_scheme"].queryset = GradingScheme.objects.filter(section__school=school, is_active=True)', 'self.fields["nursery_scheme"].queryset = GradingScheme.objects.filter(section__school=school, is_active=True, mode="descriptive")\n        self.initial["nursery_scheme"] = self.instance.grading_scheme_id if self.instance.nursery_progress else None')
edit(f,'        self.fields["grading_scheme"].help_text = "Optional override; choose descriptive levels for Baby and Middle progress reports."\n','')
edit(f,'self.fields["grading_scheme"].disabled = True','self.fields["nursery_scheme"].disabled = True')
edit(f,'scheme = data.get("grading_scheme") or self.instance.grading_scheme or current_scheme(academic_class.section)\n            data["grading_scheme"] = scheme if scheme and scheme.is_active else None\n            self.instance.grading_scheme = data["grading_scheme"]','scheme = (data.get("nursery_scheme") if data.get("nursery_progress") else None) or self.instance.grading_scheme or current_scheme(academic_class.section)\n            self.instance.grading_scheme = scheme if scheme and scheme.is_active else None')
edit('apps/academics/services.py','scheme = record.grading_scheme or current_scheme(record.academic_class.section)', 'scheme = (record.grading_scheme if record.nursery_progress else None) or current_scheme(record.academic_class.section)')
edit('apps/academics/marks.py','"completed": len(marks),', '"completed": sum(1 for mark in marks.values() if not assessment.nursery_progress or mark.is_absent or mark.observation.strip()),')
