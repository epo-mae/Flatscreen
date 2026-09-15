from datetime import timedelta
from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.utils import timezone
from household.models import AccessAttempt, DisplayDevice, ActivityEntry
from shopping.models import Mutation, ShoppingItem
from presence.models import PresenceMutation
from planning.models import CalendarEvent, Chore, ChoreCompletion, HouseNotice


class Command(BaseCommand):
    help = 'Remove expired sessions, pairing requests and records beyond their retention windows.'

    def handle(self, *args, **options):
        now = timezone.now()
        AccessAttempt.objects.filter(created_at__lt=now - timedelta(minutes=15)).delete()
        DisplayDevice.objects.filter(approved=False, expires_at__lt=now - timedelta(days=1)).delete()
        # Keep idempotency receipts for 90 days. Clients must not replay older requests.
        Mutation.objects.filter(created_at__lt=now - timedelta(days=90)).delete()
        PresenceMutation.objects.filter(created_at__lt=now - timedelta(days=90)).delete()
        ShoppingItem.objects.filter(deleted_at__lt=now - timedelta(days=7)).delete()
        CalendarEvent.objects.filter(deleted_at__lt=now - timedelta(days=30)).delete()
        HouseNotice.objects.filter(deleted_at__lt=now - timedelta(days=30)).delete()
        HouseNotice.objects.filter(expires_at__lt=now - timedelta(days=30)).delete()
        Chore.objects.filter(deleted_at__lt=now - timedelta(days=30)).delete()
        ChoreCompletion.objects.filter(completed_at__lt=now - timedelta(days=365)).delete()
        ActivityEntry.objects.filter(created_at__lt=now - timedelta(days=90)).delete()
        call_command('clearsessions')
        self.stdout.write('Maintenance complete.')
