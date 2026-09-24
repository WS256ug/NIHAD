from uuid import uuid4
from decimal import Decimal
from django import forms
from django.utils import timezone
from apps.schools.models import AcademicClass, Stream, Term
from apps.students.forms import set_date_widgets
from apps.students.models import Enrollment
from .models import FeeStructure, PaymentMethod


class FeeStructureForm(forms.ModelForm):
    class Meta:
        model = FeeStructure
        fields = ('term', 'academic_class', 'stream', 'name', 'category', 'amount', 'due_date')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['term'].queryset = Term.objects.filter(academic_year__school_id=1, is_active=True, academic_year__is_active=True)
        self.fields['academic_class'].queryset = AcademicClass.objects.filter(section__school_id=1, is_active=True)
        self.fields['stream'].queryset = Stream.objects.filter(academic_class__section__school_id=1, is_active=True)
        if self.instance.pk:
            for name in ('term', 'academic_class', 'stream'):
                self.fields[name].disabled = True
                self.fields[name].queryset = self.fields[name].queryset.model.objects.filter(pk=getattr(self.instance, name + '_id'))
        set_date_widgets(self)


class ChargeForm(forms.Form):
    enrollment = forms.ModelChoiceField(queryset=Enrollment.objects.none())
    structure = forms.ModelChoiceField(queryset=FeeStructure.objects.none())
    confirm = forms.BooleanField(label='Confirm this fee assignment')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['enrollment'].queryset = Enrollment.objects.filter(student__school_id=1).select_related('student', 'academic_year', 'academic_class', 'stream')
        self.fields['structure'].queryset = FeeStructure.objects.filter(term__academic_year__school_id=1, is_active=True).select_related('term__academic_year', 'academic_class')


class PaymentForm(forms.Form):
    amount = forms.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal('.01'))
    date = forms.DateField(initial=timezone.localdate, widget=forms.DateInput(attrs={'type': 'date'}))
    method = forms.ChoiceField(choices=PaymentMethod.choices)
    notes = forms.CharField(max_length=2000, required=False, widget=forms.Textarea(attrs={'rows': 3}))
    request_key = forms.UUIDField(widget=forms.HiddenInput, initial=uuid4)
    confirm = forms.BooleanField(label='Confirm the payment has been received')


class ReversalForm(forms.Form):
    reason = forms.CharField(max_length=500, widget=forms.Textarea(attrs={'rows': 4}))
    confirm = forms.BooleanField(label='Confirm this reversal')
