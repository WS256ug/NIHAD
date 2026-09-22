from django import forms
from apps.schools.forms import ConfigurationStatusForm


class TeacherCommentForm(forms.Form):
    comment = forms.CharField(max_length=2000, widget=forms.Textarea(attrs={'rows': 5}), label='Class-teacher comment')


class ReviewForm(forms.Form):
    comment = forms.CharField(max_length=2000, widget=forms.Textarea(attrs={'rows': 5}), label='Headteacher comment')
    decision = forms.ChoiceField(choices=[('approve', 'Approve report'), ('return', 'Return to class teacher')])


class CorrectionForm(ConfigurationStatusForm):
    reason = forms.CharField(max_length=2000, widget=forms.Textarea(attrs={'rows': 4}), help_text='Published versions stay available. All students in this assessment receive a new revision so rankings can be recalculated consistently.')
