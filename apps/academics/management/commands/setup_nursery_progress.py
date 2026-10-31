"""Create editable nursery defaults without changing section numeric grades."""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from apps.accounts.models import User
from apps.academics.models import GradeRule, GradingScheme, Subject
from apps.academics.services import require_manager
from apps.schools.models import Section
from apps.schools.services import lock_school, write_record


class Command(BaseCommand):
    help = 'Create nursery progress levels and missing learning areas for a selected section.'

    def add_arguments(self, parser):
        parser.add_argument('--section', type=int, required=True)
        parser.add_argument('--actor', type=int, required=True)

    @transaction.atomic
    def handle(self, *args, **options):
        school = lock_school()
        actor = User.objects.filter(pk=options['actor'], is_active=True).first()
        if not actor:
            raise CommandError('Choose an active School Admin account.')
        require_manager(actor)
        section = Section.objects.filter(pk=options['section'], school=school, is_active=True).first()
        if not section:
            raise CommandError('Choose an active section in this school.')
        scheme = GradingScheme.objects.filter(section=section, nursery_only=True).first()
        if not scheme:
            scheme = write_record(GradingScheme(section=section, name='Nursery progress levels',
                                  mode='descriptive', nursery_only=True), actor, 'Created nursery progress defaults.')
            for order, label in enumerate(('Emerging', 'Developing', 'Achieved', 'Excellent')):
                write_record(GradeRule(scheme=scheme, label=label, sort_order=order), actor, 'Created nursery progress level.')
            scheme.validate_configuration()
            scheme.is_active = True
            write_record(scheme, actor, 'Activated nursery progress levels.')
        defaults = [('social', 'Social Development'), ('environment', 'My Environment'),
                    ('hygiene', 'Personal Hygiene'), ('numbers', 'Numbers'), ('language', 'Language'),
                    ('oral', 'Oral Expression'), ('writing', 'Pre-writing & Pre-reading'),
                    ('physical', 'Physical Development')]
        for key, name in defaults:
            if not Subject.objects.filter(section=section, report_group='main', name__iexact=name).exists():
                code = 'NUR-' + key.upper()
                if Subject.objects.filter(section=section, code__iexact=code).exists():
                    raise CommandError(f'Subject code {code} is already used; configure this learning area manually.')
                write_record(Subject(section=section, name=name, code=code, illustration=key), actor,
                             'Created editable nursery learning area.')
        self.stdout.write(self.style.SUCCESS(f'Nursery scheme {scheme.pk} ready. Assign learning areas to teachers, then enable Nursery progress report on the Baby/Middle exams and select this scheme.'))
