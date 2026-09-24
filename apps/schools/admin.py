from django.contrib import admin

from .models import AcademicClass, AcademicYear, School, Section, Stream, Term


@admin.register(School, Section, AcademicYear, Term, AcademicClass, Stream)
class ConfigurationAdmin(admin.ModelAdmin):
    """Superusers manage configuration; workflow records remain protected."""
    editable_models = {
        "schools.school", "schools.section", "schools.academicyear",
        "schools.term", "schools.academicclass", "schools.stream",
        "academics.subject", "academics.assessmenttype", "students.guardian",
    }
    list_display = ("name", "updated_at")
    search_fields = ("name",)
    actions = None

    def get_readonly_fields(self, request, obj=None):
        if self.has_change_permission(request, obj):
            return [field.name for field in self.model._meta.fields if not field.editable or (self.model._meta.label_lower == "students.guardian" and field.name == "user")]
        return [field.name for field in self.model._meta.fields]

    def has_add_permission(self, request):
        if self.model is School and School.objects.exists():
            return False
        return self.has_change_permission(request)

    def has_change_permission(self, request, obj=None):
        return request.user.is_active and request.user.is_superuser and self.model._meta.label_lower in self.editable_models

    def has_delete_permission(self, request, obj=None):
        if not self.has_change_permission(request, obj) or self.model is School:
            return False
        if obj:
            # Even nullable dependencies are historical links, not disposable data.
            for relation in obj._meta.related_objects:
                if relation.related_model._base_manager.filter(**{relation.field.name: obj}).exists():
                    return False
        return True

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)
