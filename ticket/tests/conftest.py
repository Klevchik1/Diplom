"""
Pytest конфигурация и общие фикстуры для всех тестов
"""
import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal

from ticket.models import (
    User, Hall, HallType, Screening, Movie, AgeRating,
    Seat, TicketStatus, TicketGroup, Ticket, Genre, Country,
    Director, Actor
)

# ВАЖНО: Все фикстуры в этом файле будут использовать БД
pytestmark = pytest.mark.django_db

User = get_user_model()


@pytest.fixture
def test_user():
    """Обычный пользователь для тестов"""
    user = User.objects.create_user(
        email='test@example.com',
        password='testpass123',
        name='Тест',
        surname='Тестовый',
        number='+79991234567',
        is_email_verified=True
    )
    return user


@pytest.fixture
def unverified_user():
    """Неподтверждённый пользователь"""
    user = User.objects.create_user(
        email='unverified@example.com',
        password='testpass123',
        name='Не',
        surname='Подтверждённый',
        number='+79991112233',
        is_email_verified=False
    )
    user.generate_email_verification_code()
    return user


@pytest.fixture
def manager_user():
    """Пользователь с правами менеджера (is_staff=True)"""
    from django.contrib.auth.models import Group
    user = User.objects.create_user(
        email='manager@example.com',
        password='managerpass123',
        name='Менеджер',
        surname='Тестовый',
        number='+79998887766',
        is_email_verified=True,
        is_staff=True
    )
    manager_group, _ = Group.objects.get_or_create(name='Manager')
    user.groups.add(manager_group)
    return user


@pytest.fixture
def admin_user():
    """Администратор (суперпользователь)"""
    user = User.objects.create_superuser(
        email='admin@example.com',
        password='adminpass123',
        name='Админ',
        surname='Тестовый',
        number='+79995554433'
    )
    return user


@pytest.fixture
def hall_type():
    """Тип зала"""
    return HallType.objects.create(
        name='Стандарт',
        base_price=Decimal('300.00'),
        price_coefficient=Decimal('1.0'),
        description='Стандартный зал'
    )


@pytest.fixture
def hall(hall_type):
    """Зал 5×8 мест"""
    hall = Hall.objects.create(
        name='Тестовый зал',
        rows=5,
        seats_per_row=8,
        hall_type=hall_type,
        description='Зал для тестирования'
    )
    return hall


@pytest.fixture
def age_rating():
    """Возрастной рейтинг"""
    return AgeRating.objects.create(name='12+')


@pytest.fixture
def genre():
    """Жанр"""
    return Genre.objects.create(name='Боевик', description='Жанр для тестов')


@pytest.fixture
def country():
    """Страна"""
    return Country.objects.create(name='Россия', code='RU')


@pytest.fixture
def director():
    """Режиссёр"""
    return Director.objects.create(
        name='Тест',
        surname='Режиссёр',
        biography='Тестовый режиссёр'
    )


@pytest.fixture
def actor():
    """Актёр"""
    return Actor.objects.create(
        name='Тест',
        surname='Актёр',
        biography='Тестовый актёр'
    )


@pytest.fixture
def movie(age_rating, genre, country, director, actor):
    """Тестовый фильм"""
    movie = Movie.objects.create(
        title='Тестовый фильм',
        short_description='Короткое описание тестового фильма',
        description='Полное описание тестового фильма для проверки функциональности',
        duration=120,
        release_year=2024,
        age_rating=age_rating
    )
    movie.genres.add(genre)
    movie.countries.add(country)
    movie.directors.add(director)
    movie.actors.add(actor)
    return movie


@pytest.fixture
def screening(movie, hall):
    """Тестовый сеанс (начинается через 2 часа)"""
    now = timezone.now()
    start_time = now + timedelta(hours=2)
    duration_timedelta = timedelta(minutes=movie.duration)
    end_time = start_time + duration_timedelta + timedelta(minutes=10)

    screening = Screening.objects.create(
        movie=movie,
        hall=hall,
        start_time=start_time,
        end_time=end_time,
        ticket_price=Decimal('350.00')
    )
    return screening


@pytest.fixture
def screening_soon(movie, hall):
    """Сеанс, который начнётся через 15 минут"""
    now = timezone.now()
    start_time = now + timedelta(minutes=15)
    duration_timedelta = timedelta(minutes=movie.duration)
    end_time = start_time + duration_timedelta + timedelta(minutes=10)

    screening = Screening.objects.create(
        movie=movie,
        hall=hall,
        start_time=start_time,
        end_time=end_time,
        ticket_price=Decimal('350.00')
    )
    return screening


@pytest.fixture
def screening_past(movie, hall):
    """Прошедший сеанс"""
    now = timezone.now()
    start_time = now - timedelta(hours=2)
    duration_timedelta = timedelta(minutes=movie.duration)
    end_time = start_time + duration_timedelta + timedelta(minutes=10)

    screening = Screening.objects.create(
        movie=movie,
        hall=hall,
        start_time=start_time,
        end_time=end_time,
        ticket_price=Decimal('350.00')
    )
    return screening


@pytest.fixture
def seat(hall):
    """Конкретное место в зале (ряд 1, место 1)"""
    # Сначала создаём статусы, если их нет
    TicketStatus.objects.get_or_create(code='active', defaults={'name': 'Активный', 'can_be_refunded': True})
    TicketStatus.objects.get_or_create(code='refunded', defaults={'name': 'Возвращён', 'can_be_refunded': False})

    return Seat.objects.get(hall=hall, row=1, number=1)


@pytest.fixture
def active_ticket_status():
    """Статус 'active' для билета"""
    status, _ = TicketStatus.objects.get_or_create(
        code='active',
        defaults={'name': 'Активный', 'can_be_refunded': True, 'is_active': True}
    )
    return status


@pytest.fixture
def refunded_ticket_status():
    """Статус 'refunded' для билета"""
    status, _ = TicketStatus.objects.get_or_create(
        code='refunded',
        defaults={'name': 'Возвращён', 'can_be_refunded': False, 'is_active': True}
    )
    return status


@pytest.fixture
def ticket_group(test_user, screening, active_ticket_status):
    """Группа билетов (3 билета)"""
    group = TicketGroup.objects.create(
        user=test_user,
        screening=screening,
        purchase_date=timezone.now(),
        total_amount=Decimal('1050.00'),
        tickets_count=3,
        payment_status='paid'
    )

    for i in range(1, 4):
        seat = Seat.objects.get(hall=screening.hall, row=1, number=i)
        Ticket.objects.create(
            user=test_user,
            screening=screening,
            seat=seat,
            price=Decimal('350.00'),
            status=active_ticket_status,
            ticket_group=group
        )

    return group


@pytest.fixture
def single_ticket(test_user, screening, seat, active_ticket_status):
    """Один билет (без группы)"""
    return Ticket.objects.create(
        user=test_user,
        screening=screening,
        seat=seat,
        price=Decimal('350.00'),
        status=active_ticket_status
    )