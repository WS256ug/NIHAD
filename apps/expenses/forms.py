from uuid import uuid4
from django import forms
from apps.schools.models import School
from apps.students.forms import set_date_widgets
from .models import Expense, ExpenseCategory, OtherIncome


class CategoryForm(forms.ModelForm):
    class Meta:
        model = ExpenseCategory
        fields = ('name',)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.school_id = 1


class CashRecordForm(forms.ModelForm):
    request_key = forms.UUIDField(initial=uuid4, widget=forms.HiddenInput)
    confirm = forms.BooleanField(label='Confirm this transaction')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.school_id = 1
        if 'category' in self.fields:
            self.fields['category'].queryset = ExpenseCategory.objects.filter(school_id=1, is_active=True)
        set_date_widgets(self)


class ExpenseForm(CashRecordForm):
    class Meta:
        model = Expense
        fields = ('category', 'description', 'amount', 'date', 'method', 'reference')


class IncomeForm(CashRecordForm):
    class Meta:
        model = OtherIncome
        fields = ('source', 'description', 'amount', 'date', 'method', 'reference')
