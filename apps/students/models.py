from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.functions import Lower
from django.utils import timezone

from apps.schools.models import AuditedModel
from .photos import photo_path, photo_storage


def preserve_fields(record, fields):
    if getattr(record, "_superuser_admin_correction", False):
        return
    if record.pk and not record._state.adding:
        original = type(record).objects.get(pk=record.pk)
        if any(getattr(original, field) != getattr(record, field) for field in fields):
            raise ValidationError("Existing identity and enrollment history cannot be reassigned.")


class StudentNumber(models.Model):
    school = models.OneToOneField("schools.School", on_delete=models.PROTECT, primary_key=True)
    last_value = models.PositiveBigIntegerField(default=0)


class Student(AuditedModel):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        PROMOTED = "promoted", "Promoted"
        REPEATING = "repeating", "Repeating"
        TRANSFERRED = "transferred", "Transferred"
        WITHDRAWN = "withdrawn", "Withdrawn"
        GRADUATED = "graduated", "Graduated"
        INACTIVE = "inactive", "Inactive"

    class Religion(models.TextChoices):
        MOSLEM = "Moslem", "Moslem"
        CHRISTIAN = "Christian", "Christian"
        OTHER = "Other", "Other"

    class Gender(models.TextChoices):
        FEMALE = "female", "Female"
        MALE = "male", "Male"

    school = models.ForeignKey("schools.School", on_delete=models.PROTECT, related_name="students")
    student_id = models.CharField(max_length=30, unique=True, editable=False)
    first_name = models.CharField(max_length=100)
    middle_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100)
    photo = models.ImageField(storage=photo_storage, upload_to=photo_path, blank=True)
    gender = models.CharField(max_length=12, choices=Gender.choices)
    date_of_birth = models.DateField()
    admission_date = models.DateField(default=timezone.localdate)
    admission_number = models.CharField(max_length=50, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.ACTIVE, db_index=True)
    religion = models.CharField(max_length=100, choices=Religion.choices, blank=True)
    portal_user = models.OneToOneField(settings.AUTH_USER_MODEL, null=True, blank=True, editable=False, on_delete=models.PROTECT, related_name="portal_student")

    class Meta:
        ordering = ("last_name", "first_name", "pk")
        constraints = [
            models.CheckConstraint(condition=models.Q(date_of_birth__lte=models.F("admission_date")), name="students_birth_before_admission"),
            models.CheckConstraint(condition=models.Q(status__in=["active", "promoted", "repeating", "transferred", "withdrawn", "graduated", "inactive"]), name="students_valid_status"),
            models.CheckConstraint(condition=models.Q(gender__in=["female", "male"]), name="students_valid_gender"),
            models.CheckConstraint(condition=~models.Q(student_id=""), name="students_id_not_empty"),
            models.UniqueConstraint(Lower("admission_number"), "school", condition=~models.Q(admission_number=""), name="students_admission_unique", violation_error_message="This admission number is already in use."),
        ]

    @property
    def full_name(self):
        return " ".join(filter(None, [self.first_name, self.middle_name, self.last_name]))

    def __str__(self):
        return f"{self.student_id} / {self.full_name}"

    def clean(self):
        super().clean()
        preserve_fields(self, ("student_id", "school_id"))
        for field in ("first_name", "last_name", "middle_name", "admission_number"):
            setattr(self, field, getattr(self, field).strip())
        if not self.first_name or not self.last_name:
            raise ValidationError("Enter the student's first and last names.")
        if self.admission_number and Student.objects.filter(school_id=self.school_id, admission_number__iexact=self.admission_number).exclude(pk=self.pk).exists():
            raise ValidationError({"admission_number": "This admission number is already in use."})
        if self.date_of_birth and self.admission_date and self.date_of_birth > self.admission_date:
            raise ValidationError({"date_of_birth": "Birth date must be on or before admission."})
        if self.admission_date and self.admission_date > timezone.localdate():
            raise ValidationError({"admission_date": "Admission date cannot be in the future."})
        if self.pk and not self._state.adding:
            if self.admission_date and self.enrollments.filter(enrollment_date__lt=self.admission_date).exists():
                raise ValidationError("Admission cannot be later than an existing enrollment.")
            if self.status not in (self.Status.ACTIVE, self.Status.PROMOTED, self.Status.REPEATING) and self.enrollments.filter(status=Enrollment.Status.CURRENT).exists():
                raise ValidationError("Close current enrollments before marking the student as having left or inactive.")


class Guardian(AuditedModel):
    school = models.ForeignKey("schools.School", on_delete=models.PROTECT, related_name="guardians")
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="guardian_profile")
    first_name = models.CharField(max_length=150, default="")
    last_name = models.CharField(max_length=150, default="")
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=40)
    nin = models.CharField("National Identification Number (NIN)", max_length=50, blank=True)
    address = models.TextField(blank=True)

    class Meta:
        ordering = ("last_name", "first_name", "pk")

    def __str__(self):
        return f"{self.first_name} {self.last_name}".strip()

    def clean(self):
        super().clean()
        preserve_fields(self, ("school_id",))
        if self.pk and Guardian.objects.filter(pk=self.pk, user__isnull=False).exists():
            preserve_fields(self, ("user_id",))
        if self.user_id and self.user.role != "guardian":
            raise ValidationError("Link an independent account with the Guardian role.")
        self.first_name, self.last_name = self.first_name.strip(), self.last_name.strip()
        if not self.first_name or not self.last_name:
            raise ValidationError("Enter the guardian's first and last names.")
        self.phone = self.phone.strip()
        if not self.phone:
            raise ValidationError({"phone": "Enter a contact phone number."})


class StudentGuardian(AuditedModel):
    student = models.ForeignKey(Student, on_delete=models.PROTECT, related_name="guardian_links")
    guardian = models.ForeignKey(Guardian, on_delete=models.PROTECT, related_name="student_links")
    relationship = models.CharField(max_length=60)
    is_primary = models.BooleanField(default=False)
    is_emergency_contact = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("-is_active", "-is_primary", "pk")
        constraints = [
            models.UniqueConstraint(fields=("student", "guardian"), name="students_guardian_link_unique", violation_error_message="This guardian is already linked. Edit or reactivate the existing link."),
            models.UniqueConstraint(fields=("student",), condition=models.Q(is_primary=True, is_active=True), name="students_one_primary_guardian", violation_error_message="This student already has a primary guardian. Unmark that guardian first."),
        ]

    def __str__(self):
        return f"{self.student.student_id} / {self.guardian}"

    def clean(self):
        super().clean()
        preserve_fields(self, ("student_id", "guardian_id"))
        self.relationship = self.relationship.strip()
        if not self.relationship:
            raise ValidationError({"relationship": "Enter the guardian's relationship to the student."})
        if self.student_id and self.guardian_id:
            if self.student.school_id != self.guardian.school_id:
                raise ValidationError("Student and guardian must belong to the same school.")
            if self.is_active and self.is_primary and StudentGuardian.objects.filter(student_id=self.student_id, is_active=True, is_primary=True).exclude(pk=self.pk).exists():
                raise ValidationError("This student already has a primary guardian. Unmark that guardian first.")


class Enrollment(AuditedModel):
    class Status(models.TextChoices):
        CURRENT = "current", "Current"
        COMPLETED = "completed", "Completed"
        PROMOTED = "promoted", "Promoted"
        REPEATING = "repeating", "Repeating"
        TRANSFERRED = "transferred", "Transferred"
        WITHDRAWN = "withdrawn", "Withdrawn"
        GRADUATED = "graduated", "Graduated"

    student = models.ForeignKey(Student, on_delete=models.PROTECT, related_name="enrollments")
    academic_year = models.ForeignKey("schools.AcademicYear", on_delete=models.PROTECT, related_name="enrollments")
    section = models.ForeignKey("schools.Section", on_delete=models.PROTECT, related_name="enrollments", editable=False)
    academic_class = models.ForeignKey("schools.AcademicClass", on_delete=models.PROTECT, related_name="enrollments")
    stream = models.ForeignKey("schools.Stream", null=True, blank=True, on_delete=models.PROTECT, related_name="enrollments")
    enrollment_date = models.DateField(default=timezone.localdate)
    completion_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.CURRENT)

    class Meta:
        ordering = ("-academic_year__start_date", "-enrollment_date", "-pk")
        constraints = [
            models.UniqueConstraint(fields=("student", "academic_year"), condition=models.Q(status="current"), name="students_current_enrollment_unique", violation_error_message="Close this student's current enrollment for this year first."),
            models.CheckConstraint(condition=models.Q(status__in=["current", "completed", "promoted", "repeating", "transferred", "withdrawn", "graduated"]), name="students_enrollment_valid_status"),
            models.CheckConstraint(condition=(models.Q(status="current", completion_date__isnull=True) | (~models.Q(status="current") & models.Q(completion_date__isnull=False))), name="students_enrollment_completion"),
            models.CheckConstraint(condition=models.Q(completion_date__isnull=True) | models.Q(completion_date__gte=models.F("enrollment_date")), name="students_enrollment_dates"),
        ]

    def __str__(self):
        return f"{self.student.student_id} / {self.academic_year} / {self.academic_class}"

    def clean(self):
        super().clean()
        preserve_fields(self, ("student_id", "academic_year_id", "section_id", "academic_class_id", "stream_id", "enrollment_date"))
        if self.pk and not self._state.adding:
            original = Enrollment.objects.get(pk=self.pk)
            if original.status != self.Status.CURRENT and (original.status != self.status or original.completion_date != self.completion_date):
                raise ValidationError("Closed enrollment history cannot be changed.")
        if not (self.student_id and self.academic_year_id and self.academic_class_id):
            return
        year, classroom, student = self.academic_year, self.academic_class, self.student
        if classroom.section_id != self.section_id or classroom.section.school_id != student.school_id or year.school_id != student.school_id:
            raise ValidationError("The year, section and class must belong to the student's school.")
        if self.stream_id and self.stream.academic_class_id != self.academic_class_id:
            raise ValidationError({"stream": "Choose a stream belonging to the selected class."})
        if self._state.adding:
            if not (year.is_active and classroom.is_active and classroom.section.is_active) or (self.stream_id and not self.stream.is_active):
                raise ValidationError("New enrollments require an active year, section, class and selected stream.")
            if student.status not in (Student.Status.ACTIVE, Student.Status.PROMOTED, Student.Status.REPEATING):
                raise ValidationError("Reactivate this student before adding an enrollment.")
        if self.enrollment_date:
            if not year.start_date <= self.enrollment_date <= year.end_date:
                raise ValidationError({"enrollment_date": "Enrollment date must fall within the academic year."})
            if self.enrollment_date < student.admission_date:
                raise ValidationError({"enrollment_date": "Enrollment cannot be before admission."})
        if self.status == self.Status.CURRENT and self.completion_date:
            raise ValidationError("A current enrollment cannot have a completion date.")
        if self.status != self.Status.CURRENT and not self.completion_date:
            raise ValidationError({"completion_date": "Enter the completion date."})
        if self.completion_date and self.enrollment_date:
            if not self.enrollment_date <= self.completion_date <= year.end_date:
                raise ValidationError({"completion_date": "Completion must be on or after enrollment and within the academic year."})
            if self.pk and self.marks.filter(assessment__date__gt=self.completion_date).exists():
                raise ValidationError('Completion date cannot exclude existing assessment results.')
        if self.enrollment_date:
            overlaps = Enrollment.objects.filter(student_id=self.student_id, academic_year_id=self.academic_year_id, enrollment_date__lte=self.completion_date or year.end_date).exclude(pk=self.pk)
            if overlaps.filter(models.Q(completion_date__isnull=True) | models.Q(completion_date__gte=self.enrollment_date)).exists():
                raise ValidationError("Enrollment dates cannot overlap for a student in the same academic year.")
