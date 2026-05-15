from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from ticket.models import Ticket, TicketStatus, Screening
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Автоматически переводит активные билеты в статус "used" через 30 минут после окончания сеанса'

    def handle(self, *args, **options):
        now = timezone.now()
        cutoff_time = now - timedelta(minutes=30)

        try:
            used_status = TicketStatus.objects.get(code='used')
            active_status = TicketStatus.objects.get(code='active')
        except TicketStatus.DoesNotExist as e:
            self.stdout.write(self.style.ERROR(f'Не найден статус: {e}'))
            return

        # Находим все сеансы, которые закончились более 30 минут назад
        completed_screenings = Screening.objects.filter(
            end_time__lte=cutoff_time
        )

        updated_count = 0
        for screening in completed_screenings:
            # Находим активные билеты на этот сеанс
            tickets = Ticket.objects.filter(
                screening=screening,
                status=active_status
            )

            count = tickets.count()
            if count > 0:
                tickets.update(
                    status=used_status,
                    updated_at=now
                )
                updated_count += count
                self.stdout.write(
                    f'Сеанс "{screening.movie.title}" ({screening.start_time.strftime("%d.%m.%Y %H:%M")}): '
                    f'{count} билетов переведено в статус "used"'
                )

        if updated_count > 0:
            self.stdout.write(
                self.style.SUCCESS(f'Всего обновлено: {updated_count} билетов')
            )
        else:
            self.stdout.write('Нет билетов для обновления')