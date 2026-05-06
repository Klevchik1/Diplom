from django.core.management.base import BaseCommand
from ticket.models import APIToken


class Command(BaseCommand):
    help = 'Инициализация API токенов'

    def add_arguments(self, parser):
        parser.add_argument('--token', type=str, help='API токен')
        parser.add_argument('--label', type=str, default='Основной', help='Метка токена')

    def handle(self, *args, **options):
        token = options['token']
        label = options['label']

        if not token:
            self.stdout.write(self.style.WARNING('Укажите токен через --token=...'))
            self.stdout.write('\nТекущие токены:')
            for t in APIToken.objects.all():
                self.stdout.write(f"  • {t.label}: {t.token[:10]}... ({t.requests_today}/{t.daily_limit})")
            return

        obj, created = APIToken.objects.get_or_create(
            token=token,
            defaults={'label': label, 'daily_limit': 200}
        )

        if created:
            self.stdout.write(self.style.SUCCESS(f'✅ Токен "{label}" добавлен'))
        else:
            self.stdout.write(self.style.WARNING(f'⚠️ Токен уже существует: {label}'))