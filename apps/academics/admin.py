from django.contrib import admin
from apps.schools.admin import ConfigurationAdmin
from .models import Assessment, AssessmentType, ClassTeacherAssignment, Mark, Subject, Teacher, TeachingAssignment
from .models import DivisionRule, GradeRule, GradingScheme, MarkSubmission


@admin.register(Teacher, Subject, TeachingAssignment, ClassTeacherAssignment, AssessmentType, Assessment, Mark, DivisionRule, GradeRule, GradingScheme, MarkSubmission)
class AcademicRecordAdmin(ConfigurationAdmin):
    list_display = ("__str__", "updated_at")
    search_fields = ()
