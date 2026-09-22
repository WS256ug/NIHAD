from django.core.exceptions import ValidationError
from django.db import models
from apps.schools.models import AuditedModel
from apps.students.models import preserve_fields


class StudentReport(AuditedModel):
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Awaiting class-teacher comment'
        REVIEW = 'review', 'Awaiting headteacher review'
        APPROVED = 'approved', 'Approved'
        PUBLISHED = 'published', 'Published'

    assessment = models.ForeignKey('academics.Assessment', on_delete=models.PROTECT, related_name='reports')
    enrollment = models.ForeignKey('students.Enrollment', on_delete=models.PROTECT, related_name='reports')
    version = models.PositiveIntegerField(default=1)
    is_current = models.BooleanField(default=True)
    previous = models.OneToOneField('self', on_delete=models.PROTECT, null=True, blank=True, related_name='replacement')
    correction_reason = models.TextField(blank=True, max_length=2000)
    snapshot = models.JSONField(default=dict, blank=True)
    teacher_comment = models.TextField(blank=True, max_length=2000)
    headteacher_comment = models.TextField(blank=True, max_length=2000)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ('-assessment__date', 'enrollment__student__last_name', 'enrollment__student__first_name', '-version')
        constraints = [
            models.UniqueConstraint(fields=('assessment', 'enrollment', 'version'), name='reports_version_unique'),
            models.UniqueConstraint(fields=('assessment', 'enrollment'), condition=models.Q(is_current=True), name='reports_current_unique'),
            models.CheckConstraint(condition=models.Q(status__in=['draft', 'review', 'approved', 'published']), name='reports_valid_status'),
            models.CheckConstraint(condition=~models.Q(status='published') | models.Q(published_at__isnull=False), name='reports_publication_time'),
        ]

    def __str__(self):
        return f'{self.enrollment.student.student_id} / {self.assessment.assessment_type} / v{self.version}'

    def clean(self):
        super().clean()
        preserve_fields(self, ('assessment_id', 'enrollment_id', 'version', 'previous_id', 'correction_reason'))
        if self.pk:
            previous = StudentReport.objects.get(pk=self.pk)
            if previous.status == self.Status.PUBLISHED:
                preserve_fields(self, ('snapshot', 'teacher_comment', 'headteacher_comment', 'status', 'published_at'))
            elif previous.status == self.Status.APPROVED:
                preserve_fields(self, ('snapshot', 'teacher_comment', 'headteacher_comment'))
        if self.status != self.Status.DRAFT and (not self.snapshot or not self.teacher_comment.strip()):
            raise ValidationError('Complete results and a class-teacher comment are required.')
        if self.status in (self.Status.APPROVED, self.Status.PUBLISHED) and not self.headteacher_comment.strip():
            raise ValidationError('Approval requires a headteacher comment.')
        if self.assessment_id and self.enrollment_id:
            if self.assessment.academic_class_id != self.enrollment.academic_class_id or self.assessment.term.academic_year_id != self.enrollment.academic_year_id:
                raise ValidationError('The report enrollment must match its assessment.')
