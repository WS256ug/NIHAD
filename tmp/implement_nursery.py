from pathlib import Path

def edit(path, old, new):
 p=Path(path); s=p.read_text(encoding='utf-8'); assert old in s,(path,old); p.write_text(s.replace(old,new),encoding='utf-8')
m='apps/academics/models.py'
edit(m,'class Subject(AuditedModel):','''class Subject(AuditedModel):
    illustration = models.CharField(max_length=12, blank=True, choices=[
        ("social", "Sharing and play"), ("environment", "Home and environment"),
        ("hygiene", "Hand washing"), ("numbers", "Counting blocks"),
        ("language", "Reading"), ("oral", "Conversation"),
        ("writing", "Drawing"), ("physical", "Ball games"),
    ], help_text="Optional nursery report illustration.")''')
edit(m,'class Assessment(AuditedModel):','''class Assessment(AuditedModel):
    nursery_progress = models.BooleanField(default=False, verbose_name="Nursery progress report", help_text="Use progress levels and teacher observations entered through the exam. Select a descriptive grading scheme.")''')
edit(m,'        if self.set_one_weight is not None', '''        if self.nursery_progress and (not self.grading_scheme_id or self.grading_scheme.mode != "descriptive"):
            raise ValidationError("Nursery progress reports require a descriptive grading scheme.")
        if self.set_one_weight is not None''')
edit(m,'            previous = Assessment.objects.get(pk=self.pk)\n            if (self.two_exam_sets', '''            previous = Assessment.objects.get(pk=self.pk)
            if self.nursery_progress != previous.nursery_progress:
                raise ValidationError("Report format cannot change after results or submissions exist.")
            if (self.two_exam_sets''')
edit(m,'class Mark(AuditedModel):','''class Mark(AuditedModel):
    observation = models.TextField(blank=True, max_length=2000)''')
f='apps/academics/forms.py'
s=Path(f).read_text(); print(s[s.index('class SubjectForm'):s.index('class SubjectForm')+220])
edit(f,'"maximum_score", "requires_mark_review",','"maximum_score", "nursery_progress", "grading_scheme", "requires_mark_review",')
edit(f,'        self.fields["set_one_weight"].required = False','''        self.fields["grading_scheme"].queryset = GradingScheme.objects.filter(section__school=school, is_active=True)
        self.fields["grading_scheme"].help_text = "Optional override; choose descriptive levels for Baby and Middle progress reports."
        if self.instance.pk and (self.instance.marks.exists() or self.instance.reports.exists()):
            self.fields["grading_scheme"].disabled = True
            self.fields["nursery_progress"].disabled = True
        self.fields["set_one_weight"].required = False''')
edit(f,'        if academic_class and not self.instance.grading_scheme_id:\n            scheme = current_scheme(academic_class.section)\n            self.instance.grading_scheme = scheme if scheme and scheme.is_active else None','''        if academic_class:
            scheme = data.get("grading_scheme") or self.instance.grading_scheme or current_scheme(academic_class.section)
            data["grading_scheme"] = scheme if scheme and scheme.is_active else None
            self.instance.grading_scheme = data["grading_scheme"]''')
edit(f,'fields = ("score", "level", "is_absent")','fields = ("score", "level", "is_absent", "observation")')
edit(f,'        self.instance.exam_set = exam_set','''        if not assessment.nursery_progress:
            self.fields.pop("observation")
        else:
            self.fields["observation"].widget = forms.Textarea(attrs={"rows": 2})
        self.instance.exam_set = exam_set''')
s='apps/academics/services.py'
edit(s,'scheme = previous.grading_scheme if previous and previous.grading_scheme_id else current_scheme(record.academic_class.section)','scheme = record.grading_scheme or current_scheme(record.academic_class.section)')
edit(s,'    record.is_absent = proposed.is_absent','    record.is_absent = proposed.is_absent\n    record.observation = proposed.observation.strip()')
edit(s,'(record.requires_mark_review or record.two_exam_sets)', '(record.requires_mark_review or record.two_exam_sets or record.nursery_progress)')
f='apps/academics/mark_sheets.py'
edit(f,'class SheetRowForm(forms.Form):','''class SheetRowForm(forms.Form):
    observation = forms.CharField(required=False, max_length=2000, widget=forms.Textarea(attrs={"rows": 2}))''')
edit(f,'"is_absent": mark.is_absent if mark else False,','"observation": mark.observation if mark else "", "is_absent": mark.is_absent if mark else False,')
edit(f,'        self.enrollment, self.mark = enrollment, mark','        self.enrollment, self.mark = enrollment, mark\n        self.nursery_progress = assessment.nursery_progress')
edit(f,'        self.maximum = assessment.maximum_score','''        self.maximum = assessment.maximum_score
        if not assessment.nursery_progress:
            self.fields.pop("observation")
        else:
            self.fields["observation"].widget.attrs["aria-label"] = f"Teacher observation for {enrollment.student.full_name}"''')
edit(f,'        return data\n\n    def has_result', '''        if self.nursery_progress and data.get("observation") and not data.get("is_absent") and level is None:
            self.add_error("level", "Choose a progress level for this observation.")
        return data

    def has_result''')
edit(f,'    return [[pk, marks[pk]] for pk in ids]','''    if assessment.nursery_progress:
        for mark in Mark.objects.filter(assessment=assessment, exam_set=exam_set, subject=assignment.subject, enrollment_id__in=ids):
            if not mark.is_absent and (not mark.level_id or not mark.observation.strip()):
                raise ValidationError("Every assessed learner needs a progress level and teacher observation before submission.")
    return [[pk, marks[pk]] for pk in ids]''')
edit(f,'(current.score, current.level_id, current.is_absent)', '(current.score, current.level_id, current.is_absent, current.observation)')
edit(f,'form.cleaned_data["is_absent"]):','form.cleaned_data["is_absent"], form.cleaned_data.get("observation", "")):')
g='apps/academics/grading.py'
edit(g,"        subjects.append(row)",'''        if mark.assessment.nursery_progress:
            if not mark.is_absent and not mark.observation.strip():
                raise ValidationError("Complete each learner's teacher observations before generating reports.")
            row.update(observation=mark.observation, illustration=mark.subject.illustration)
        subjects.append(row)''')
f='templates/academics/marks.html'
edit(f,'Subject and stream','{% if assessment.nursery_progress %}Learning area and stream{% else %}Subject and stream{% endif %}')
edit(f,'Choose a learning level for each student.','Choose a progress level for each learner.{% if assessment.nursery_progress %} Enter your observation of their capabilities. Observations are required before submission or closing the exam.{% endif %}')
edit(f,'<th>Absent</th>','{% if assessment.nursery_progress %}<th>Teacher observation</th>{% endif %}<th>Absent</th>')
edit(f,'</td><td>{% if can_edit %}{{ row.is_absent }}','</td>{% if assessment.nursery_progress %}<td>{% if can_edit %}{{ row.observation }}{{ row.observation.errors }}{% else %}{{ row.mark.observation|linebreaksbr }}{% endif %}</td>{% endif %}<td>{% if can_edit %}{{ row.is_absent }}')
f='apps/reports/services.py'
edit(f,'if assessment.requires_mark_review or assessment.two_exam_sets:', 'if assessment.requires_mark_review or assessment.two_exam_sets or assessment.nursery_progress:')
edit(f,"            'schema_version': 1,", "            'nursery_progress': assessment.nursery_progress,\n            'schema_version': 1,")
edit(f,"        reports.append(write_record",'''        if assessment.nursery_progress:
            report.teacher_comment = ''
            report.status = 'review'
            report.snapshot.pop('teacher_comment_suggestion', None)
        reports.append(write_record''')
edit(f,"    report.status = 'approved' if approve else 'draft'", "    report.status = 'approved' if approve else 'draft'\n    if not approve and report.snapshot.get('nursery_progress'):\n        raise ValidationError('Use the assessment correction workflow to return nursery observations for correction.')")
f='apps/reports/models.py'
edit(f,"(not self.snapshot or not self.teacher_comment.strip())", "(not self.snapshot or (not self.snapshot.get('nursery_progress') and not self.teacher_comment.strip()))")
f='apps/reports/comments.py'
edit(f,"    if snapshot.get('mode') != 'numeric'",'''    if snapshot.get('nursery_progress'):
        from collections import Counter
        levels = Counter(row['grade'] for row in snapshot.get('subjects', []) if not row.get('absent'))
        summary = '; '.join(f"{label}: {count} learning area{'s' if count != 1 else ''}" for label, count in levels.items())
        comment = ('Recorded progress - ' + summary + '. ' if summary else 'No learning areas were assessed. ')
        comment += "Please follow the teacher observations for individual support and next steps."
        if any(row.get('absent') for row in snapshot.get('subjects', [])):
            comment += " Some learning areas were not assessed due to absence."
        return {'comment': comment, 'levels': dict(levels), 'method': 'recorded_progress_levels'}
    if snapshot.get('mode') != 'numeric' ''')
