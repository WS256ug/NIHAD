from django.contrib import admin
from apps.schools.admin import ConfigurationAdmin
from .models import Enrollment, Guardian, Student, StudentGuardian


@admin.register(Student, Guardian, StudentGuardian, Enrollment)
class StudentRecordAdmin(ConfigurationAdmin):
    """Read-only inspection; validated writes and protected photos use the portal."""
    list_display = ("__str__", "updated_at")
    search_fields = ()
    exclude = ("photo",)

    def get_readonly_fields(self, request, obj=None):
        return [field.name for field in self.model._meta.fields if field.name != "photo"]
