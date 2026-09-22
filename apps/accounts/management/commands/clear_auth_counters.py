from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.accounts.models import AuthenticationBucket


class Command(BaseCommand):
    help = 'Delete expired authentication counters older than one day.'

    def handle(self, *args, **options):
        count, _ = AuthenticationBucket.objects.filter(window_started__lt=timezone.now() - timedelta(days=1)).delete()
        self.stdout.write(f'Removed {count} expired counters.')
