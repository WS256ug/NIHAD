"""Audited grade correction for an open assessment with no generated reports."""
import json
from pathlib import Path
from uuid import uuid4

from django.contrib.admin.models import CHANGE, LogEntry
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.accounts.permissions import has_role
from apps.academics.models import Assessment, DivisionRule, GradeRule, GradingScheme
from apps.schools.services import lock_school, write_record


class Command(BaseCommand):
    help = 'Preview or apply numeric grade bands to one open assessment without reports.'

    def add_arguments(self, parser):
        parser.add_argument('--assessment', type=int, required=True)
        parser.add_argument('--expected-scheme', type=int, required=True, help='Current scheme ID; use 0 only when no scheme is linked.')
        parser.add_argument('--source-scheme', type=int, help='Copy an existing active numeric scheme, including its grade bands.')
        parser.add_argument('--actor', required=True, help='School administrator username')
        parser.add_argument('--rules', help='JSON grade-band file; omit when using --source-scheme')
        parser.add_argument('--apply', action='store_true')

    @transaction.atomic
    def handle(self, *args, **options):
        try:
            return self.correct(options)
        except (ValidationError, ValueError, TypeError, KeyError, OSError) as exc:
            raise CommandError(str(exc)) from exc

    def correct(self, options):
        actor = User.objects.filter(username=options['actor']).first()
        if not actor or not has_role(actor, User.Role.SCHOOL_ADMIN):
            raise CommandError('An active school administrator is required.')
        school = lock_school()
        assessment = Assessment.objects.select_for_update().filter(pk=options['assessment']).first()
        if not assessment or assessment.academic_class.section.school_id != school.pk:
            raise CommandError('Assessment not found in this school.')
        if assessment.status != 'open' or assessment.reports.exists():
            raise CommandError('Requires an open assessment with no generated reports. Existing reports require the report correction workflow.')
        current = assessment.grading_scheme
        if (assessment.grading_scheme_id or 0) != options['expected_scheme']:
            raise CommandError('Expected grading scheme does not match; inspect the assessment again.')
        if bool(options.get('source_scheme')) == bool(options.get('rules')):
            raise CommandError('Provide either --source-scheme or --rules, not both.')
        source = (GradingScheme.objects.select_for_update().filter(
            pk=options['source_scheme'], section__school=school, is_active=True).first()
            if options.get('source_scheme') else current)
        if not source or source.mode != 'numeric':
            raise CommandError('Choose a numeric source scheme; --source-scheme must be active and belong to this school.')
        if options.get('source_scheme'):
            source.validate_configuration()
        if source.section_id != assessment.academic_class.section_id and source.required_subjects.exists():
            raise CommandError('The source has required subjects in another section. Configure their Top-class equivalents before copying this aggregation scheme.')
        if assessment.marks.filter(level__isnull=False).exists():
            raise CommandError('Assessment contains descriptive results.')
        fields = ('label', 'minimum', 'maximum', 'points')
        bands = (list(source.rules.order_by('sort_order', 'pk').values(*fields))
                 if options.get('source_scheme') else json.loads(Path(options['rules']).read_text(encoding='utf-8-sig')))
        if not isinstance(bands, list) or not bands:
            raise CommandError('Rules must be a nonempty JSON list.')
        if any(not isinstance(band, dict) or set(band) != set(fields) for band in bands):
            raise CommandError('Each rule requires label, minimum, maximum and points.')
        old = list(current.rules.order_by('minimum').values(*fields)) if current else []
        self.stdout.write(f'Assessment {assessment.pk}: {assessment}; current scheme {assessment.grading_scheme_id}')
        self.stdout.write(f'Source scheme: {source.pk} / {source.section} / {source.name}')
        self.stdout.write(f'Current bands: {old}')
        self.stdout.write(f'Proposed bands: {bands}')
        target = write_record(GradingScheme(
            section=assessment.academic_class.section, name=f'Corrected grades {uuid4().hex[:12]}',
            mode='numeric', aggregate_mode=source.aggregate_mode, best_n=source.best_n,
        ), actor, 'Created grading correction version.')
        target.required_subjects.set(source.required_subjects.all())
        for index, band in enumerate(bands):
            write_record(GradeRule(scheme=target, sort_order=index, **band), actor, 'Installed supplied grade band.')
        for rule in source.divisions.all():
            write_record(DivisionRule(scheme=target, label=rule.label, minimum=rule.minimum,
                                     maximum=rule.maximum), actor, 'Preserved division configuration.')
        target.validate_configuration()
        target.is_active = True
        write_record(target, actor, 'Validated corrected grade bands.')
        # Explicit exception to the normal immutable scheme link: locked open
        # numeric assessment, no reports, unchanged marks, separate old scheme.
        Assessment.objects.filter(pk=assessment.pk).update(
            grading_scheme=target, updated_by=actor, updated_at=timezone.now())
        LogEntry.objects.create(user=actor, content_type=ContentType.objects.get_for_model(assessment),
                                object_id=str(assessment.pk), object_repr=str(assessment)[:200],
                                action_flag=CHANGE,
                                change_message=f'Corrected grading scheme {options["expected_scheme"] or "None"} -> {target.pk}; copied source {source.pk}; marks preserved.')
        if not options['apply']:
            transaction.set_rollback(True)
            self.stdout.write('PREVIEW ONLY: validation passed; no changes saved.')
        else:
            self.stdout.write(self.style.SUCCESS(f'Applied scheme {target.pk}. Reload the marks page. Other assessments retain their schemes.'))
