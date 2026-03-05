from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta, datetime, time
import random
from faker import Faker
import os
from django.core.files import File
from django.conf import settings
from django.db.models import Q
from rest_framework.exceptions import ValidationError

from ticket.models import (
    Hall, Movie, Screening, Seat, User, Genre, AgeRating,
    TicketStatus, Country, HallType, Director, Actor,
    MovieDirector, MovieActor, ActionType, ModuleType,
    Ticket, TicketGroup, PendingRegistration, PasswordResetRequest,
    EmailChangeRequest, BackupManager, OperationLog
)

fake = Faker('ru_RU')


class Command(BaseCommand):
    help = 'Заполняет базу данных расширенными тестовыми данными кинотеатра'

    def handle(self, *args, **options):
        self.clear_old_data()
        self.create_admin()
        self.create_countries()
        self.create_action_and_module_types()
        self.create_ticket_statuses()
        self.create_hall_types()
        genres = self.create_genres()
        age_ratings = self.create_age_ratings()
        halls = self.create_halls()
        directors, actors = self.create_directors_and_actors()
        movies = self.create_movies(genres, age_ratings, directors, actors)
        self.create_screenings(halls, movies)

        self.stdout.write(self.style.SUCCESS('✅ База успешно заполнена тестовыми данными!'))

    def clear_old_data(self):
        """Очистка старых данных (кроме суперпользователей)"""
        self.stdout.write('Очистка старых данных...')

        # Удаляем в правильном порядке из-за внешних ключей
        self.stdout.write('  Удаление билетов...')
        Ticket.objects.all().delete()

        self.stdout.write('  Удаление групп билетов...')
        TicketGroup.objects.all().delete()

        self.stdout.write('  Удаление сеансов...')
        Screening.objects.all().delete()

        self.stdout.write('  Удаление мест...')
        Seat.objects.all().delete()

        self.stdout.write('  Удаление фильмов...')
        Movie.objects.all().delete()

        self.stdout.write('  Удаление режиссёров и актёров...')
        MovieDirector.objects.all().delete()
        MovieActor.objects.all().delete()
        Director.objects.all().delete()
        Actor.objects.all().delete()

        self.stdout.write('  Удаление возрастных рейтингов...')
        AgeRating.objects.all().delete()

        self.stdout.write('  Удаление залов...')
        Hall.objects.all().delete()

        self.stdout.write('  Удаление типов залов...')
        HallType.objects.all().delete()

        self.stdout.write('  Удаление жанров...')
        Genre.objects.all().delete()

        self.stdout.write('  Удаление статусов билетов...')
        TicketStatus.objects.all().delete()

        self.stdout.write('  Удаление стран...')
        Country.objects.all().delete()

        self.stdout.write('  Удаление типов действий и модулей...')
        ActionType.objects.all().delete()
        ModuleType.objects.all().delete()

        # Удаляем временные регистрации и запросы
        PendingRegistration.objects.all().delete()
        PasswordResetRequest.objects.all().delete()
        EmailChangeRequest.objects.all().delete()
        BackupManager.objects.all().delete()
        OperationLog.objects.all().delete()

        self.stdout.write(self.style.SUCCESS('✅ Старые данные удалены'))

    def create_admin(self):
        """Создание администратора если его нет"""
        if not User.objects.filter(email='admin@example.com').exists():
            admin = User.objects.create_superuser(
                email='admin@example.com',
                password='admin',
                name='Администратор',
                surname='Системы',
                number='+79001234567'
            )
            self.stdout.write(self.style.SUCCESS(f'✅ Создан администратор: {admin.email}'))
        else:
            self.stdout.write(self.style.SUCCESS('✅ Администратор уже существует'))

    def create_countries(self):
        """Создание стран для режиссёров и актёров"""
        self.stdout.write('Создание стран...')

        countries_data = [
            {'name': 'Россия', 'code': 'RU'},
            {'name': 'США', 'code': 'US'},
            {'name': 'Великобритания', 'code': 'GB'},
            {'name': 'Франция', 'code': 'FR'},
            {'name': 'Германия', 'code': 'DE'},
            {'name': 'Италия', 'code': 'IT'},
            {'name': 'Испания', 'code': 'ES'},
            {'name': 'Канада', 'code': 'CA'},
            {'name': 'Австралия', 'code': 'AU'},
            {'name': 'Япония', 'code': 'JP'},
            {'name': 'Китай', 'code': 'CN'},
            {'name': 'Южная Корея', 'code': 'KR'},
        ]

        countries = {}
        for data in countries_data:
            country, created = Country.objects.get_or_create(
                code=data['code'],
                defaults={'name': data['name']}
            )
            countries[data['code']] = country
            if created:
                self.stdout.write(self.style.SUCCESS(f'  ✅ Создана страна: {country.name}'))

        return countries

    def create_action_and_module_types(self):
        """Создание типов действий и модулей для логирования"""
        self.stdout.write('Создание типов действий и модулей для логирования...')

        # Типы действий
        action_types = [
            {'code': 'CREATE', 'name': 'Создание', 'description': 'Создание объекта'},
            {'code': 'UPDATE', 'name': 'Обновление', 'description': 'Обновление объекта'},
            {'code': 'DELETE', 'name': 'Удаление', 'description': 'Удаление объекта'},
            {'code': 'VIEW', 'name': 'Просмотр', 'description': 'Просмотр объекта'},
            {'code': 'EXPORT', 'name': 'Экспорт', 'description': 'Экспорт данных'},
            {'code': 'LOGIN', 'name': 'Вход', 'description': 'Вход в систему'},
            {'code': 'LOGOUT', 'name': 'Выход', 'description': 'Выход из системы'},
            {'code': 'BACKUP', 'name': 'Бэкап', 'description': 'Создание бэкапа'},
            {'code': 'REPORT', 'name': 'Отчет', 'description': 'Генерация отчета'},
            {'code': 'OTHER', 'name': 'Другое', 'description': 'Другое действие'},
        ]

        for data in action_types:
            obj, created = ActionType.objects.get_or_create(
                code=data['code'],
                defaults={'name': data['name'], 'description': data['description']}
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'  ✅ Создан тип действия: {obj.name}'))

        # Типы модулей
        module_types = [
            {'code': 'USERS', 'name': 'Пользователи', 'description': 'Управление пользователями'},
            {'code': 'MOVIES', 'name': 'Фильмы', 'description': 'Управление фильмами'},
            {'code': 'HALLS', 'name': 'Залы', 'description': 'Управление залами'},
            {'code': 'SCREENINGS', 'name': 'Сеансы', 'description': 'Управление сеансами'},
            {'code': 'TICKETS', 'name': 'Билеты', 'description': 'Управление билетами'},
            {'code': 'REPORTS', 'name': 'Отчеты', 'description': 'Генерация отчетов'},
            {'code': 'BACKUPS', 'name': 'Бэкапы', 'description': 'Управление бэкапами'},
            {'code': 'SYSTEM', 'name': 'Система', 'description': 'Системные операции'},
            {'code': 'AUTH', 'name': 'Аутентификация', 'description': 'Вход и выход из системы'},
        ]

        for data in module_types:
            obj, created = ModuleType.objects.get_or_create(
                code=data['code'],
                defaults={'name': data['name'], 'description': data['description']}
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'  ✅ Создан тип модуля: {obj.name}'))

    def create_ticket_statuses(self):
        """Создание статусов билетов для системы возвратов"""
        self.stdout.write('Создание статусов билетов...')

        statuses = [
            {
                'code': 'active',
                'name': 'Активный',
                'description': 'Билет активен и действителен',
                'is_active': True,
                'can_be_refunded': True
            },
            {
                'code': 'refund_requested',
                'name': 'Запрошен возврат',
                'description': 'Пользователь запросил возврат билета',
                'is_active': True,
                'can_be_refunded': False
            },
            {
                'code': 'refunded',
                'name': 'Возвращен',
                'description': 'Билет возвращен, деньги возвращены',
                'is_active': True,
                'can_be_refunded': False
            },
            {
                'code': 'used',
                'name': 'Использован',
                'description': 'Билет использован на сеансе',
                'is_active': True,
                'can_be_refunded': False
            },
            {
                'code': 'cancelled',
                'name': 'Отменен',
                'description': 'Билет отменен (сеанс отменен)',
                'is_active': True,
                'can_be_refunded': False
            },
            {
                'code': 'expired',
                'name': 'Просрочен',
                'description': 'Срок действия билета истек',
                'is_active': True,
                'can_be_refunded': False
            }
        ]

        created_count = 0
        for status_data in statuses:
            obj, created = TicketStatus.objects.update_or_create(
                code=status_data['code'],
                defaults=status_data
            )
            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f'  ✅ Создан статус: {status_data["code"]} - {status_data["name"]}'))

        self.stdout.write(self.style.SUCCESS(f'✅ Статусы билетов готовы! Создано: {created_count}, Всего: {TicketStatus.objects.count()}'))

    def create_hall_types(self):
        """Создание типов залов с коэффициентами цен"""
        self.stdout.write('Создание типов залов...')

        hall_types_data = [
            {
                'name': 'Стандарт',
                'description': 'Классический кинозал с комфортными креслами',
                'price_coefficient': 1.0,
                'base_price': 350
            },
            {
                'name': 'VIP',
                'description': 'Премиальный зал с кожаными креслами-реклайнерами',
                'price_coefficient': 1.8,
                'base_price': 600
            },
            {
                'name': 'Love Hall',
                'description': 'Романтический зал с двухместными диванами',
                'price_coefficient': 1.5,
                'base_price': 500
            },
            {
                'name': 'Комфорт',
                'description': 'Зал с мягкими бескаркасными креслами',
                'price_coefficient': 1.2,
                'base_price': 400
            },
            {
                'name': 'IMAX',
                'description': 'Зал с гигантским экраном и объемным звуком',
                'price_coefficient': 2.0,
                'base_price': 450
            }
        ]

        hall_types = {}
        for data in hall_types_data:
            hall_type, created = HallType.objects.get_or_create(
                name=data['name'],
                defaults={
                    'description': data['description'],
                    'price_coefficient': data['price_coefficient'],
                    'base_price': data['base_price']
                }
            )
            hall_types[data['name']] = hall_type
            if created:
                self.stdout.write(self.style.SUCCESS(f'  ✅ Создан тип зала: {hall_type.name}'))

        return hall_types

    def create_halls(self):
        """Создание 5 залов разных типов с описаниями"""
        self.stdout.write('Создание залов...')

        hall_types = {ht.name: ht for ht in HallType.objects.all()}

        halls_data = [
            {
                'name': 'Стандарт',
                'hall_type': 'Стандарт',
                'rows': 10,
                'seats_per_row': 15,
                'description': 'Классический кинозал с комфортными тканевыми креслами, системой звука Dolby Digital и качественным проектором. Идеальный выбор для просмотра фильмов любого жанра.'
            },
            {
                'name': 'VIP Зал',
                'hall_type': 'VIP',
                'rows': 6,
                'seats_per_row': 8,
                'description': 'Премиальный зал с кожаными креслами-реклайнерами, увеличенным расстоянием между рядами, индивидуальными столиками для напитков и закусок. Обслуживание официантом.'
            },
            {
                'name': 'Love Hall',
                'hall_type': 'Love Hall',
                'rows': 5,
                'seats_per_row': 6,
                'description': 'Романтический зал с двухместными диванами вместо кресел. 1 билет = диван на двух человек. Идеально для пар: уютные пледы, приглушенный свет и интимная атмосфера.'
            },
            {
                'name': 'Комфорт',
                'hall_type': 'Комфорт',
                'rows': 7,
                'seats_per_row': 10,
                'description': 'Зал с мягкими бескаркасными креслами-подушками вместо обычных кресел. Расслабляющая атмосфера, идеально для комфортного просмотра длинных фильмов.'
            },
            {
                'name': 'IMAX',
                'hall_type': 'IMAX',
                'rows': 12,
                'seats_per_row': 18,
                'description': 'Легендарный формат IMAX с гигантским изогнутым экраном, лазерной проекцией и 12-канальной системой звука. Погружение в фильм на 100%.'
            }
        ]

        halls = []
        for data in halls_data:
            hall = Hall.objects.create(
                name=data['name'],
                hall_type=hall_types[data['hall_type']],
                rows=data['rows'],
                seats_per_row=data['seats_per_row'],
                description=data['description']
            )
            halls.append(hall)
            self.stdout.write(self.style.SUCCESS(f'  ✅ Создан зал: {hall.name}'))

        return halls

    def create_genres(self):
        """Создание основных жанров с уникальными именами"""
        self.stdout.write('Создание жанров...')

        genres_list = [
            'Фантастика', 'Комедия', 'Боевик', 'Драма', 'Приключения',
            'Биография', 'Мультфильм', 'Ужасы', 'Триллер', 'Мелодрама',
            'Фэнтези', 'Детектив', 'Вестерн', 'Исторический', 'Документальный'
        ]

        created_genres = {}
        for genre_name in genres_list:
            genre_name = genre_name.strip().title()
            genre, created = Genre.objects.get_or_create(name=genre_name)
            created_genres[genre_name] = genre
            if created:
                self.stdout.write(self.style.SUCCESS(f'  ✅ Создан жанр: {genre_name}'))

        return created_genres

    def create_age_ratings(self):
        """Создание возрастных рейтингов"""
        self.stdout.write('Создание возрастных рейтингов...')

        age_ratings_data = ['0+', '6+', '12+', '16+', '18+']

        created_age_ratings = {}
        for rating_name in age_ratings_data:
            rating, created = AgeRating.objects.get_or_create(name=rating_name)
            created_age_ratings[rating_name] = rating
            if created:
                self.stdout.write(self.style.SUCCESS(f'  ✅ Создан возрастной рейтинг: {rating.name}'))

        return created_age_ratings

    def create_directors_and_actors(self):
        """Создание режиссёров и актёров"""
        self.stdout.write('Создание режиссёров и актёров...')

        countries = {c.code: c for c in Country.objects.all()}

        # Режиссёры
        directors_data = [
            {'name': 'Джеймс', 'surname': 'Кэмерон', 'country': 'US'},
            {'name': 'Кристофер', 'surname': 'Нолан', 'country': 'GB'},
            {'name': 'Квентин', 'surname': 'Тарантино', 'country': 'US'},
            {'name': 'Стивен', 'surname': 'Спилберг', 'country': 'US'},
            {'name': 'Мартин', 'surname': 'Скорсезе', 'country': 'US'},
            {'name': 'Ридли', 'surname': 'Скотт', 'country': 'GB'},
            {'name': 'Питер', 'surname': 'Джексон', 'country': 'NZ'},
            {'name': 'Дэвид', 'surname': 'Финчер', 'country': 'US'},
            {'name': 'Уэс', 'surname': 'Андерсон', 'country': 'US'},
            {'name': 'Дени', 'surname': 'Вильнёв', 'country': 'CA'},
            {'name': 'Андрей', 'surname': 'Тарковский', 'country': 'RU'},
            {'name': 'Никита', 'surname': 'Михалков', 'country': 'RU'},
        ]

        directors = []
        for data in directors_data:
            country = countries.get(data['country'])
            director, created = Director.objects.get_or_create(
                name=data['name'],
                surname=data['surname'],
                defaults={
                    'country': country,
                    'biography': fake.text(max_nb_chars=200)
                }
            )
            directors.append(director)
            if created:
                self.stdout.write(self.style.SUCCESS(f'  ✅ Создан режиссёр: {director.name} {director.surname}'))

        # Актёры
        actors_data = [
            {'name': 'Леонардо', 'surname': 'ДиКаприо', 'country': 'US'},
            {'name': 'Том', 'surname': 'Хэнкс', 'country': 'US'},
            {'name': 'Морган', 'surname': 'Фриман', 'country': 'US'},
            {'name': 'Роберт', 'surname': 'Дауни-младший', 'country': 'US'},
            {'name': 'Скарлетт', 'surname': 'Йоханссон', 'country': 'US'},
            {'name': 'Дженнифер', 'surname': 'Лоуренс', 'country': 'US'},
            {'name': 'Кристиан', 'surname': 'Бейл', 'country': 'GB'},
            {'name': 'Кейт', 'surname': 'Уинслет', 'country': 'GB'},
            {'name': 'Мэтт', 'surname': 'Дэймон', 'country': 'US'},
            {'name': 'Брэд', 'surname': 'Питт', 'country': 'US'},
            {'name': 'Анджелина', 'surname': 'Джоли', 'country': 'US'},
            {'name': 'Джонни', 'surname': 'Депп', 'country': 'US'},
            {'name': 'Константин', 'surname': 'Хабенский', 'country': 'RU'},
            {'name': 'Владимир', 'surname': 'Машков', 'country': 'RU'},
            {'name': 'Евгений', 'surname': 'Миронов', 'country': 'RU'},
            {'name': 'Чулпан', 'surname': 'Хаматова', 'country': 'RU'},
        ]

        actors = []
        for data in actors_data:
            country = countries.get(data['country'])
            actor, created = Actor.objects.get_or_create(
                name=data['name'],
                surname=data['surname'],
                defaults={
                    'country': country,
                    'biography': fake.text(max_nb_chars=200)
                }
            )
            actors.append(actor)
            if created:
                self.stdout.write(self.style.SUCCESS(f'  ✅ Создан актёр: {actor.name} {actor.surname}'))

        return directors, actors

    def create_movies(self, genres, age_ratings, directors, actors):
        """Создание фильмов с реальными описаниями и возрастными рейтингами"""
        self.stdout.write('Создание фильмов...')

        posters_dir = os.path.join(settings.BASE_DIR, 'ticket', 'management', 'commands', 'posters')

        movies_data = [
            {
                'title': 'Аватар: Путь воды',
                'duration': 192,
                'genre': 'Фантастика',
                'age_rating': '12+',
                'poster': 'avatar.jpg',
                'short_description': 'Джейк Салли и Нейтири создали семью, но им вновь угрожают люди с Земли.',
                'description': 'Прошло более десяти лет после событий первого фильма "Аватар". Джейк Салли и Нейтири создали семью и делают всё возможное, чтобы оставаться вместе. Однако им вновь угрожает опасность с Земли. Когда древние метки снова появляются, Джейк должен вести войну против людей. В поисках убежища семья Салли отправляется в регионы Пандоры, населённые другими кланами На\'ви. Живя среди нового племени, они учатся жить и выживать в водной среде, одновременно готовясь к неизбежной битве, которая определит будущее Пандоры.'
            },
            {
                'title': 'Один дома',
                'duration': 103,
                'genre': 'Комедия',
                'age_rating': '6+',
                'poster': 'home_alone.jpg',
                'short_description': '8-летний Кевин случайно остается один дома и защищает свой дом от грабителей.',
                'description': 'Семья Маккаллистеров в спешке собирается в рождественское путешествие в Париж. В суматохе они забывают дома своего восьмилетнего сына Кевина. Поначалу мальчик рад возможности пожить самостоятельно: он ест сладости, смотрит запрещённые фильмы и устраивает беспорядок. Но вскоре он обнаруживает, что его дом стал мишенью для двух незадачливых грабителей — Гарри и Марва. Используя всю свою смекалку, Кевин превращает дом в крепость с хитроумными ловушками, чтобы дать отпор непрошеным гостям в канун Рождества.'
            },
            {
                'title': 'Интерстеллар',
                'duration': 169,
                'genre': 'Фантастика',
                'age_rating': '12+',
                'poster': 'interstellar.jpg',
                'short_description': 'Команда исследователей совершает путешествие через червоточину в поисках нового дома для человечества.',
                'description': 'В недалёком будущем из-за глобального потепления и пыльных бурь человечество переживает продольственный кризис. Бывший пилот НАСА Купер ведёт фермерское хозяйство вместе со своей семьёй в американской глубинке. Когда его дочь Мёрф утверждает, что в её комнате живёт призрак, Купер понимает, что аномалии гравитации — это послание от пришельцев, которые дают человечеству шанс на спасение. Он присоединяется к секретной экспедиции НАСА, целью которой является поиск нового дома для человечества за пределами Солнечной системы через червоточину.'
            },
            {
                'title': 'Оппенгеймер',
                'duration': 180,
                'genre': 'Биография',
                'age_rating': '16+',
                'poster': 'oppenheimer.jpg',
                'short_description': 'История жизни американского физика Роберта Оппенгеймера, создателя атомной бомбы.',
                'description': 'Фильм рассказывает о жизни американского физика-теоретика Роберта Оппенгеймера, который во время Второй мировой войны руководил Манхэттенским проектом — программой по созданию атомной бомбы. Картина охватывает разные периоды его жизни: учёбу в Европе, работу в Калифорнийском университете в Беркли, руководство Лос-Аламосской лабораторией и последующие слушания по допуску к секретной информации в 1954 году. Фильм исследует моральные дилеммы, с которыми столкнулся учёный, создавая оружие массового уничтожения.'
            },
            {
                'title': 'Барби',
                'duration': 114,
                'genre': 'Комедия',
                'age_rating': '12+',
                'poster': 'barbie.jpg',
                'short_description': 'Кукла Барби живет в идеальном мире, но обнаруживает, что её мир не так прекрасен.',
                'description': 'Кукла Барби живёт в идеальном мире Барбиленда, где каждый день — самый лучший. Однако однажды она начинает замечать странные изменения: её утренний тост подгорает, а во время вечеринки у бассейна она внезапно задумывается о смерти. Чтобы исправить ситуацию, она отправляется в реальный мир вместе с Кеном. В ходе путешествия они сталкиваются с радостями и трудностями жизни среди людей, узнают ценность настоящей дружбы и самопознания, а также понимают, что совершенство — это не всегда то, к чему нужно стремиться.'
            },
            {
                'title': 'Джон Уик 4',
                'duration': 169,
                'genre': 'Боевик',
                'age_rating': '18+',
                'poster': 'john_wick.jpg',
                'short_description': 'Джон Уик обнаруживает путь к победе над Правлением Кланов.',
                'description': 'Джон Уик продолжает свой путь к свободе, сталкиваясь с новыми врагами и могущественными альянсами. На этот раз ему предстоит сразиться с Правлением Кланов, которое сосредоточило против него все свои силы. Чтобы победить, Уик должен найти способ уничтожить организацию изнутри. Его ждут эпические сражения в Париже, Берлине, Нью-Йорке и Осаке, где он столкнётся с самыми опасными противниками в своей жизни.'
            },
            {
                'title': 'Стражи Галактики 3',
                'duration': 150,
                'genre': 'Фантастика',
                'age_rating': '16+',
                'poster': 'guardians.jpg',
                'short_description': 'Питер Квилл все еще оплачивает потерю Гаморы и должен сплотить свою команду.',
                'description': 'Питер Квилл всё ещё оплакивает потерю Гаморы и должен сплотить свою команду, чтобы защитить Вселенную и защитить одного из своих. В этой заключительной главе Стражи Галактики отправляются в опасное путешествие, чтобы раскрыть тайны происхождения Ракеты. По пути они сталкиваются с новыми и старыми врагами, которые угрожают уничтожить их и всю галактику. Команде предстоит пройти через самые трудные испытания, чтобы остаться вместе.'
            },
            {
                'title': 'Человек-паук: Паутина вселенных',
                'duration': 140,
                'genre': 'Мультфильм',
                'age_rating': '6+',
                'poster': 'spiderman.jpg',
                'short_description': 'Майлз Моралес переносится через Мультивселенную и встречает команду Людей-пауков.',
                'description': 'Майлз Моралес возвращается в следующей главе оскароносной саги "Человек-паук: Через вселенные". Во время путешествия по Мультивселенной он встречает команду Людей-пауков, которые должны защитить само её существование. Когда герои сталкиваются с новым врагом, Майлзу приходится переосмыслить всё, что значит быть героем, чтобы спасти близких из разных измерений. Фильм исследует идею о том, что любой человек может надеть маску и стать героем.'
            },
            {
                'title': 'Миссия невыполнима 7',
                'duration': 163,
                'genre': 'Боевик',
                'age_rating': '12+',
                'poster': 'mission_impossible.jpg',
                'short_description': 'Итан Хант и его команда МВФ должны отследить новое ужасающее оружие.',
                'description': 'Итан Хант и его команда МВФ должны отследить новое ужасающее оружие, которое угрожает всему человечеству, если оно окажется в неправильных руках. С контролем над будущим и судьбой мира в своих руках, и с темными силами из прошлого Итана, начинается смертельная гонка по всему миру. Столкнувшись с загадочным и всемогущим противником, Итан вынужден считать, что ничто не имеет значения больше, чем его миссия — даже жизни тех, кто ему дорог.'
            },
            {
                'title': 'Индиана Джонс и реликвия судьбы',
                'duration': 154,
                'genre': 'Приключения',
                'age_rating': '12+',
                'poster': 'indiana_jones.jpg',
                'short_description': 'Археолог Индиана Джонс отправляется в новое опасное приключение.',
                'description': 'Археолог Индиана Джонс отправляется в новое опасное приключение, чтобы найти древнюю реликвию, обладающую невероятной силой. Действие фильма происходит в 1969 году, на фоне космической гонки. Джонс понимает, что его давно потерянный племянник работает на злодейскую организацию, которая надеется использовать артефакт для изменения хода истории. Чтобы сорвать их планы, Индиана должен объединиться со своей крестницей и отправиться в путешествие, которое приведёт его в самые отдалённые уголки мира.'
            },
            {
                'title': 'Дюна',
                'duration': 155,
                'genre': 'Фантастика',
                'age_rating': '12+',
                'poster': 'dune.jpg',
                'short_description': 'Пол Атрейдес вместе с семьей отправляется на опасную планету Арракис.',
                'description': 'Пол Атрейдес вместе с семьёй отправляется на опасную планету Арракис, где сталкивается с врагами и начинает путь к своей судьбе. На этой пустынной планете находится самый ценный ресурс во вселенной — пряность, которая продлевает жизнь и делает возможными межзвёздные путешествия. Когда его семья попадает в ловушку зловещего заговора, Пол должен отправиться в самое сердце Арракиса, чтобы встретиться с фрименами и исполнить древнее пророчество, которое изменит судьбу галактики.'
            },
            {
                'title': 'Трансформеры: Эпоха зверей',
                'duration': 127,
                'genre': 'Фантастика',
                'age_rating': '12+',
                'poster': 'transformers.jpg',
                'short_description': 'Автоботы и Максималы объединяются с человечеством против террористических Предаконов.',
                'description': 'Автоботы и Максималы объединяются с человечеством против террористических Предаконов в битве за Землю. Действие фильма происходит в 1994 году, когда гигантские роботы скрываются среди людей. Когда новая угроза emerges из космоса, Автоботы должны объединиться с племенем Максималов, чтобы защитить планету от уничтожения. В этой эпической битве решается судьба не только Земли, но и всей галактики.'
            }
        ]

        movies = []
        for data in movies_data:
            # Получаем объект Genre
            genre_name = data['genre'].strip().title()
            genre_obj = genres.get(genre_name)
            if not genre_obj:
                genre_obj, _ = Genre.objects.get_or_create(name=genre_name)
                genres[genre_name] = genre_obj

            # Получаем объект AgeRating
            age_rating_name = data['age_rating']
            age_rating_obj = age_ratings.get(age_rating_name)
            if not age_rating_obj:
                age_rating_obj, _ = AgeRating.objects.get_or_create(name=age_rating_name)
                age_ratings[age_rating_name] = age_rating_obj

            # Создаем фильм
            movie = Movie.objects.create(
                title=data['title'],
                short_description=data['short_description'],
                description=data['description'],
                duration=data['duration'],
                release_year=random.randint(2020, 2025),
                genre=genre_obj,
                age_rating=age_rating_obj
            )

            # Добавляем постер если он существует
            poster_path = os.path.join(posters_dir, data['poster'])
            if os.path.exists(poster_path):
                with open(poster_path, 'rb') as f:
                    movie.poster.save(data['poster'], File(f))
                    movie.save()
                self.stdout.write(self.style.SUCCESS(f'  ✅ Создан фильм: {movie.title} ({age_rating_name}, с постером)'))
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f'  ⚠️ Создан фильм: {movie.title} ({age_rating_name}, постер не найден: {data["poster"]})'))

            # Добавляем режиссёров (случайным образом)
            movie_directors = random.sample(directors, k=random.randint(1, 2))
            for director in movie_directors:
                MovieDirector.objects.create(movie=movie, director=director)

            # Добавляем актёров (случайным образом)
            movie_actors = random.sample(actors, k=random.randint(3, 5))
            for actor in movie_actors:
                MovieActor.objects.create(movie=movie, actor=actor)

            movies.append(movie)

        self.stdout.write(self.style.SUCCESS(f'✅ Всего создано фильмов: {len(movies)}'))
        return movies

    def get_time_multiplier(self, screening_time):
        """Возвращает множитель цены в зависимости от времени сеанса"""
        from decimal import Decimal

        hour = screening_time.hour
        if 8 <= hour < 12:
            return Decimal('0.7')
        elif 12 <= hour < 16:
            return Decimal('0.9')
        elif 16 <= hour < 20:
            return Decimal('1.2')
        else:
            return Decimal('1.4')

    def calculate_ticket_price(self, hall, start_time):
        """Рассчитывает цену билета на основе типа зала и времени"""
        from decimal import Decimal

        hall_type = hall.hall_type
        base_price = hall_type.base_price  # Decimal
        coefficient = hall_type.price_coefficient  # Decimal
        time_multiplier = Decimal(str(self.get_time_multiplier(start_time)))  # Преобразуем float в Decimal

        # Все операнды теперь Decimal
        result = base_price * coefficient * time_multiplier
        return int(result)  # Преобразуем в int для цены

    def is_time_slot_available(self, hall, start_time, duration):
        """Проверяет, свободен ли временной слот в зале"""
        end_time = start_time + timedelta(minutes=duration) + timedelta(minutes=20)

        # Проверяем, что сеанс заканчивается до 24:00
        local_end = timezone.localtime(end_time)
        if local_end.hour >= 24 or (local_end.hour == 0 and local_end.minute > 0) or local_end.hour < start_time.hour:
            return False

        conflicting_screenings = Screening.objects.filter(
            hall=hall
        ).filter(
            Q(start_time__lt=end_time, end_time__gt=start_time)
        )
        return not conflicting_screenings.exists()

    def create_screenings(self, halls, movies):
        """Создание сеансов на месяц вперед"""
        self.stdout.write('Создание сеансов...')

        now = timezone.localtime(timezone.now())
        # Убираем поздние сеансы, которые могут перейти за полночь
        screening_times = ['08:00', '10:30', '13:00', '15:30', '18:00', '20:00']
        created_count = 0
        screenings_per_movie = {movie.id: 0 for movie in movies}

        # Создаем сеансы на 30 дней вперед
        for day in range(30):
            current_date = now + timedelta(days=day)
            if day % 7 == 0:
                self.stdout.write(f'  Создание сеансов на {current_date.strftime("%d.%m.%Y")}...')

            for hall in halls:
                available_times = screening_times.copy()
                random.shuffle(available_times)

                # Берем до 3 сеансов в день на зал
                for time_str in available_times[:3]:
                    # Выбираем случайный фильм
                    movie = random.choice(movies)

                    screening_time = datetime.combine(
                        current_date.date(),
                        datetime.strptime(time_str, '%H:%M').time()
                    )
                    screening_time = timezone.make_aware(screening_time)

                    # Проверяем, что сеанс не в прошлом
                    if screening_time < now:
                        continue

                    # Проверяем, что сеанс закончится до полуночи
                    end_time = screening_time + timedelta(minutes=movie.duration) + timedelta(minutes=10)
                    if end_time.date() > current_date.date():
                        # Если сеанс переходит на следующий день, пропускаем
                        continue

                    # Проверяем доступность слота
                    if not self.is_time_slot_available(hall, screening_time, movie.duration):
                        continue

                    # Рассчитываем цену
                    ticket_price = self.calculate_ticket_price(hall, screening_time)

                    # Создаем сеанс
                    try:
                        duration_timedelta = timedelta(minutes=movie.duration)
                        end_time = screening_time + duration_timedelta + timedelta(minutes=10)

                        Screening.objects.create(
                            movie=movie,
                            hall=hall,
                            start_time=screening_time,
                            end_time=end_time,
                            ticket_price=ticket_price
                        )
                        created_count += 1
                        screenings_per_movie[movie.id] += 1
                    except ValidationError as e:
                        self.stdout.write(self.style.WARNING(f'    ⚠️ Пропущен сеанс: {e}'))
                        continue

        # Выводим статистику
        self.stdout.write(self.style.SUCCESS(f'✅ Всего создано {created_count} сеансов'))
        for movie in movies:
            count = screenings_per_movie.get(movie.id, 0)
            if count > 0:
                self.stdout.write(self.style.SUCCESS(f'  ✅ {movie.title}: {count} сеансов'))

    def add_arguments(self, parser):
        parser.add_argument(
            '--skip-movies',
            action='store_true',
            help='Пропустить создание фильмов',
        )
        parser.add_argument(
            '--skip-halls',
            action='store_true',
            help='Пропустить создание залов',
        )
        parser.add_argument(
            '--skip-screenings',
            action='store_true',
            help='Пропустить создание сеансов',
        )
        parser.add_argument(
            '--skip-statuses',
            action='store_true',
            help='Пропустить создание статусов билетов',
        )
        parser.add_argument(
            '--skip-countries',
            action='store_true',
            help='Пропустить создание стран',
        )
        parser.add_argument(
            '--skip-directors-actors',
            action='store_true',
            help='Пропустить создание режиссёров и актёров',
        )