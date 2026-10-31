from django.contrib import admin
from apps.schools.admin import ConfigurationAdmin
from .models import Assessment, ExamSet, AssessmentType, ClassTeacherAssignment, Mark, Subject, Teacher, TeachingAssignment
from .models import DivisionRule, GradeRule, GradingScheme, MarkSubmission


@admin.register(ExamSet, Teacher, Subject, TeachingAssignment, ClassTeacherAssignment, AssessmentType, Assessment, Mark, DivisionRule, GradeRule, GradingScheme, MarkSubmission)
class AcademicRecordAdmin(ConfigurationAdmin):
    list_display = ("__str__", "updated_at")
    search_fields = ()

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if isinstance(obj, Assessment):
            from .services import configure_exam_sets
            configure_exam_sets(obj, request.user)
