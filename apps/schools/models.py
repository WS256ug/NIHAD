"""One school's configurable structure. Relationships are preserved once created."""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, RegexValidator
from django.db import models
from django.db.models.functions import Lower


class AuditedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, editable=False, on_delete=models.SET_NULL, related_name="+")
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, editable=False, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        abstract = True


class School(AuditedModel):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    name = models.CharField(max_length=160)
    motto = models.CharField(max_length=200, blank=True)
    address = models.TextField(blank=True)
    phone = models.CharField(max_length=40, blank=True)
    email = models.EmailField(blank=True)
    website = models.URLField(blank=True)
    currency_code = models.CharField(max_length=3, default="UGX", validators=[RegexValidator(r"^[A-Z]{3}$", "Use a three-letter uppercase currency code, such as UGX.")])
    enable_ranking = models.BooleanField(default=False)
    require_fee_clearance_for_reports = models.BooleanField(default=True)
    current_academic_year = models.ForeignKey("AcademicYear", null=True, blank=True, on_delete=models.PROTECT, related_name="current_for_schools")
    current_term = models.ForeignKey("Term", null=True, blank=True, on_delete=models.PROTECT, related_name="current_for_schools")

    class Meta:
        verbose_name = "school profile"
        constraints = [
            models.CheckConstraint(condition=models.Q(id=1), name="schools_single_profile"),
            models.CheckConstraint(condition=models.Q(current_term__isnull=True) | models.Q(current_academic_year__isnull=False), name="schools_term_requires_year"),
        ]

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        self.name = self.name.strip()
        if not self.name:
            raise ValidationError({"name": "Enter the school name."})
        if self.current_academic_year_id:
            year = self.current_academic_year
            if year.school_id != self.pk or not year.is_active:
                raise ValidationError("The current academic year must be active and belong to this school.")
        if self.current_term_id:
            term = self.current_term
            if not term.is_active or term.academic_year_id != self.current_academic_year_id:
                raise ValidationError("The current term must be active and belong to the current academic year.")


class ConfigurationRecord(AuditedModel):
    name = models.CharField(max_length=80)
    is_active = models.BooleanField(default=True)

    class Meta:
        abstract = True

    def clean(self):
        super().clean()
        self.name = self.name.strip()
        if not self.name:
            raise ValidationError({"name": "Enter a name."})

    def check_parent_unchanged(self, field):
        if self.pk and not self._state.adding:
            original = type(self).objects.filter(pk=self.pk).values_list(field, flat=True).first()
            if original != getattr(self, field):
                raise ValidationError("The parent cannot be changed. Create a new record to preserve existing history.")


class Section(ConfigurationRecord):
    school = models.ForeignKey(School, on_delete=models.PROTECT, related_name="sections")
    description = models.TextField(blank=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ("sort_order", "name", "pk")
        constraints = [models.UniqueConstraint(Lower("name"), "school", name="schools_section_name_unique")]

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        self.check_parent_unchanged("school_id")
        if self.pk and not self.is_active and self.classes.filter(is_active=True).exists():
            raise ValidationError("Deactivate this section's active classes first.")


class AcademicYear(ConfigurationRecord):
    school = models.ForeignKey(School, on_delete=models.PROTECT, related_name="academic_years")
    start_date = models.DateField()
    end_date = models.DateField()

    class Meta:
        ordering = ("-start_date", "name", "pk")
        constraints = [
            models.UniqueConstraint(Lower("name"), "school", name="schools_year_name_unique"),
            models.CheckConstraint(condition=models.Q(end_date__gte=models.F("start_date")), name="schools_year_dates_ordered"),
        ]

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        self.check_parent_unchanged("school_id")
        if self.start_date and self.end_date:
            if self.end_date < self.start_date:
                raise ValidationError({"end_date": "The end date must be on or after the start date."})
            overlaps = AcademicYear.objects.filter(school_id=self.school_id, start_date__lte=self.end_date, end_date__gte=self.start_date).exclude(pk=self.pk)
            if overlaps.exists():
                raise ValidationError("Academic years for this school cannot overlap.")
            if self.pk and self.terms.filter(models.Q(start_date__lt=self.start_date) | models.Q(end_date__gt=self.end_date)).exists():
                raise ValidationError("The academic year must contain all of its existing terms.")
        if self.pk and not self.is_active:
            if School.objects.filter(current_academic_year_id=self.pk).exists():
                raise ValidationError("Select a different current academic year or clear the current period first.")
            if self.terms.filter(is_active=True).exists():
                raise ValidationError("Deactivate this year's active terms first.")


class Term(ConfigurationRecord):
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.PROTECT, related_name="terms")
    sequence = models.PositiveSmallIntegerField(default=1, validators=[MinValueValidator(1)])
    start_date = models.DateField()
    end_date = models.DateField()

    class Meta:
        ordering = ("-academic_year__start_date", "sequence", "pk")
        constraints = [
            models.UniqueConstraint(Lower("name"), "academic_year", name="schools_term_name_unique"),
            models.UniqueConstraint(fields=("academic_year", "sequence"), name="schools_term_sequence_unique"),
            models.CheckConstraint(condition=models.Q(sequence__gte=1), name="schools_term_sequence_positive"),
            models.CheckConstraint(condition=models.Q(end_date__gte=models.F("start_date")), name="schools_term_dates_ordered"),
        ]

    def __str__(self):
        return f"{self.academic_year} / {self.name}"

    def clean(self):
        super().clean()
        self.check_parent_unchanged("academic_year_id")
        if self.academic_year_id:
            if self.is_active and not self.academic_year.is_active:
                raise ValidationError("Active terms require an active academic year.")
            if self.start_date and self.end_date:
                if self.end_date < self.start_date:
                    raise ValidationError({"end_date": "The end date must be on or after the start date."})
                if self.start_date < self.academic_year.start_date or self.end_date > self.academic_year.end_date:
                    raise ValidationError("Term dates must fall within their academic year.")
                overlaps = Term.objects.filter(academic_year_id=self.academic_year_id, start_date__lte=self.end_date, end_date__gte=self.start_date).exclude(pk=self.pk)
                if overlaps.exists():
                    raise ValidationError("Terms in the same academic year cannot overlap.")
        if self.pk and not self.is_active and School.objects.filter(current_term_id=self.pk).exists():
            raise ValidationError("Select a different current term or clear the current term first.")


class AcademicClass(ConfigurationRecord):
    section = models.ForeignKey(Section, on_delete=models.PROTECT, related_name="classes")
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name_plural = "academic classes"
        ordering = ("section__sort_order", "sort_order", "name", "pk")
        constraints = [models.UniqueConstraint(Lower("name"), "section", name="schools_class_name_unique")]

    def __str__(self):
        return f"{self.section} / {self.name}"

    def clean(self):
        super().clean()
        self.check_parent_unchanged("section_id")
        if self.section_id and self.is_active and not self.section.is_active:
            raise ValidationError("Active classes require an active section.")
        if self.pk and not self.is_active and self.streams.filter(is_active=True).exists():
            raise ValidationError("Deactivate this class's active streams first.")


class Stream(ConfigurationRecord):
    academic_class = models.ForeignKey(AcademicClass, on_delete=models.PROTECT, related_name="streams")

    class Meta:
        ordering = ("academic_class__section__sort_order", "academic_class__sort_order", "name", "pk")
        constraints = [models.UniqueConstraint(Lower("name"), "academic_class", name="schools_stream_name_unique")]

    def __str__(self):
        return f"{self.academic_class} / {self.name}"

    def clean(self):
        super().clean()
        self.check_parent_unchanged("academic_class_id")
        if self.academic_class_id and self.is_active:
            if not self.academic_class.is_active or not self.academic_class.section.is_active:
                raise ValidationError("Active streams require an active class and section.")
