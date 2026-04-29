from django.core.management.base import BaseCommand
from ticket.models import PendingRegistration
from django.utils import timezone


class Command(BaseCommand):
    help = 'Clean up expired pending registrations'

    def handle(self, *args, **options):
        expired_count = PendingRegistration.objects.filter(
            created_at__lt=timezone.now() - timezone.timedelta(minutes=30)
        ).count()

        PendingRegistration.objects.filter(
            created_at__lt=timezone.now() - timezone.timedelta(minutes=30)
        ).delete()

        self.stdout.write(
            self.style.SUCCESS(f'Deleted {expired_count} expired pending registrations')
        )