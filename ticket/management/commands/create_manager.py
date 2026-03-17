from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group
from ticket.models import User
from django.utils import timezone


class Command(BaseCommand):
    help = 'Создает пользователя-менеджера с email manager@example.com и паролем manager'

    def add_arguments(self, parser):
        parser.add_argument(
            '--email',
            type=str,
            default='manager@example.com',
            help='Email для менеджера (по умолчанию: manager@example.com)'
        )
        parser.add_argument(
            '--password',
            type=str,
            default='manager',
            help='Пароль для менеджера (по умолчанию: manager)'
        )
        parser.add_argument(
            '--name',
            type=str,
            default='Иван',
            help='Имя менеджера (по умолчанию: Иван)'
        )
        parser.add_argument(
            '--surname',
            type=str,
            default='Менеджеров',
            help='Фамилия менеджера (по умолчанию: Менеджеров)'
        )
        parser.add_argument(
            '--phone',
            type=str,
            default='+79991112233',
            help='Телефон менеджера (по умолчанию: +79991112233)'
        )

    def handle(self, *args, **options):
        email = options['email']
        password = options['password']
        name = options['name']
        surname = options['surname']
        phone = options['phone']

        self.stdout.write('🚀 Создание менеджера...')

        # Создаем или получаем группу Manager
        manager_group, group_created = Group.objects.get_or_create(name='Manager')
        if group_created:
            self.stdout.write(self.style.SUCCESS('  ✅ Создана группа Manager'))
        else:
            self.stdout.write(self.style.SUCCESS('  ✅ Группа Manager уже существует'))

        # Проверяем, существует ли уже пользователь с таким email
        if User.objects.filter(email=email).exists():
            self.stdout.write(self.style.WARNING(f'⚠️ Пользователь с email {email} уже существует'))

            user = User.objects.get(email=email)

            # Проверяем, в группе ли он
            if manager_group in user.groups.all():
                self.stdout.write(self.style.SUCCESS(f'  ✅ Пользователь уже в группе Manager'))
            else:
                user.groups.add(manager_group)
                self.stdout.write(self.style.SUCCESS(f'  ✅ Пользователь добавлен в группу Manager'))

            self.stdout.write(self.style.SUCCESS('\n📊 Информация о пользователе:'))
            self.stdout.write(f'   Email: {user.email}')
            self.stdout.write(f'   Имя: {user.name} {user.surname}')
            self.stdout.write(f'   Телефон: {user.number}')
            self.stdout.write(f'   Админ: {"Да" if user.is_staff else "Нет"}')
            self.stdout.write(f'   Суперпользователь: {"Да" if user.is_superuser else "Нет"}')
            self.stdout.write(f'   Email подтвержден: {"Да" if user.is_email_verified else "Нет"}')

            return

        # Создаем нового менеджера
        user = User.objects.create_user(
            email=email,
            password=password,
            name=name,
            surname=surname,
            number=phone,
            is_staff=False,  # Не админ
            is_superuser=False,  # Не суперпользователь
            is_email_verified=True  # Сразу верифицируем
        )

        # Добавляем в группу Manager
        user.groups.add(manager_group)

        self.stdout.write(self.style.SUCCESS('\n✅ Менеджер успешно создан!'))
        self.stdout.write(self.style.SUCCESS('📊 Данные для входа:'))
        self.stdout.write(f'   Email: {email}')
        self.stdout.write(f'   Пароль: {password}')
        self.stdout.write(f'   Имя: {name} {surname}')
        self.stdout.write(f'   Телефон: {phone}')
        self.stdout.write('\n🔐 Путь для входа в панель менеджера:')
        self.stdout.write('   http://127.0.0.1:8000/manager/')

        # Выводим информацию о группе
        self.stdout.write('\n👥 Информация о группе Manager:')
        self.stdout.write(f'   Название группы: {manager_group.name}')
        self.stdout.write(f'   ID группы: {manager_group.id}')
        self.stdout.write(f'   Количество пользователей в группе: {manager_group.user_set.count()}')