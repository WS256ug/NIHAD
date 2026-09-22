from dataclasses import dataclass
from .forms import AssessmentForm, AssessmentTypeForm, ClassTeacherAssignmentForm, SubjectForm, TeacherForm, TeachingAssignmentForm
from .models import Assessment, AssessmentType, ClassTeacherAssignment, Subject, Teacher, TeachingAssignment
from .forms import DivisionRuleForm, GradeRuleForm, GradingSchemeForm
from .models import DivisionRule, GradeRule, GradingScheme


@dataclass(frozen=True)
class AcademicResource:
    model: type
    form: type
    label: str
    singular: str
    scope: str
    search: tuple
    related: tuple
    status: bool = True


RESOURCES = {
    "grading-schemes": AcademicResource(GradingScheme, GradingSchemeForm, "Grading schemes", "grading scheme", "section__school", ("name", "section__name"), ("section",)),
    "grade-rules": AcademicResource(GradeRule, GradeRuleForm, "Grades and learning levels", "grade or learning level", "scheme__section__school", ("label", "scheme__name"), ("scheme",), False),
    "division-rules": AcademicResource(DivisionRule, DivisionRuleForm, "Division rules", "division rule", "scheme__section__school", ("label", "scheme__name"), ("scheme",), False),
    "teachers": AcademicResource(Teacher, TeacherForm, "Teachers", "teacher profile", "school", ("teacher_id", "user__first_name", "user__last_name", "user__username"), ("user",), False),
    "subjects": AcademicResource(Subject, SubjectForm, "Subjects", "subject", "section__school", ("name", "code"), ("section",)),
    "teaching": AcademicResource(TeachingAssignment, TeachingAssignmentForm, "Teaching assignments", "teaching assignment", "academic_year__school", ("teacher__user__first_name", "teacher__user__last_name", "subject__name", "academic_class__name"), ("teacher__user", "academic_year", "academic_class__section", "subject", "stream", "term")),
    "class-teachers": AcademicResource(ClassTeacherAssignment, ClassTeacherAssignmentForm, "Class teachers", "class teacher assignment", "academic_year__school", ("teacher__user__first_name", "teacher__user__last_name", "academic_class__name"), ("teacher__user", "academic_year", "academic_class__section", "stream", "term")),
    "assessment-types": AcademicResource(AssessmentType, AssessmentTypeForm, "Assessment types", "assessment type", "school", ("name",), ()),
    "assessments": AcademicResource(Assessment, AssessmentForm, "Assessments and marks", "assessment", "term__academic_year__school", ("assessment_type__name", "academic_class__name", "term__name"), ("term__academic_year", "academic_class__section", "stream", "assessment_type"), False),
}
