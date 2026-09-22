from django.core.management.base import BaseCommand, CommandError
from apps.schools.backups import restore_backup, verify_backup


class Command(BaseCommand):
    help = 'Verify a backup or restore it into an empty database and empty private media directory.'
    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument('directory')
        parser.add_argument('--verify-only', action='store_true')
        parser.add_argument('--maintenance-confirmed', action='store_true')

    def handle(self, *args, **options):
        if options['verify_only']:
            manifest = verify_backup(options['directory'])
            self.stdout.write(self.style.SUCCESS(f'Backup verified ({len(manifest["files"])} files).'))
            return
        if not options['maintenance_confirmed']:
            raise CommandError('Stop the application, configure an empty target, then pass --maintenance-confirmed.')
        restore_backup(options['directory'])
        self.stdout.write(self.style.SUCCESS('Restored into the empty target. Run migrations, check record counts and verify private media before starting the application.'))
