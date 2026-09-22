from django.contrib import admin
from apps.schools.admin import ConfigurationAdmin
from .models import Expense, ExpenseCategory, ExpenseReversal, IncomeReversal, OtherIncome


@admin.register(Expense, ExpenseCategory, ExpenseReversal, IncomeReversal, OtherIncome)
class ExpenseRecordAdmin(ConfigurationAdmin):
    list_display = ('__str__', 'created_at')
