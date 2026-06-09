"""
Команда для заполнения базы данных реальными данными
Запуск: python manage.py populate_real_data
"""

import random
import uuid
from datetime import datetime, timedelta, time
from decimal import Decimal
from collections import defaultdict
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from faker import Faker

from ticket.models import (
    User, Movie, Hall, Screening, Seat, Ticket, TicketGroup, TicketStatus,
    Payment
)

fake = Faker('ru_RU')

try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False
    def tqdm(iterable, desc=""):
        return iterable


class Command(BaseCommand):
    help = 'Заполнение БД реальными данными'

    def add_arguments(self, parser):
        parser.add_argument('--users', type=int, default=10, help='Количество пользователей')
        parser.add_argument('--clear', action='store_true', help='Очистить старые данные')
        parser.add_argument('--no-payments', action='store_true', help='Не создавать платежи')

    def handle(self, *args, **options):
        self.users_count = options['users']
        self.clear_existing = options['clear']
        self.create_payments = not options['no_payments']

        # Константы
        self.WORK_START = 8  # 8:00
        self.WORK_END = time(0, 30)  # 00:30
        self.MIN_BREAK = 10
        self.MAX_BREAK = 60
        self.MIN_SCREENINGS_PER_MOVIE = 20
        self.MIN_DAYS_PER_MOVIE = 3
        self.MAX_SCREENINGS_PER_DAY_PER_MOVIE = 8
        self.MIN_SCREENINGS_PER_DAY_PER_MOVIE = 3
        self.MOVIES_PER_RENTAL_MIN = 8
        self.MOVIES_PER_RENTAL_MAX = 15
        self.RENTAL_DAYS = 7
        self.MAX_OCCUPANCY_PERCENT = 50
        self.REPEAT_PURCHASE_CHANCE = 0.05

        self.stats = {
            'users_created': 0,
            'screenings_created': 0,
            'tickets_created': 0,
            'groups_created': 0,
            'payments_created': 0,
            'errors': 0
        }

        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(self.style.SUCCESS('🎭 ЗАПОЛНЕНИЕ БАЗЫ ДАННЫХ РЕАЛЬНЫМИ ДАННЫМИ'))
        self.stdout.write(self.style.SUCCESS('=' * 70))

        if not self.check_prerequisites():
            return

        if self.clear_existing:
            self.clear_old_data()

        users = self.create_users()
        screenings = self.create_screenings()

        if not screenings:
            self.stdout.write(self.style.ERROR("❌ Не удалось создать ни одного сеанса!"))
            return

        tickets, groups = self.create_tickets_and_groups(screenings, users)

        if self.create_payments:
            self.create_fake_payments(groups)

        self.print_stats()

    def check_prerequisites(self):
        """Проверка наличия необходимых данных"""
        if Movie.objects.count() == 0:
            self.stdout.write(self.style.ERROR("❌ Нет фильмов. Запустите: python manage.py full_import"))
            return False

        if Hall.objects.count() == 0:
            self.stdout.write(self.style.ERROR("❌ Нет залов. Запустите: python manage.py big_populate_db --interactive"))
            return False

        try:
            self.active_status = TicketStatus.objects.get(code='active')
            self.used_status = TicketStatus.objects.get(code='used')
        except TicketStatus.DoesNotExist:
            self.stdout.write(self.style.ERROR("❌ Нет статусов 'active'/'used'"))
            return False

        self.movies = list(Movie.objects.all())
        self.halls = list(Hall.objects.all())
        self.stdout.write(f"✅ Фильмов: {len(self.movies)}, залов: {len(self.halls)}")
        return True

    def clear_old_data(self):
        """Очистка существующих данных"""
        self.stdout.write("Очистка старых данных...")
        with transaction.atomic():
            Payment.objects.all().delete()
            Ticket.objects.all().delete()
            TicketGroup.objects.all().delete()
            Screening.objects.all().delete()
        self.stdout.write(self.style.SUCCESS("✅ Очистка завершена"))

    def create_users(self):
        """Создание пользователей"""
        users = []
        password = 'mix9070mix'

        for i in tqdm(range(self.users_count), desc="  Создание пользователей", disable=not HAS_TQDM):
            first_name = fake.first_name()
            last_name = fake.last_name()
            email = f"user_{i+1}_{uuid.uuid4().hex[:8]}@example.com"
            phone = f"+7{random.randint(900, 999)}{random.randint(1000000, 9999999)}"

            while User.objects.filter(email=email).exists():
                email = f"user_{i+1}_{uuid.uuid4().hex[:8]}@example.com"
            while User.objects.filter(number=phone).exists():
                phone = f"+7{random.randint(900, 999)}{random.randint(1000000, 9999999)}"

            user = User.objects.create_user(
                email=email, password=password,
                name=first_name, surname=last_name, number=phone,
                is_email_verified=True
            )
            users.append(user)
            self.stats['users_created'] += 1

        self.stdout.write(self.style.SUCCESS(f"  ✅ Создано {len(users)} пользователей (пароль: {password})"))
        return users

    def create_rentals(self):
        """Создание прокатов с равномерным распределением фильмов"""
        movies_copy = self.movies.copy()
        random.shuffle(movies_copy)

        rentals = []
        idx = 0

        while idx < len(movies_copy):
            count = random.randint(self.MOVIES_PER_RENTAL_MIN, self.MOVIES_PER_RENTAL_MAX)
            if idx + count > len(movies_copy):
                count = len(movies_copy) - idx

            rental_movies = movies_copy[idx:idx+count]
            rentals.append({
                'movies': rental_movies,
            })
            idx += count

        return rentals

    def get_movie_daily_distribution(self, movie):
        """Получить распределение сеансов фильма по дням (3-7 дней, сумма 20)"""
        days = random.randint(self.MIN_DAYS_PER_MOVIE, self.RENTAL_DAYS)

        min_per_day = self.MIN_SCREENINGS_PER_DAY_PER_MOVIE
        max_per_day = self.MAX_SCREENINGS_PER_DAY_PER_MOVIE

        # Корректируем максимум для длинных фильмов
        if movie.duration > 150:
            max_per_day = 4
        elif movie.duration > 120:
            max_per_day = 5
        elif movie.duration > 90:
            max_per_day = 6

        # Простое равномерное распределение
        base = self.MIN_SCREENINGS_PER_MOVIE // days
        remainder = self.MIN_SCREENINGS_PER_MOVIE % days
        distribution = [base + (1 if i < remainder else 0) for i in range(days)]

        # Корректируем, если какой-то день превышает максимум
        for i in range(len(distribution)):
            if distribution[i] > max_per_day:
                extra = distribution[i] - max_per_day
                distribution[i] = max_per_day
                # Добавляем лишние сеансы в другие дни
                for j in range(len(distribution)):
                    if j != i and distribution[j] < max_per_day:
                        add = min(extra, max_per_day - distribution[j])
                        distribution[j] += add
                        extra -= add
                        if extra == 0:
                            break

        return distribution

    def create_screenings(self):
        """Создание сеансов с правилом половины фильма (ГЛОБАЛЬНОЕ)"""
        rentals = self.create_rentals()

        total_rentals = len(rentals)
        total_days = total_rentals * self.RENTAL_DAYS

        self.stdout.write(f"  📊 Всего прокатов: {total_rentals}, дней: {total_days}")

        all_screenings = []
        start_date = timezone.now().date() + timedelta(days=1)

        for rental_idx, rental in enumerate(rentals):
            rental_start = start_date + timedelta(days=rental_idx * self.RENTAL_DAYS)

            self.stdout.write(f"\n  📅 Прокат {rental_idx + 1}: {rental_start} - {rental_start + timedelta(days=self.RENTAL_DAYS - 1)}")
            self.stdout.write(f"     Фильмов: {len(rental['movies'])}")

            # Для каждого фильма получаем распределение по дням
            movie_distribution = {}
            for movie in rental['movies']:
                distribution = self.get_movie_daily_distribution(movie)
                movie_distribution[movie.id] = distribution
                self.stdout.write(f"     📋 {movie.title[:30]}: {distribution} сеансов по дням")

            # Планируем сеансы по дням проката
            for day_offset in range(self.RENTAL_DAYS):
                current_date = rental_start + timedelta(days=day_offset)

                # Собираем фильмы на этот день
                today_movies = []
                for movie in rental['movies']:
                    dist = movie_distribution.get(movie.id, [])
                    if day_offset < len(dist):
                        for _ in range(dist[day_offset]):
                            today_movies.append(movie)

                if not today_movies:
                    continue

                random.shuffle(today_movies)

                # ===== ГЛОБАЛЬНОЕ отслеживание сеансов за день (по всем залам) =====
                global_today_screenings = []  # Список всех сеансов за сегодня во всех залах

                # Распределяем по залам
                for hall in self.halls:
                    day_screenings = self.create_daily_schedule_for_hall(
                        hall, current_date, today_movies.copy(), global_today_screenings
                    )

                    for screening_data in day_screenings:
                        try:
                            screening = Screening.objects.create(
                                movie=screening_data['movie'],
                                hall=hall,
                                start_time=screening_data['start_time']
                            )
                            all_screenings.append(screening)
                            self.stats['screenings_created'] += 1

                            # Добавляем в глобальный список
                            global_today_screenings.append({
                                'movie': screening_data['movie'],
                                'start_time': screening_data['start_time'],
                                'hall_id': hall.id
                            })
                        except Exception as e:
                            self.stats['errors'] += 1

        self.stdout.write(self.style.SUCCESS(f"\n  ✅ Создано сеансов: {len(all_screenings)}"))
        return all_screenings

    def create_daily_schedule_for_hall(self, hall, date, all_movies, global_today_screenings):
        """
        Создать расписание на день для одного зала.
        global_today_screenings — список всех сеансов за сегодня во ВСЕХ залах (для проверки правила половины)
        """
        end_of_day = datetime.combine(date + timedelta(days=1), self.WORK_END)
        end_of_day = timezone.make_aware(end_of_day)

        result = []
        current_time = datetime.combine(date, time(self.WORK_START, 0))
        current_time = timezone.make_aware(current_time)

        # Отслеживаем, какие фильмы уже были в этом зале сегодня
        movies_played_in_hall_today = set()

        remaining_movies = all_movies.copy()

        while current_time < end_of_day and remaining_movies:
            found = False

            for i, movie in enumerate(remaining_movies):
                # Правило 1: В этом же зале не было этого фильма сегодня
                if movie.id in movies_played_in_hall_today:
                    continue

                # Правило 2: Проверка по другим залам (через global_today_screenings)
                can_start = True
                for other in global_today_screenings:
                    if other['movie'].id == movie.id and other['hall_id'] != hall.id:
                        half_duration = movie.duration / 2
                        time_since_start = (current_time - other['start_time']).total_seconds() / 60
                        # Если сеанс идёт и прошло меньше половины - запрещаем
                        if 0 <= time_since_start < half_duration:
                            can_start = False
                            break

                if not can_start:
                    continue

                # Рассчитываем время окончания
                break_minutes = random.randint(self.MIN_BREAK, self.MAX_BREAK)
                end_time = current_time + timedelta(minutes=movie.duration + break_minutes)

                if end_time <= end_of_day:
                    result.append({
                        'movie': movie,
                        'start_time': current_time
                    })
                    movies_played_in_hall_today.add(movie.id)
                    current_time = end_time
                    remaining_movies.pop(i)
                    found = True
                    break

            if not found:
                # Ни один фильм не влезает, завершаем день
                break

        return result

    def create_tickets_and_groups(self, screenings, users):
        """Создание билетов с распределением по дням"""
        all_tickets = []
        all_groups = []

        # Группируем сеансы по дням
        screenings_by_date = defaultdict(list)
        for screening in screenings:
            date_key = screening.start_time.date()
            screenings_by_date[date_key].append(screening)

        dates = sorted(screenings_by_date.keys())

        # Получаем все места
        all_seats = list(Seat.objects.all())
        seats_by_hall = defaultdict(list)
        for seat in all_seats:
            seats_by_hall[seat.hall_id].append(seat)

        # Создаём покупки на каждый день
        with tqdm(total=len(screenings), desc="  Создание билетов", disable=not HAS_TQDM) as pbar:
            for date in dates:
                day_screenings = screenings_by_date[date]

                for screening in day_screenings:
                    try:
                        hall_seats = seats_by_hall.get(screening.hall_id, [])
                        if not hall_seats:
                            pbar.update(1)
                            continue

                        total_seats = len(hall_seats)
                        max_tickets = int(total_seats * self.MAX_OCCUPANCY_PERCENT / 100)

                        if max_tickets < 2:
                            pbar.update(1)
                            continue

                        num_tickets = random.randint(2, max_tickets)
                        available_seats = hall_seats.copy()
                        random.shuffle(available_seats)
                        selected_seats = available_seats[:num_tickets]

                        # Распределяем билеты между пользователями
                        num_users = random.randint(1, min(len(users), num_tickets))
                        selected_users = random.sample(users, num_users)

                        temp_seats = selected_seats.copy()
                        remaining = num_tickets

                        for user in selected_users:
                            if remaining <= 0 or not temp_seats:
                                break

                            if random.random() < self.REPEAT_PURCHASE_CHANCE and remaining > 1:
                                num_groups = random.randint(1, 2)
                                for _ in range(num_groups):
                                    if remaining <= 0 or not temp_seats:
                                        break
                                    seats_count = min(random.randint(1, 3), remaining, len(temp_seats))
                                    if seats_count > 0:
                                        user_seats = temp_seats[:seats_count]
                                        temp_seats = temp_seats[seats_count:]
                                        remaining -= seats_count

                                        self.create_ticket_group_and_tickets(
                                            user, screening, user_seats, date, all_groups, all_tickets
                                        )
                            else:
                                seats_count = min(random.randint(1, 4), remaining, len(temp_seats))
                                if seats_count > 0:
                                    user_seats = temp_seats[:seats_count]
                                    temp_seats = temp_seats[seats_count:]
                                    remaining -= seats_count

                                    self.create_ticket_group_and_tickets(
                                        user, screening, user_seats, date, all_groups, all_tickets
                                    )

                        pbar.update(1)

                    except Exception as e:
                        self.stats['errors'] += 1
                        pbar.update(1)

        # Обновляем статусы для прошедших сеансов
        self.update_past_ticket_statuses()

        self.stdout.write(self.style.SUCCESS(f"  ✅ Групп: {len(all_groups)}, билетов: {len(all_tickets)}"))
        return all_tickets, all_groups

    def create_ticket_group_and_tickets(self, user, screening, seats, date, all_groups, all_tickets):
        """Создание одной группы билетов"""
        total_amount = Decimal(str(screening.ticket_price)) * len(seats)

        max_offset = max(0, (date - timezone.now().date()).days)
        if max_offset > 0:
            purchase_offset = random.randint(0, max_offset)
        else:
            purchase_offset = 0
        purchase_date = timezone.now() + timedelta(days=purchase_offset)

        ticket_group = TicketGroup.objects.create(
            group_uuid=uuid.uuid4(),
            user=user,
            screening=screening,
            purchase_date=purchase_date,
            total_amount=total_amount,
            tickets_count=len(seats),
            payment_status='paid'
        )
        all_groups.append(ticket_group)
        self.stats['groups_created'] += 1

        for seat in seats:
            ticket = Ticket.objects.create(
                user=user,
                screening=screening,
                seat=seat,
                price=screening.ticket_price,
                status=self.active_status,
                ticket_group=ticket_group
            )
            all_tickets.append(ticket)
            self.stats['tickets_created'] += 1

    def update_past_ticket_statuses(self):
        """Обновление статусов для прошедших сеансов"""
        now = timezone.now()
        past_tickets = Ticket.objects.filter(
            screening__start_time__lt=now,
            status=self.active_status
        )

        count = past_tickets.update(status=self.used_status)
        if count > 0:
            self.stdout.write(f"  🔄 Обновлено статусов 'used': {count}")

    def create_fake_payments(self, groups):
        """Создание фейковых платежей"""
        for group in tqdm(groups, desc="  Создание платежей", disable=not HAS_TQDM):
            try:
                Payment.objects.create(
                    ticket_group=group,
                    payment_id=f"fake_{uuid.uuid4().hex[:16]}",
                    idempotence_key=uuid.uuid4().hex,
                    status='succeeded',
                    amount=group.total_amount,
                    currency='RUB',
                    payment_method=random.choice(['bank_card', 'yoo_money']),
                    expires_at=timezone.now() + timedelta(minutes=30)
                )
                self.stats['payments_created'] += 1
            except Exception:
                self.stats['errors'] += 1

    def print_stats(self):
        self.stdout.write(self.style.SUCCESS('\n' + '=' * 70))
        self.stdout.write(self.style.SUCCESS('📊 ИТОГОВАЯ СТАТИСТИКА'))
        self.stdout.write('=' * 70)
        self.stdout.write(f"   👥 Пользователей: {self.stats['users_created']}")
        self.stdout.write(f"   🎬 Сеансов: {self.stats['screenings_created']}")
        self.stdout.write(f"   📦 Групп билетов: {self.stats['groups_created']}")
        self.stdout.write(f"   🎫 Билетов: {self.stats['tickets_created']}")
        self.stdout.write(f"   💳 Платежей: {self.stats['payments_created']}")
        if self.stats['errors'] > 0:
            self.stdout.write(self.style.WARNING(f"   ⚠️ Ошибок: {self.stats['errors']}"))
        self.stdout.write(self.style.SUCCESS('=' * 70))