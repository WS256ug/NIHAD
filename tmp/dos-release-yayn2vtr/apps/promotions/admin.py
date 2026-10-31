from django.contrib import admin
from apps.schools.admin import ConfigurationAdmin
from .models import PromotionBatch, PromotionDecision


@admin.register(PromotionBatch, PromotionDecision)
class PromotionRecordAdmin(ConfigurationAdmin):
    list_display = ('__str__', 'created_at')
