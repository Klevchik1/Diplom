from django.core.management.base import BaseCommand
from django.utils import timezone
from ticket.models import User
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Удаляет неподтверждённых пользователей, у которых истёк срок верификации (10 минут)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Показать, какие пользователи будут удалены, без фактического удаления',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        now = timezone.now()
        expiration_time = now - timezone.timedelta(minutes=10)

        # Находим пользователей для удаления:
        # - email не подтверждён
        # - не staff и не superuser (администраторов и менеджеров не трогаем)
        # - код был отправлен более 10 минут назад (или не отправлялся вообще)
        users_to_delete = User.objects.filter(
            is_email_verified=False,
            is_staff=False,
            is_superuser=False,
        ).filter(
            # Либо код отправлен и истёк, либо код никогда не отправлялся
            models.Q(email_verification_code_sent_at__lt=expiration_time) |
            models.Q(email_verification_code_sent_at__isnull=True)
        )

        count = users_to_delete.count()

        if count == 0:
            self.stdout.write(self.style.SUCCESS('Нет пользователей для удаления'))
            return

        if dry_run:
            self.stdout.write(self.style.WARNING(f'[DRY RUN] Будет удалено {count} пользователей:'))
            for user in users_to_delete[:20]:  # Показываем не более 20
                self.stdout.write(f'  - {user.email} (создан: {user.created_at.strftime("%Y-%m-%d %H:%M")})')
            if count > 20:
                self.stdout.write(f'  ... и ещё {count - 20} пользователей')
            return

        # Фактическое удаление
        deleted_count, _ = users_to_delete.delete()

        self.stdout.write(
            self.style.SUCCESS(
                f'✅ Удалено {deleted_count} неподтверждённых пользователей с истёкшим сроком верификации')
        )

        # Логируем в system log (если есть логгер)
        logger.info(f'Cleanup unverified users: deleted {deleted_count} users')