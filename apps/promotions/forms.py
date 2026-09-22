from django import forms
from django.forms import BaseFormSet, formset_factory
from apps.schools.models import AcademicClass, AcademicYear, Stream
from apps.students.forms import set_date_widgets
from apps.students.models import Enrollment
from .models import PromotionBatch, PromotionDecision


class BatchForm(forms.ModelForm):
    class Meta:
        model = PromotionBatch
        fields = ('source_year', 'source_class', 'source_stream', 'completion_date', 'destination_year', 'destination_class', 'destination_stream', 'enrollment_date')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for prefix in ('source', 'destination'):
            self.fields[prefix + '_year'].queryset = AcademicYear.objects.filter(school_id=1, is_active=True)
            self.fields[prefix + '_class'].queryset = AcademicClass.objects.filter(section__school_id=1, is_active=True)
            self.fields[prefix + '_stream'].queryset = Stream.objects.filter(academic_class__section__school_id=1, is_active=True)
        self.fields['destination_class'].help_text = 'Promoted students enter this class. Repeating students remain in their source class in the new year.'
        set_date_widgets(self)


class DecisionForm(forms.Form):
    enrollment = forms.ModelChoiceField(queryset=Enrollment.objects.none(), widget=forms.HiddenInput)
    selected = forms.BooleanField(required=False, label='Include student')
    decision = forms.ChoiceField(choices=PromotionDecision.Decision.choices)
    notes = forms.CharField(max_length=500, required=False)

    def __init__(self, *args, enrollments, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['enrollment'].queryset = enrollments


class DecisionFormSet(BaseFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return
        ids = [form.cleaned_data['enrollment'].pk for form in self.forms if form.cleaned_data]
        if len(ids) != len(set(ids)):
            raise forms.ValidationError('Each student can appear only once in a batch.')


DecisionForms = formset_factory(DecisionForm, formset=DecisionFormSet, extra=0, max_num=1000, validate_max=True, absolute_max=1000)


class RevisionForm(forms.Form):
    revision = forms.IntegerField(min_value=0, widget=forms.HiddenInput)


class ConfirmBatchForm(RevisionForm):
    confirm = forms.BooleanField(label='Confirm every selected decision and preserve previous enrollment history')
