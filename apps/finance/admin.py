from django.contrib import admin
from apps.schools.admin import ConfigurationAdmin
from .models import ChargeCancellation, FeeCharge, FeeStructure, Payment, PaymentReversal


@admin.register(ChargeCancellation, FeeCharge, FeeStructure, Payment, PaymentReversal)
class FinancialRecordAdmin(ConfigurationAdmin):
    list_display = ('__str__', 'created_at')
