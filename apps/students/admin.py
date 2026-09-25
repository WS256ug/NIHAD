from django.contrib import admin
from apps.schools.admin import ConfigurationAdmin
from .models import Enrollment, Guardian, Student, StudentGuardian


@admin.register(Student, Guardian, StudentGuardian, Enrollment)
class StudentRecordAdmin(ConfigurationAdmin):
    """Superuser record management; protected photos use the student workspace."""
    list_display = ("__str__", "updated_at")
    search_fields = ()
    exclude = ("photo",)

    def save_model(self, request, obj, form, change):
        if isinstance(obj, Student) and not change:
            from django.db.models import F
            from .models import StudentNumber
            counter, _ = StudentNumber.objects.select_for_update().get_or_create(school=obj.school)
            StudentNumber.objects.filter(pk=counter.pk).update(last_value=F("last_value") + 1)
            counter.refresh_from_db()
            obj.student_id = f"NBS-{counter.last_value:04d}"
        super().save_model(request, obj, form, change)
