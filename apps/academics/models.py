from uuid import uuid4
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models.functions import Lower
from django.utils import timezone

from apps.schools.models import AuditedModel
from apps.students.models import preserve_fields


def teacher_identifier():
    return "TCH-" + uuid4().hex[:12].upper()


class Teacher(AuditedModel):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        LEAVE = "leave", "On leave"
        LEFT = "left", "Left school"

    school = models.ForeignKey("schools.School", on_delete=models.PROTECT, related_name="teachers")
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="teacher_profile")
    teacher_id = models.CharField(max_length=20, unique=True, default=teacher_identifier, editable=False)
    phone = models.CharField(max_length=40)
    date_joined = models.DateField(default=timezone.localdate)
    employment_status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)
    specialization = models.CharField(max_length=160, blank=True)

    class Meta:
        ordering = ("user__last_name", "user__first_name", "pk")
        constraints = [models.CheckConstraint(condition=models.Q(employment_status__in=["active", "leave", "left"]), name="academics_teacher_valid_status")]

    def __str__(self):
        return self.user.get_full_name() or self.user.username

    def clean(self):
        super().clean()
        preserve_fields(self, ("school_id", "user_id", "teacher_id"))
        if self.user_id and self.user.role != "teacher":
            raise ValidationError("Select an account with the Teacher role.")
        if self.employment_status == self.Status.ACTIVE and self.user_id and not self.user.is_active:
            raise ValidationError("An active teacher requires an active account.")
        if self.date_joined and self.date_joined > timezone.localdate():
            raise ValidationError({"date_joined": "Date joined cannot be in the future."})
        if self.pk and self.employment_status != self.Status.ACTIVE:
            if self.teaching_assignments.filter(is_active=True).exists() or self.class_assignments.filter(is_active=True).exists():
                raise ValidationError("Deactivate this teacher's assignments first.")


class Subject(AuditedModel):
    section = models.ForeignKey("schools.Section", on_delete=models.PROTECT, related_name="subjects")
    code = models.CharField(max_length=20)
    name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("section__sort_order", "name", "pk")
        constraints = [
            models.UniqueConstraint(Lower("code"), "section", name="academics_subject_code_unique", violation_error_message="This subject code is already used in the section."),
            models.UniqueConstraint(Lower("name"), "section", name="academics_subject_name_unique", violation_error_message="This subject name is already used in the section."),
        ]

    def __str__(self):
        return f"{self.section} / {self.name}"

    def clean(self):
        super().clean()
        preserve_fields(self, ("section_id",))
        self.code, self.name = self.code.strip().upper(), self.name.strip()
        if not self.code or not self.name:
            raise ValidationError("Enter a subject code and name.")
        if self.section_id and self.is_active and not self.section.is_active:
            raise ValidationError("An active subject requires an active section.")
        if self.pk and not self.is_active and self.assignments.filter(is_active=True).exists():
            raise ValidationError("Deactivate the subject's teaching assignments first.")


def scope_constraints(prefix, extra_fields=()):
    constraints = []
    for term_null in (True, False):
        for stream_null in (True, False):
            fields = ["academic_year", "academic_class", *extra_fields]
            if not term_null:
                fields.append("term")
            if not stream_null:
                fields.append("stream")
            constraints.append(models.UniqueConstraint(fields=fields, condition=models.Q(is_active=True, term__isnull=term_null, stream__isnull=stream_null), name=f"{prefix}_{int(term_null)}{int(stream_null)}", violation_error_message="An active assignment already exists for this scope."))
    return constraints


class Assignment(AuditedModel):
    teacher = models.ForeignKey(Teacher, on_delete=models.PROTECT, related_name="%(class)s_records")
    academic_year = models.ForeignKey("schools.AcademicYear", on_delete=models.PROTECT, related_name="%(class)s_records")
    term = models.ForeignKey("schools.Term", on_delete=models.PROTECT, null=True, blank=True, related_name="%(class)s_records")
    section = models.ForeignKey("schools.Section", on_delete=models.PROTECT, editable=False, related_name="%(class)s_records")
    academic_class = models.ForeignKey("schools.AcademicClass", on_delete=models.PROTECT, related_name="%(class)s_records")
    stream = models.ForeignKey("schools.Stream", on_delete=models.PROTECT, null=True, blank=True, related_name="%(class)s_records")
    is_active = models.BooleanField(default=True)

    class Meta:
        abstract = True
        ordering = ("-academic_year__start_date", "academic_class__sort_order", "pk")

    def __str__(self):
        return f"{self.teacher} / {self.academic_year} / {self.academic_class.name}" + (f" {self.stream.name}" if self.stream_id else "") + (f" / {self.term.name}" if self.term_id else " / All terms")

    def clean(self):
        super().clean()
        immutable = ["teacher_id", "academic_year_id", "term_id", "section_id", "academic_class_id", "stream_id"]
        if hasattr(self, "subject_id"):
            immutable.append("subject_id")
        preserve_fields(self, immutable)
        if not (self.teacher_id and self.academic_year_id and self.academic_class_id):
            return
        year, classroom, teacher = self.academic_year, self.academic_class, self.teacher
        if teacher.school_id != year.school_id or classroom.section.school_id != year.school_id or self.section_id != classroom.section_id:
            raise ValidationError("Teacher, year and class must belong to the same school and section context.")
        if self.term_id and self.term.academic_year_id != self.academic_year_id:
            raise ValidationError({"term": "Choose a term from the selected academic year."})
        if self.stream_id and self.stream.academic_class_id != self.academic_class_id:
            raise ValidationError({"stream": "Choose a stream from the selected class."})
        subject = getattr(self, "subject", None) if getattr(self, "subject_id", None) else None
        if subject and subject.section_id != self.section_id:
            raise ValidationError({"subject": "Choose a subject from the class's section."})
        if not self.is_active:
            return
        if not (year.is_active and classroom.is_active and classroom.section.is_active and teacher.employment_status == Teacher.Status.ACTIVE and teacher.user.is_active):
            raise ValidationError("Active assignments require an active teacher, account, year, class and section.")
        if (self.term_id and not self.term.is_active) or (self.stream_id and not self.stream.is_active) or (subject and not subject.is_active):
            raise ValidationError("Selected term, stream and subject must be active.")
        overlaps = type(self).objects.filter(academic_year_id=self.academic_year_id, academic_class_id=self.academic_class_id, is_active=True).exclude(pk=self.pk)
        if subject:
            overlaps = overlaps.filter(subject_id=self.subject_id)
        if self.term_id:
            overlaps = overlaps.filter(models.Q(term__isnull=True) | models.Q(term_id=self.term_id))
        if self.stream_id:
            overlaps = overlaps.filter(models.Q(stream__isnull=True) | models.Q(stream_id=self.stream_id))
        if overlaps.exists():
            raise ValidationError("Another active assignment covers this class/stream and period. Deactivate it before replacing it.")


class TeachingAssignment(Assignment):
    teacher = models.ForeignKey(Teacher, on_delete=models.PROTECT, related_name="teaching_assignments")
    subject = models.ForeignKey(Subject, on_delete=models.PROTECT, related_name="assignments")

    class Meta(Assignment.Meta):
        abstract = False
        constraints = scope_constraints("academics_teaching_scope", ("subject",))

    def __str__(self):
        return f"{super().__str__()} / {self.subject.name}"


class ClassTeacherAssignment(Assignment):
    teacher = models.ForeignKey(Teacher, on_delete=models.PROTECT, related_name="class_assignments")

    class Meta(Assignment.Meta):
        abstract = False
        constraints = scope_constraints("academics_class_teacher_scope")


class AssessmentType(AuditedModel):
    school = models.ForeignKey("schools.School", on_delete=models.PROTECT, related_name="assessment_types")
    name = models.CharField(max_length=80)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("name", "pk")
        constraints = [models.UniqueConstraint(Lower("name"), "school", name="academics_assessment_type_name", violation_error_message="This assessment type already exists.")]

    def __str__(self):
        return self.name

    def clean(self):
        preserve_fields(self, ("school_id",))
        self.name = self.name.strip()
        if not self.name:
            raise ValidationError({"name": "Enter an assessment type, such as Mid-Term or End-Term."})
        if self.pk and not self.is_active and self.assessments.exclude(status="closed").exists():
            raise ValidationError("Close this type's assessments before deactivating it.")


class Assessment(AuditedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        OPEN = "open", "Open for marks"
        CLOSED = "closed", "Marks closed"

    assessment_type = models.ForeignKey(AssessmentType, on_delete=models.PROTECT, related_name="assessments")
    term = models.ForeignKey("schools.Term", on_delete=models.PROTECT, related_name="assessments")
    academic_class = models.ForeignKey("schools.AcademicClass", on_delete=models.PROTECT, related_name="assessments")
    stream = models.ForeignKey("schools.Stream", on_delete=models.PROTECT, null=True, blank=True, related_name="assessments")
    date = models.DateField()
    maximum_score = models.DecimalField(max_digits=7, decimal_places=2, default=Decimal("100"), validators=[MinValueValidator(Decimal("0.01"))])
    grading_scheme = models.ForeignKey("GradingScheme", on_delete=models.PROTECT, null=True, blank=True, related_name="assessments")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    requires_mark_review = models.BooleanField(default=False, verbose_name="Require marks review", help_text="Enable submission and approval of subject marks before closing the assessment.")

    class Meta:
        ordering = ("-date", "pk")
        constraints = [
            models.CheckConstraint(condition=models.Q(maximum_score__gt=0), name="academics_assessment_max_positive"),
            models.CheckConstraint(condition=models.Q(status__in=["draft", "open", "closed"]), name="academics_assessment_status"),
            models.UniqueConstraint(fields=("assessment_type", "term", "academic_class", "stream"), condition=models.Q(stream__isnull=False), name="academics_assessment_stream_unique"),
            models.UniqueConstraint(fields=("assessment_type", "term", "academic_class"), condition=models.Q(stream__isnull=True), name="academics_assessment_class_unique"),
        ]

    def __str__(self):
        return f"{self.term} / {self.academic_class.name}" + (f" {self.stream.name}" if self.stream_id else "") + f" / {self.assessment_type}"

    def clean(self):
        super().clean()
        preserve_fields(self, ("assessment_type_id", "term_id", "academic_class_id", "stream_id"))
        if not (self.term_id and self.academic_class_id and self.assessment_type_id):
            return
        if self.term.academic_year.school_id != self.academic_class.section.school_id or self.assessment_type.school_id != self.term.academic_year.school_id:
            raise ValidationError("The assessment type, term and class must belong to the same school.")
        if self.stream_id and self.stream.academic_class_id != self.academic_class_id:
            raise ValidationError({"stream": "Choose a stream from the selected class."})
        if self.grading_scheme_id and (self.grading_scheme.section_id != self.academic_class.section_id or not self.grading_scheme.is_active):
            raise ValidationError("Choose an active grading scheme from the class's section.")
        if self.date and not self.term.start_date <= self.date <= self.term.end_date:
            raise ValidationError({"date": "Assessment date must fall within the selected term."})
        overlaps = Assessment.objects.filter(assessment_type_id=self.assessment_type_id, term_id=self.term_id, academic_class_id=self.academic_class_id).exclude(pk=self.pk)
        if self.stream_id:
            overlaps = overlaps.filter(models.Q(stream__isnull=True) | models.Q(stream_id=self.stream_id))
        if overlaps.exists():
            raise ValidationError("This assessment type already covers the selected class/stream and term.")
        if self._state.adding or self.status == self.Status.OPEN:
            if not (self.term.is_active and self.term.academic_year.is_active and self.academic_class.is_active and self.academic_class.section.is_active and self.assessment_type.is_active) or (self.stream_id and not self.stream.is_active):
                raise ValidationError("Assessment setup requires active school configuration.")
        if self.pk and not self._state.adding and self.marks.exists():
            previous = Assessment.objects.get(pk=self.pk)
            if self.grading_scheme_id and self.grading_scheme.mode == "descriptive" and self.marks.filter(score__isnull=False).exists():
                raise ValidationError("Existing numeric marks cannot be reassigned to a descriptive scheme.")
            if self.date != previous.date or self.maximum_score != previous.maximum_score or (previous.grading_scheme_id and self.grading_scheme_id != previous.grading_scheme_id):
                raise ValidationError("Assessment date, maximum score and grading scheme cannot change after marks exist.")


class Mark(AuditedModel):
    assessment = models.ForeignKey(Assessment, on_delete=models.PROTECT, related_name="marks")
    enrollment = models.ForeignKey("students.Enrollment", on_delete=models.PROTECT, related_name="marks")
    subject = models.ForeignKey(Subject, on_delete=models.PROTECT, related_name="marks")
    teaching_assignment = models.ForeignKey(TeachingAssignment, on_delete=models.PROTECT, related_name="marks")
    score = models.DecimalField(max_digits=7, decimal_places=2, validators=[MinValueValidator(0)], null=True, blank=True)
    level = models.ForeignKey("GradeRule", on_delete=models.PROTECT, null=True, blank=True, related_name="descriptive_marks")
    revision = models.PositiveIntegerField(default=1, editable=False)
    is_absent = models.BooleanField(default=False)

    class Meta:
        ordering = ("enrollment__student__last_name", "enrollment__student__first_name", "subject__name")
        constraints = [
            models.UniqueConstraint(fields=("assessment", "enrollment", "subject"), name="academics_mark_unique"),
            models.CheckConstraint(condition=models.Q(score__gte=0), name="academics_mark_nonnegative"),
            models.CheckConstraint(condition=(models.Q(is_absent=True, score__isnull=True, level__isnull=True) | (models.Q(is_absent=False) & (models.Q(score__isnull=False, level__isnull=True) | models.Q(score__isnull=True, level__isnull=False)))), name="academics_mark_value_exclusive"),
        ]

    def __str__(self):
        return f"{self.enrollment.student.student_id} / {self.subject.name} / {self.score}"

    def clean(self):
        super().clean()
        preserve_fields(self, ("assessment_id", "enrollment_id", "subject_id"))
        if not (self.assessment_id and self.enrollment_id and self.subject_id and self.teaching_assignment_id):
            return
        assessment, enrollment, assignment = self.assessment, self.enrollment, self.teaching_assignment
        scheme = assessment.grading_scheme
        if self.is_absent:
            if self.score is not None or self.level_id:
                raise ValidationError("An absent student cannot also have a score or learning level.")
        elif scheme and scheme.mode == "descriptive":
            if self.score is not None or not self.level_id or self.level.scheme_id != scheme.pk:
                raise ValidationError("Select a learning level from this assessment's descriptive grading scheme.")
        elif self.score is None or self.level_id:
            raise ValidationError("Enter a numeric score for this assessment.")
        if assessment.status != Assessment.Status.OPEN:
            raise ValidationError("This assessment is not open for marks.")
        if self.score is not None and not Decimal("0") <= self.score <= assessment.maximum_score:
            raise ValidationError({"score": f"Enter a score between 0 and {assessment.maximum_score}."})
        if enrollment.academic_year_id != assessment.term.academic_year_id or enrollment.academic_class_id != assessment.academic_class_id or (assessment.stream_id and enrollment.stream_id != assessment.stream_id):
            raise ValidationError("This enrollment does not belong to the assessment's class and year.")
        if enrollment.enrollment_date > assessment.date or (enrollment.completion_date and enrollment.completion_date < assessment.date):
            raise ValidationError("The student was not enrolled in this class on the assessment date.")
        if assignment.subject_id != self.subject_id or assignment.academic_year_id != enrollment.academic_year_id or assignment.academic_class_id != enrollment.academic_class_id or (assignment.term_id and assignment.term_id != assessment.term_id) or (assignment.stream_id and assignment.stream_id != enrollment.stream_id):
            raise ValidationError("The teaching assignment does not cover this student, subject and period.")
        if not assignment.is_active or assignment.teacher.employment_status != Teacher.Status.ACTIVE or not assignment.teacher.user.is_active:
            raise ValidationError("The teaching assignment is no longer active.")


class MarkSubmission(AuditedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "In progress"
        SUBMITTED = "submitted", "Awaiting review"
        APPROVED = "approved", "Approved"
        RETURNED = "returned", "Returned for correction"

    assessment = models.ForeignKey(Assessment, on_delete=models.PROTECT, related_name="mark_submissions")
    assignment = models.ForeignKey(TeachingAssignment, on_delete=models.PROTECT, related_name="mark_submissions")
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    revision = models.PositiveIntegerField(default=0)
    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="submitted_mark_sheets")
    submitted_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="reviewed_mark_sheets")
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_note = models.TextField(blank=True)
    snapshot = models.JSONField(default=list, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("assessment", "assignment"), name="academics_submission_unique"),
            models.CheckConstraint(condition=models.Q(status__in=["draft", "submitted", "approved", "returned"]), name="academics_submission_status"),
        ]

    def __str__(self):
        return f"{self.assessment} / {self.assignment.subject} / {self.get_status_display()}"

    def clean(self):
        super().clean()
        preserve_fields(self, ("assessment_id", "assignment_id"))
        if self.assessment_id and self.assignment_id:
            assessment, assignment = self.assessment, self.assignment
            if assignment.academic_class_id != assessment.academic_class_id or assignment.academic_year_id != assessment.term.academic_year_id or (assignment.term_id and assignment.term_id != assessment.term_id) or (assessment.stream_id and assignment.stream_id and assignment.stream_id != assessment.stream_id):
                raise ValidationError("This teaching assignment does not belong to the assessment.")


class GradingScheme(AuditedModel):
    class Mode(models.TextChoices):
        NUMERIC = "numeric", "Numeric grades"
        DESCRIPTIVE = "descriptive", "Descriptive learning levels"

    class Aggregate(models.TextChoices):
        NONE = "none", "No aggregate"
        ALL = "all", "All graded subjects"
        BEST = "best", "Best N subjects, including required subjects"
        SELECTED = "selected", "Required subject combination only"

    section = models.ForeignKey("schools.Section", on_delete=models.PROTECT, related_name="grading_schemes")
    name = models.CharField(max_length=100)
    mode = models.CharField(max_length=12, choices=Mode.choices, default=Mode.NUMERIC)
    aggregate_mode = models.CharField(max_length=10, choices=Aggregate.choices, default=Aggregate.NONE)
    best_n = models.PositiveSmallIntegerField(null=True, blank=True)
    required_subjects = models.ManyToManyField(Subject, blank=True, related_name="required_in_schemes")
    is_active = models.BooleanField(default=False)

    class Meta:
        ordering = ("section__sort_order", "name", "pk")
        constraints = [models.UniqueConstraint(Lower("name"), "section", name="academics_grading_scheme_name")]

    def __str__(self):
        return f"{self.section} / {self.name}"

    def in_use(self):
        return bool(self.pk and self.assessments.filter(marks__isnull=False).exists())

    def clean(self):
        super().clean()
        preserve_fields(self, ("section_id",))
        if self.in_use():
            preserve_fields(self, ("name", "mode", "aggregate_mode", "best_n", "is_active"))
        if self.mode == self.Mode.DESCRIPTIVE and self.aggregate_mode != self.Aggregate.NONE:
            raise ValidationError("Descriptive learning levels do not use numeric aggregates.")
        if self.aggregate_mode == self.Aggregate.BEST and not self.best_n:
            raise ValidationError({"best_n": "Enter the number of subjects to aggregate."})

    def validate_configuration(self):
        rules = list(self.rules.order_by("minimum", "pk"))
        if not rules:
            raise ValidationError("Add grade rules or learning levels before activating this scheme.")
        if self.mode == self.Mode.NUMERIC:
            from .grading import numeric_intervals
            boundary = Decimal("0")
            for rule, upper in numeric_intervals(rules):
                if rule.minimum != boundary:
                    raise ValidationError("Numeric grade ranges must cover 0 to 100 without gaps or overlaps.")
                boundary = upper
                if self.aggregate_mode != self.Aggregate.NONE and rule.points is None:
                    raise ValidationError("Each numeric grade needs points when aggregates are enabled.")
            if boundary != Decimal("100"):
                raise ValidationError("Numeric grade ranges must end at 100 percent.")
        if self.required_subjects.exclude(section_id=self.section_id).exists():
            raise ValidationError("Required subjects must belong to this scheme's section.")
        required_count = self.required_subjects.count()
        if self.aggregate_mode == self.Aggregate.SELECTED and not required_count:
            raise ValidationError("Choose the required subject combination.")
        if self.aggregate_mode == self.Aggregate.BEST and required_count > self.best_n:
            raise ValidationError("Best N must include every required subject.")


def validate_rule_edit(record):
    preserve_fields(record, ("scheme_id",))
    if record.scheme_id and (record.scheme.is_active or record.scheme.in_use()):
        raise ValidationError("Rules belong to an inactive, unused scheme. Create a new scheme to change rules already used for marks.")


class GradeRule(AuditedModel):
    scheme = models.ForeignKey(GradingScheme, on_delete=models.PROTECT, related_name="rules")
    label = models.CharField(max_length=60)
    minimum = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    maximum = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    points = models.PositiveSmallIntegerField(null=True, blank=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ("scheme__name", "sort_order", "-minimum", "pk")
        constraints = [models.UniqueConstraint(Lower("label"), "scheme", name="academics_grade_label_unique")]

    def __str__(self):
        return f"{self.scheme.name} / {self.label}"

    def clean(self):
        super().clean()
        validate_rule_edit(self)
        if not self.scheme_id:
            return
        if self.scheme.mode == "descriptive":
            if any(value is not None for value in (self.minimum, self.maximum, self.points)):
                raise ValidationError("Descriptive levels use labels and display order only.")
            return
        if self.minimum is None or self.maximum is None or not Decimal("0") <= self.minimum < self.maximum <= Decimal("100"):
            raise ValidationError("Enter percentage boundaries with 0 <= minimum < maximum <= 100.")
        if self.scheme.rules.exclude(pk=self.pk).filter(minimum__lt=self.maximum, maximum__gt=self.minimum).exists():
            raise ValidationError("This grade range overlaps another rule.")


class DivisionRule(AuditedModel):
    scheme = models.ForeignKey(GradingScheme, on_delete=models.PROTECT, related_name="divisions")
    label = models.CharField(max_length=60)
    minimum = models.PositiveIntegerField()
    maximum = models.PositiveIntegerField()

    class Meta:
        ordering = ("scheme__name", "minimum", "pk")
        constraints = [models.UniqueConstraint(Lower("label"), "scheme", name="academics_division_label_unique"), models.CheckConstraint(condition=models.Q(maximum__gte=models.F("minimum")), name="academics_division_range")]

    def __str__(self):
        return f"{self.scheme.name} / {self.label} ({self.minimum}–{self.maximum})"

    def clean(self):
        super().clean()
        validate_rule_edit(self)
        if not self.scheme_id:
            return
        if self.scheme.mode != "numeric" or self.scheme.aggregate_mode == "none":
            raise ValidationError("Divisions require numeric aggregate grading.")
        if self.minimum is not None and self.maximum is not None:
            if self.minimum > self.maximum or self.scheme.divisions.exclude(pk=self.pk).filter(minimum__lte=self.maximum, maximum__gte=self.minimum).exists():
                raise ValidationError("Division ranges must be ordered and cannot overlap.")
