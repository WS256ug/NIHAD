from django import forms
from django.forms import BaseFormSet, formset_factory
from apps.schools.models import AcademicClass, AcademicYear, Stream
from apps.students.forms import selected_pk, set_date_widgets
from apps.students.models import Enrollment
from .models import PromotionBatch, PromotionDecision, higher_classes


class BatchForm(forms.ModelForm):
    class Meta:
        model = PromotionBatch
        fields = ('source_year', 'source_class', 'source_stream', 'completion_date', 'destination_year', 'destination_class', 'destination_stream', 'enrollment_date')

    def __init__(self, *args, dialog=False, **kwargs):
        super().__init__(*args, **kwargs)
        for prefix in ('source', 'destination'):
            self.fields[prefix + '_year'].queryset = AcademicYear.objects.filter(school_id=1, is_active=True)
            self.fields[prefix + '_class'].queryset = AcademicClass.objects.filter(section__school_id=1, is_active=True)
            self.fields[prefix + '_stream'].queryset = Stream.objects.filter(academic_class__section__school_id=1, is_active=True)
        def chosen(name):
            return selected_pk(self.data.get(self.add_prefix(name)) if self.is_bound else self.initial.get(name))

        source_year = self.fields['source_year'].queryset.filter(pk=chosen('source_year')).first()
        source_class = self.fields['source_class'].queryset.filter(pk=chosen('source_class')).first()
        years = self.fields['destination_year'].queryset
        self.fields['destination_year'].queryset = years.filter(start_date__gt=source_year.end_date) if source_year else years.none()
        classes = self.fields['destination_class'].queryset.filter(section__is_active=True)
        self.fields['destination_class'].queryset = classes.filter(higher_classes(source_class)) if source_class else classes.none()
        for prefix in ('source', 'destination'):
            self.fields[prefix + '_stream'].queryset = self.fields[prefix + '_stream'].queryset.filter(academic_class_id=chosen(prefix + '_class'))
        from django.urls import reverse
        for name in ('source_year', 'source_class', 'destination_class'):
            self.fields[name].widget.attrs.update({
                'hx-get': reverse('promotions:create') + ('?dialog=1' if dialog else ''), 'hx-trigger': 'change',
                'hx-include': 'closest form', 'hx-target': 'closest form',
                'hx-select': '#promotion-batch-form', 'hx-swap': 'outerHTML',
                'hx-sync': 'closest form:replace',
                'hx-params': ','.join(self._meta.fields),
            })
        self.fields['destination_year'].help_text = 'Choose a source year first. Only later active years are available.'
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
