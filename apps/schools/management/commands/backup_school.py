from datetime import datetime, timezone
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from apps.schools.backups import create_backup, verify_backup


class Command(BaseCommand):
    help = 'Back up the database and private media after application writes have been stopped.'

    def add_arguments(self, parser):
        parser.add_argument('--output')
        parser.add_argument('--maintenance-confirmed', action='store_true')

    def handle(self, *args, **options):
        if not options['maintenance_confirmed']:
            raise CommandError('Stop application writes first, then pass --maintenance-confirmed for a consistent database/media backup.')
        destination = options['output'] or settings.BACKUP_ROOT / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        path = create_backup(destination)
        manifest = verify_backup(path)
        self.stdout.write(self.style.SUCCESS(f'Backup verified: {path} ({len(manifest["files"])} files). Store it securely off-site.'))
