from django.core.exceptions import ValidationError
from django.db import models
from apps.schools.models import AuditedModel
from apps.students.models import preserve_fields


def higher_classes(source):
    """Progress follows configured section order, then class order."""
    return models.Q(section_id=source.section_id, sort_order__gt=source.sort_order) | models.Q(section__sort_order__gt=source.section.sort_order)


class PromotionBatch(AuditedModel):
    source_year = models.ForeignKey('schools.AcademicYear', on_delete=models.PROTECT, related_name='outgoing_batches')
    source_class = models.ForeignKey('schools.AcademicClass', on_delete=models.PROTECT, related_name='outgoing_batches')
    source_stream = models.ForeignKey('schools.Stream', on_delete=models.PROTECT, null=True, blank=True, related_name='outgoing_batches')
    destination_year = models.ForeignKey('schools.AcademicYear', on_delete=models.PROTECT, null=True, blank=True, related_name='incoming_batches')
    destination_class = models.ForeignKey('schools.AcademicClass', on_delete=models.PROTECT, null=True, blank=True, related_name='incoming_batches')
    destination_stream = models.ForeignKey('schools.Stream', on_delete=models.PROTECT, null=True, blank=True, related_name='incoming_batches')
    completion_date = models.DateField()
    enrollment_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=12, choices=[('draft', 'Draft'), ('confirmed', 'Confirmed')], default='draft')
    revision = models.PositiveIntegerField(default=0)
    confirmed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ('-created_at', '-pk')
        constraints = [models.CheckConstraint(condition=models.Q(status__in=['draft', 'confirmed']), name='promotions_batch_status'), models.CheckConstraint(condition=(models.Q(status='draft', confirmed_at__isnull=True) | models.Q(status='confirmed', confirmed_at__isnull=False)), name='promotions_confirmation_time')]

    def __str__(self):
        return f'{self.source_year} / {self.source_class.name} / Batch {self.pk or "new"}'

    def clean(self):
        super().clean()
        identity = ('source_year_id', 'source_class_id', 'source_stream_id', 'destination_year_id', 'destination_class_id', 'destination_stream_id', 'completion_date', 'enrollment_date')
        preserve_fields(self, identity)
        if self.pk and PromotionBatch.objects.filter(pk=self.pk, status='confirmed').exists():
            preserve_fields(self, ('status', 'revision', 'confirmed_at'))
        if not self.source_year_id or not self.source_class_id:
            return
        if self.source_year.school_id != self.source_class.section.school_id or (self.source_stream_id and self.source_stream.academic_class_id != self.source_class_id):
            raise ValidationError('Source year, class and stream must belong to the same school and class context.')
        if self.completion_date and not self.source_year.start_date <= self.completion_date <= self.source_year.end_date:
            raise ValidationError({'completion_date': 'Completion date must fall within the source year.'})
        if self.destination_year_id:
            year = self.destination_year
            if year.school_id != self.source_year.school_id or year.start_date <= self.source_year.end_date or not year.is_active:
                raise ValidationError('Choose an active destination year after the source year.')
            if not self.enrollment_date or not year.start_date <= self.enrollment_date <= year.end_date:
                raise ValidationError({'enrollment_date': 'Enter an enrollment date within the destination year.'})
        elif self.enrollment_date or self.destination_class_id:
            raise ValidationError('Choose a destination year for new enrollments.')
        if self.destination_class_id and (self.destination_class.section.school_id != self.source_year.school_id or not self.destination_class.is_active or not self.destination_class.section.is_active):
            raise ValidationError('Choose an active destination class from this school.')
        if self.destination_class_id and not type(self.source_class).objects.filter(pk=self.destination_class_id).filter(higher_classes(self.source_class)).exists():
            raise ValidationError({'destination_class': 'Choose a higher class using the configured section and class order.'})
        if self.destination_stream_id and (self.destination_stream.academic_class_id != self.destination_class_id or not self.destination_stream.is_active):
            raise ValidationError('Choose an active stream from the destination class.')


class PromotionDecision(AuditedModel):
    class Decision(models.TextChoices):
        PROMOTE = 'promoted', 'Promoted'
        PROBATION = 'probation', 'Promoted On Probation'
        REPEAT = 'repeating', 'Try Again'
        TRANSFER = 'transferred', 'Transfer out'
        WITHDRAW = 'withdrawn', 'Withdraw'
        GRADUATE = 'graduated', 'Graduate'

    @classmethod
    def current_choices(cls):
        return [(value, value.label) for value in (cls.Decision.PROMOTE, cls.Decision.PROBATION, cls.Decision.REPEAT)]

    batch = models.ForeignKey(PromotionBatch, on_delete=models.PROTECT, related_name='decisions')
    enrollment = models.ForeignKey('students.Enrollment', on_delete=models.PROTECT, related_name='promotion_decisions')
    decision = models.CharField(max_length=12, choices=Decision.choices)
    selected = models.BooleanField(default=True)
    notes = models.CharField(max_length=500, blank=True)
    new_enrollment = models.OneToOneField('students.Enrollment', on_delete=models.PROTECT, null=True, blank=True, related_name='promotion_origin')
    snapshot = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ('enrollment__student__last_name', 'enrollment__student__first_name', 'pk')
        constraints = [models.UniqueConstraint(fields=('batch', 'enrollment'), name='promotions_decision_unique'), models.CheckConstraint(condition=models.Q(decision__in=['promoted', 'probation', 'repeating', 'transferred', 'withdrawn', 'graduated']), name='promotions_decision_valid')]

    def __str__(self):
        return f'{self.enrollment.student.student_id} / {self.get_decision_display()}'

    def clean(self):
        super().clean()
        preserve_fields(self, ('batch_id', 'enrollment_id'))
        if self.batch_id and PromotionBatch.objects.filter(pk=self.batch_id, status='confirmed').exists():
            if self._state.adding:
                raise ValidationError('Confirmed promotion batches cannot accept new decisions.')
            preserve_fields(self, ('decision', 'selected', 'notes', 'new_enrollment_id', 'snapshot'))
        if self.batch_id and self.enrollment_id:
            if self.enrollment.academic_year_id != self.batch.source_year_id or self.enrollment.academic_class_id != self.batch.source_class_id or (self.batch.source_stream_id and self.enrollment.stream_id != self.batch.source_stream_id):
                raise ValidationError('This enrollment does not belong to the batch source.')
