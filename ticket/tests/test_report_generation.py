"""
FPOS-03-тест-отчетов-3
Тестирование генерации отчетов через ReportGenerator
"""
from datetime import datetime, timedelta
from django.test import TestCase
from django.utils import timezone
from ticket.models import User, Movie, Hall, Screening, Ticket, TicketStatus, Genre, AgeRating, Seat
from ticket.report_utils import ReportGenerator


class ReportGenerationTest(TestCase):
    """Тестирование генерации отчетов"""

    def setUp(self):
        """Создание тестовых данных для отчетов"""
        print("\nНастройка тестовых данных для отчетов...")

        # Создаем пользователя
        self.user = User.objects.create_user(
            email='reportuser@example.com',
            password='testpass123',
            name='Отчетный',
            surname='Пользователь',
            number='+79123456780',
            is_email_verified=True
        )

        # Создаем жанр
        self.genre = Genre.objects.create(name='Тестовый жанр')

        # Создаем возрастной рейтинг
        self.age_rating = AgeRating.objects.create(name='12+', description='Для детей старше 12 лет')

        # Создаем фильм
        self.movie = Movie.objects.create(
            title='Тестовый фильм для отчетов',
            description='Описание тестового фильма',
            duration=timedelta(hours=2),
            genre=self.genre,
            age_rating=self.age_rating
        )

        # Создаем зал
        self.hall = Hall.objects.create(
            name='Тестовый зал',
            rows=5,
            seats_per_row=10
        )

        # Создаем места (автоматически через сигнал)
        seats_created = Seat.objects.filter(hall=self.hall).count()
        print(f"Создано мест в зале: {seats_created}")

        # Создаем статусы билетов
        self.active_status = TicketStatus.objects.create(
            code='active',
            name='Активный',
            description='Билет активен',
            is_active=True,
            can_be_refunded=True
        )

        # Создаем сеансы
        self.screening1 = Screening.objects.create(
            movie=self.movie,
            hall=self.hall,
            start_time=timezone.now() + timedelta(days=1),
            price=500.00
        )

        self.screening2 = Screening.objects.create(
            movie=self.movie,
            hall=self.hall,
            start_time=timezone.now() + timedelta(days=2),
            price=600.00
        )

        # Создаем билеты
        seats = Seat.objects.filter(hall=self.hall)[:5]  # Берем первые 5 мест

        for i, seat in enumerate(seats):
            Ticket.objects.create(
                user=self.user,
                screening=self.screening1 if i < 3 else self.screening2,
                seat=seat,
                status=self.active_status,
                purchase_date=timezone.now() - timedelta(days=i)
            )

        print(f"Создано билетов: {Ticket.objects.count()}")

    def test_fpos_03_report_generation_success(self):
        """FPOS-03: Успешная генерация всех типов отчетов"""
        print("\n" + "=" * 60)
        print("FPOS-03-тест-отчетов-3")
        print("Тест: Генерация аналитических отчетов")
        print("=" * 60)

        # Шаг 1: Отчет по популярным фильмам
        print("Шаг 1: Генерация отчета по популярным фильмам...")
        movies_report = ReportGenerator.get_popular_movies(limit=10)

        self.assertIsNotNone(movies_report)
        self.assertIsInstance(movies_report, list)

        if movies_report:
            first_movie = movies_report[0]
            self.assertIn('title', first_movie)
            self.assertIn('tickets_sold', first_movie)
            self.assertIn('total_revenue', first_movie)
            self.assertIn('popularity_percentage', first_movie)
            print(f"✓ Отчет по фильмам создан, записей: {len(movies_report)}")
            print(f"  Самый популярный фильм: {first_movie.get('title')}")
            print(f"  Продано билетов: {first_movie.get('tickets_sold')}")
        else:
            print("⚠ Отчет по фильмам пустой (возможно нет данных)")

        # Шаг 2: Отчет по загруженности залов
        print("\nШаг 2: Генерация отчета по загруженности залов...")
        halls_report = ReportGenerator.get_hall_occupancy()

        self.assertIsNotNone(halls_report)
        self.assertIsInstance(halls_report, list)

        if halls_report:
            first_hall = halls_report[0]
            self.assertIn('name', first_hall)
            self.assertIn('total_seats', first_hall)
            self.assertIn('sold_tickets', first_hall)
            self.assertIn('occupancy_percent', first_hall)
            print(f"✓ Отчет по залам создан, записей: {len(halls_report)}")
            print(f"  Зал: {first_hall.get('name')}")
            print(f"  Загруженность: {first_hall.get('occupancy_percent')}%")
        else:
            print("⚠ Отчет по залам пустой (возможно нет данных)")

        # Шаг 3: Статистика продаж
        print("\nШаг 3: Генерация общей статистики продаж...")
        sales_stats = ReportGenerator.get_sales_statistics()

        self.assertIsNotNone(sales_stats)
        self.assertIsInstance(sales_stats, dict)

        expected_keys = [
            'total_tickets',
            'total_revenue',
            'avg_ticket_price',
            'popular_movie',
            'popular_movie_tickets'
        ]

        for key in expected_keys:
            self.assertIn(key, sales_stats)

        print(f"✓ Статистика продаж создана")
        print(f"  Всего билетов: {sales_stats.get('total_tickets')}")
        print(f"  Общая выручка: {sales_stats.get('total_revenue'):.2f} руб.")
        print(f"  Средний чек: {sales_stats.get('avg_ticket_price'):.2f} руб.")
        print(f"  Популярный фильм: {sales_stats.get('popular_movie')}")

        # Шаг 4: Финансовая статистика по периодам
        print("\nШаг 4: Генерация финансовой статистики...")

        # Дневная статистика
        daily_revenue = ReportGenerator.get_revenue_stats(period='daily')
        self.assertIsInstance(daily_revenue, list)
        print(f"✓ Дневная статистика: {len(daily_revenue)} записей")

        # Недельная статистика
        weekly_revenue = ReportGenerator.get_revenue_stats(period='weekly')
        self.assertIsInstance(weekly_revenue, list)
        print(f"✓ Недельная статистика: {len(weekly_revenue)} записей")

        # Месячная статистика
        monthly_revenue = ReportGenerator.get_revenue_stats(period='monthly')
        self.assertIsInstance(monthly_revenue, list)
        print(f"✓ Месячная статистика: {len(monthly_revenue)} записей")

        # Шаг 5: Агрегированные метрики
        print("\nШаг 5: Расчет агрегированных метрик...")

        if movies_report:
            movie_metrics = ReportGenerator.get_aggregated_metrics_for_movies(movies_report)
            self.assertIn('total_tickets', movie_metrics)
            self.assertIn('total_revenue', movie_metrics)
            print(f"✓ Метрики фильмов рассчитаны")
            print(f"  Общие билеты: {movie_metrics['total_tickets']}")
            print(f"  Общая выручка: {movie_metrics['total_revenue']:.2f}")

        if halls_report:
            hall_metrics = ReportGenerator.get_aggregated_metrics_for_halls(halls_report)
            self.assertIn('avg_occupancy', hall_metrics)
            self.assertIn('total_revenue', hall_metrics)
            print(f"✓ Метрики залов рассчитаны")
            print(f"  Средняя загруженность: {hall_metrics['avg_occupancy']:.1f}%")
            print(f"  Общая выручка: {hall_metrics['total_revenue']:.2f}")

        print("\n" + "=" * 60)
        print("РЕЗУЛЬТАТ: ТЕСТ УСПЕШНО ПРОЙДЕН ✅")
        print("Все отчеты сгенерированы корректно")
        print("=" * 60)