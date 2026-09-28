from django import forms
from apps.schools.forms import ConfigurationStatusForm


class TeacherCommentForm(forms.Form):
    comment = forms.CharField(max_length=2000, widget=forms.Textarea(attrs={'rows': 5}), label='Class-teacher comment')

    def __init__(self, *args, suggested_comment='', **kwargs):
        super().__init__(*args, **kwargs)
        if suggested_comment:
            self.initial['comment'] = suggested_comment
            self.fields['comment'].required = False
            self.fields['comment'].help_text = 'Filled from the saved comment or report results. You can edit it before submission. Leaving it blank uses the saved comment or automatic suggestion.'
        else:
            self.fields['comment'].help_text = 'Enter a comment: these results do not have a complete numeric average for automatic selection.'


class ReviewForm(forms.Form):
    comment = forms.CharField(max_length=2000, widget=forms.Textarea(attrs={'rows': 5}), label='Headteacher comment')
    decision = forms.ChoiceField(choices=[('approve', 'Approve report'), ('return', 'Return to class teacher')])

    def __init__(self, *args, suggested_comment='', **kwargs):
        super().__init__(*args, **kwargs)
        if suggested_comment:
            self.initial['comment'] = suggested_comment
            self.fields['comment'].required = False
            self.fields['comment'].help_text = 'Automatically filled from the report results. You can edit it before approval. Leaving it blank on approval uses the saved suggestion.'
        else:
            self.fields['comment'].help_text = 'Enter a comment: these results do not have a complete numeric average for automatic selection.'

    def clean(self):
        data = super().clean()
        if data.get('decision') == 'return' and not data.get('comment'):
            self.add_error('comment', 'Enter a comment explaining the correction needed.')
        return data


class CorrectionForm(ConfigurationStatusForm):
    reason = forms.CharField(max_length=2000, widget=forms.Textarea(attrs={'rows': 4}), help_text='Published versions stay available. All students in this assessment receive a new revision so rankings can be recalculated consistently.')
