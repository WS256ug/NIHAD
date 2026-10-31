from django.contrib import admin
from django import forms

from .models import AcademicClass, AcademicYear, School, Section, Stream, Term


class SuperuserRecordForm(forms.ModelForm):
    """Admin-only corrections retain field and relationship validation."""

    def clean(self):
        data = super().clean()
        self.instance._superuser_admin_correction = True
        classroom = data.get("academic_class")
        if classroom and hasattr(self.instance, "section_id"):
            self.instance.section_id = classroom.section_id
        if self.instance._state.adding:
            school = data.get("school")
            if school and hasattr(self.instance, "currency"):
                self.instance.currency = school.currency_code
            category = data.get("category")
            if category and hasattr(self.instance, "category_name"):
                self.instance.category_name = category.name
        return data


@admin.register(School, Section, AcademicYear, Term, AcademicClass, Stream)
class ConfigurationAdmin(admin.ModelAdmin):
    """Full audited administration for active superusers."""
    form = SuperuserRecordForm
    list_display = ("name", "updated_at")
    search_fields = ("name",)

    def get_readonly_fields(self, request, obj=None):
        if self.has_change_permission(request, obj):
            return [field.name for field in self.model._meta.fields if not field.editable or (self.model._meta.label_lower == "students.guardian" and field.name == "user")]
        return [field.name for field in self.model._meta.fields]

    def has_view_permission(self, request, obj=None):
        return self.has_change_permission(request, obj)

    def has_add_permission(self, request):
        if self.model is School and School.objects.exists():
            return False
        return self.has_change_permission(request)

    def has_change_permission(self, request, obj=None):
        return request.user.is_active and request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return self.has_change_permission(request, obj)

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)
