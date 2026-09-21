from django import forms

from .models import AcademicClass, AcademicYear, School, Section, Stream, Term


class SchoolForm(forms.ModelForm):
    class Meta:
        model = School
        fields = ("name", "motto", "address", "phone", "email", "website", "currency_code", "enable_ranking", "require_fee_clearance_for_reports")
        widgets = {"address": forms.Textarea(attrs={"rows": 3})}
        help_texts = {
            "enable_ranking": "Use ranking when academic reports are introduced.",
            "require_fee_clearance_for_reports": "Require fee clearance when guardian report access is introduced.",
        }

    def clean_currency_code(self):
        return self.cleaned_data["currency_code"].upper()


class ConfigurationForm(forms.ModelForm):
    parent_field = None

    def __init__(self, *args, school, **kwargs):
        super().__init__(*args, **kwargs)
        if "school" in [field.name for field in self._meta.model._meta.fields]:
            self.instance.school = school
        if self.parent_field:
            field = self.fields[self.parent_field]
            if self.instance.pk:
                # Keeping a relation immutable also rejects forged POST values.
                field.disabled = True
                field.queryset = field.queryset.filter(pk=getattr(self.instance, self.parent_field + "_id"))
            elif self.parent_field == "academic_year":
                field.queryset = AcademicYear.objects.filter(school=school, is_active=True)
            elif self.parent_field == "section":
                field.queryset = Section.objects.filter(school=school, is_active=True)
            else:
                field.queryset = AcademicClass.objects.filter(section__school=school, section__is_active=True, is_active=True).select_related("section")
        for name in ("start_date", "end_date"):
            if name in self.fields:
                self.fields[name].widget = forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")


class SectionForm(ConfigurationForm):
    class Meta:
        model = Section
        fields = ("name", "description", "sort_order")
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}


class AcademicYearForm(ConfigurationForm):
    class Meta:
        model = AcademicYear
        fields = ("name", "start_date", "end_date")


class TermForm(ConfigurationForm):
    parent_field = "academic_year"

    class Meta:
        model = Term
        fields = ("academic_year", "name", "start_date", "end_date")
        help_texts = {"start_date": "Terms are ordered by their start date within the academic year."}


class AcademicClassForm(ConfigurationForm):
    parent_field = "section"

    class Meta:
        model = AcademicClass
        fields = ("section", "name", "sort_order")


class StreamForm(ConfigurationForm):
    parent_field = "academic_class"

    class Meta:
        model = Stream
        fields = ("academic_class", "name")


class CurrentPeriodForm(forms.Form):
    academic_year = forms.ModelChoiceField(queryset=AcademicYear.objects.none(), required=False, empty_label="No current year")
    term = forms.ModelChoiceField(queryset=Term.objects.none(), required=False, empty_label="No current term")

    def __init__(self, *args, school, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["academic_year"].queryset = AcademicYear.objects.filter(school=school, is_active=True)
        self.initial.update(academic_year=school.current_academic_year_id, term=school.current_term_id)
        selected = self.data.get("academic_year") if self.is_bound else school.current_academic_year_id
        try:
            selected = int(selected)
        except (ValueError, TypeError):
            selected = None
        self.fields["term"].queryset = Term.objects.filter(academic_year_id=selected, academic_year__school=school, academic_year__is_active=True, is_active=True)


class ConfigurationStatusForm(forms.Form):
    confirm = forms.BooleanField(label="I confirm this status change.")
