from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from ticket.models import Movie, Screening, Hall, Genre, AgeRating, Director, Actor, HallType, Country


class Command(BaseCommand):
    help = 'Создает группу Manager и настраивает права доступа'

    def handle(self, *args, **options):
        # Создаем группу менеджеров
        manager_group, created = Group.objects.get_or_create(name='Manager')

        if created:
            self.stdout.write(self.style.SUCCESS('Группа Manager создана'))
        else:
            self.stdout.write(self.style.WARNING('Группа Manager уже существует'))

        # Очищаем существующие права
        manager_group.permissions.clear()

        # Модели, к которым нужен доступ
        models = [Movie, Screening, Hall, Genre, AgeRating, Director, Actor, HallType, Country]

        permissions_added = 0

        for model in models:
            content_type = ContentType.objects.get_for_model(model)

            # Получаем разрешения для CRUD операций
            perms = Permission.objects.filter(
                content_type=content_type,
                codename__in=[
                    f'add_{model._meta.model_name}',
                    f'change_{model._meta.model_name}',
                    f'delete_{model._meta.model_name}',
                    f'view_{model._meta.model_name}',
                ]
            )

            for perm in perms:
                manager_group.permissions.add(perm)
                permissions_added += 1
                self.stdout.write(f'  + {perm.codename}')

        self.stdout.write(self.style.SUCCESS(f'\n✅ Добавлено прав: {permissions_added}'))

        # Выводим информацию о группе
        self.stdout.write(f'\nГруппа "Manager" настроена успешно!')
        self.stdout.write(f'Теперь вы можете назначать пользователей в эту группу в админ-панели.')