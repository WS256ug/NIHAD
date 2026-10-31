from django.contrib import admin
from apps.schools.admin import ConfigurationAdmin
from .models import StudentReport


@admin.register(StudentReport)
class StudentReportAdmin(ConfigurationAdmin):
    list_display = ('__str__', 'status', 'version', 'published_at')
