from django import forms
from apps.accounts.models import User
from apps.accounts.permissions import manageable_accounts
from apps.schools.models import AcademicClass, AcademicYear, Section, Stream, Term
from apps.students.forms import selected_pk, set_date_widgets
from .models import Assessment, AssessmentType, ClassTeacherAssignment, DivisionRule, GradeRule, GradingScheme, Mark, Subject, Teacher, TeachingAssignment


class TeacherForm(forms.ModelForm):
    class Meta:
        model = Teacher
        fields = ("user", "phone", "date_joined", "employment_status", "specialization")

    def __init__(self, *args, school, actor, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.school = school
        if self.instance.pk:
            self.fields["user"].disabled = True
            self.fields["user"].queryset = User.objects.filter(pk=self.instance.user_id)
        else:
            self.fields["user"].queryset = manageable_accounts(actor).filter(role=User.Role.TEACHER, is_active=True, teacher_profile__isnull=True)
        set_date_widgets(self)


class SubjectForm(forms.ModelForm):
    class Meta:
        model = Subject
        fields = ("section", "code", "name")

    def __init__(self, *args, school, actor, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["section"].queryset = Section.objects.filter(school=school, is_active=True)
        if self.instance.pk:
            self.fields["section"].disabled = True
            self.fields["section"].queryset = Section.objects.filter(pk=self.instance.section_id, school=school)


class AssignmentForm(forms.ModelForm):
    def __init__(self, *args, school, actor, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["teacher"].queryset = Teacher.objects.filter(school=school, employment_status="active", user__is_active=True).select_related("user")
        self.fields["academic_year"].queryset = AcademicYear.objects.filter(school=school, is_active=True)
        self.fields["academic_class"].queryset = AcademicClass.objects.filter(section__school=school, section__is_active=True, is_active=True).select_related("section")
        self.fields["term"].queryset = Term.objects.filter(academic_year__school=school, academic_year__is_active=True, is_active=True).select_related("academic_year")
        self.fields["stream"].queryset = Stream.objects.filter(academic_class__section__school=school, academic_class__section__is_active=True, academic_class__is_active=True, is_active=True).select_related("academic_class__section")
        if "subject" in self.fields:
            self.fields["subject"].queryset = Subject.objects.filter(section__school=school, section__is_active=True, is_active=True).select_related("section")
        if self.instance.pk:
            for name, field in self.fields.items():
                field.disabled = True
                field.queryset = field.queryset.model.objects.filter(pk=getattr(self.instance, name + "_id"))
        elif self.is_bound:
            self.fields["term"].queryset = self.fields["term"].queryset.filter(academic_year_id=selected_pk(self.data.get("academic_year")))
            self.fields["stream"].queryset = self.fields["stream"].queryset.filter(academic_class_id=selected_pk(self.data.get("academic_class")))
            if "subject" in self.fields:
                self.fields["subject"].queryset = self.fields["subject"].queryset.filter(section__classes__pk=selected_pk(self.data.get("academic_class")))

    def clean(self):
        data = super().clean()
        if data.get("academic_class"):
            self.instance.section = data["academic_class"].section
        return data


class TeachingAssignmentForm(AssignmentForm):
    class Meta:
        model = TeachingAssignment
        fields = ("teacher", "academic_year", "term", "academic_class", "stream", "subject")


class ClassTeacherAssignmentForm(AssignmentForm):
    class Meta:
        model = ClassTeacherAssignment
        fields = ("teacher", "academic_year", "term", "academic_class", "stream")


class AssessmentTypeForm(forms.ModelForm):
    class Meta:
        model = AssessmentType
        fields = ("name",)

    def __init__(self, *args, school, actor, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.school = school


class AssessmentForm(forms.ModelForm):
    class Meta:
        model = Assessment
        fields = ("assessment_type", "term", "academic_class", "stream", "date", "maximum_score", "grading_scheme")

    def __init__(self, *args, school, actor, **kwargs):
        super().__init__(*args, **kwargs)
        choices = {
            "assessment_type": AssessmentType.objects.filter(school=school, is_active=True),
            "term": Term.objects.filter(academic_year__school=school, academic_year__is_active=True, is_active=True).select_related("academic_year"),
            "academic_class": AcademicClass.objects.filter(section__school=school, section__is_active=True, is_active=True).select_related("section"),
            "stream": Stream.objects.filter(academic_class__section__school=school, academic_class__is_active=True, is_active=True).select_related("academic_class__section"),
        }
        for name, queryset in choices.items():
            self.fields[name].queryset = queryset
            if self.instance.pk:
                self.fields[name].disabled = True
                self.fields[name].queryset = queryset.model.objects.filter(pk=getattr(self.instance, name + "_id"))
        if self.is_bound and not self.instance.pk:
            self.fields["stream"].queryset = self.fields["stream"].queryset.filter(academic_class_id=selected_pk(self.data.get("academic_class")))
        self.fields["grading_scheme"].queryset = GradingScheme.objects.filter(section__school=school, is_active=True)
        if self.instance.pk and self.instance.grading_scheme_id and self.instance.marks.exists():
            self.fields["grading_scheme"].disabled = True
        set_date_widgets(self)


class MarkForm(forms.ModelForm):
    expected_revision = forms.IntegerField(min_value=0, widget=forms.HiddenInput)

    class Meta:
        model = Mark
        fields = ("score", "level")

    def __init__(self, *args, assessment, enrollment, subject, assignment, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.assessment = assessment
        self.instance.enrollment = enrollment
        self.instance.subject = subject
        self.instance.teaching_assignment = assignment
        self.initial["expected_revision"] = self.instance.revision if self.instance.pk else 0
        if assessment.grading_scheme_id and assessment.grading_scheme.mode == "descriptive":
            self.fields.pop("score")
            self.fields["level"].queryset = assessment.grading_scheme.rules.all()
            self.fields["level"].required = True
        else:
            self.fields.pop("level")
            self.fields["score"].required = True
            self.fields["score"].min_value = 0
            self.fields["score"].max_value = assessment.maximum_score
            self.fields["score"].widget.attrs.update(min=0, max=assessment.maximum_score, step="0.01")


class GradingSchemeForm(forms.ModelForm):
    class Meta:
        model = GradingScheme
        fields = ("section", "name", "mode", "aggregate_mode", "best_n", "required_subjects")

    def __init__(self, *args, school, actor, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["section"].queryset = Section.objects.filter(school=school, is_active=True)
        self.fields["required_subjects"].queryset = Subject.objects.filter(section__school=school, is_active=True)
        if self.instance.pk:
            self.fields["section"].disabled = True
        if self.is_bound:
            section_id = self.instance.section_id or selected_pk(self.data.get("section"))
            self.fields["required_subjects"].queryset = self.fields["required_subjects"].queryset.filter(section_id=section_id)

    def clean(self):
        data = super().clean()
        if self.instance.in_use():
            raise forms.ValidationError("This scheme is already used by marks. Create a new version to change grading.")
        if self.instance.is_active:
            raise forms.ValidationError("Deactivate this unused scheme before changing its configuration.")
        return data


class GradingRuleForm(forms.ModelForm):
    def __init__(self, *args, school, actor, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["scheme"].queryset = GradingScheme.objects.filter(section__school=school, is_active=False)
        if self.instance.pk:
            self.fields["scheme"].disabled = True
            self.fields["scheme"].queryset = GradingScheme.objects.filter(pk=self.instance.scheme_id)


class GradeRuleForm(GradingRuleForm):
    class Meta:
        model = GradeRule
        fields = ("scheme", "label", "minimum", "maximum", "points", "sort_order")
        help_texts = {"minimum": "Percentage included in this grade. Leave blank for descriptive levels.", "maximum": "Upper boundary excluded, except 100 which is included. Example: 80 to 100.", "points": "Aggregate points; leave blank for descriptive levels."}


class DivisionRuleForm(GradingRuleForm):
    class Meta:
        model = DivisionRule
        fields = ("scheme", "label", "minimum", "maximum")
