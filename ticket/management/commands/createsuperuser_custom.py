from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import transaction

User = get_user_model()


class Command(BaseCommand):
    help = 'Create a superuser with automatically verified email'

    def handle(self, *args, **options):
        with transaction.atomic():
            # Используем стандартную команду createsuperuser
            call_command('createsuperuser', interactive=True)

            # Находим последнего созданного суперпользователя и подтверждаем его email
            latest_superuser = User.objects.filter(is_superuser=True).order_by('-date_joined').first()
            if latest_superuser:
                latest_superuser.is_email_verified = True
                latest_superuser.save()
                self.stdout.write(
                    self.style.SUCCESS(f'Superuser {latest_superuser.email} created with verified email!')
                )