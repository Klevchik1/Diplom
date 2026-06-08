"""
Утилиты для генерации тестовых данных
"""
import random
from datetime import datetime, timedelta
from decimal import Decimal
from django.utils import timezone


def generate_random_movie_data():
    """Генерация случайных данных для фильма"""
    titles = [
        'Начало', 'Титаник', 'Аватар', 'Матрица', 'Гладиатор',
        'Тёмный рыцарь', 'Криминальное чтиво', 'Форрест Гамп',
        'Зелёная миля', 'Бойцовский клуб', 'Интерстеллар'
    ]

    return {
        'title': random.choice(titles) + f" {random.randint(2020, 2025)}",
        'short_description': 'Короткое описание фильма для тестирования',
        'description': 'Полное описание фильма, содержащее детальный сюжет и информацию о производстве.',
        'duration': random.randint(90, 180),
        'release_year': random.randint(1990, 2025),
    }


def generate_random_user_data():
    """Генерация случайных данных для пользователя"""
    first_names = ['Иван', 'Петр', 'Сергей', 'Алексей', 'Дмитрий', 'Анна', 'Мария', 'Елена']
    last_names = ['Иванов', 'Петров', 'Сидоров', 'Смирнов', 'Кузнецов']

    random_id = random.randint(1, 100000)

    return {
        'email': f"test_user_{random_id}@example.com",
        'name': random.choice(first_names),
        'surname': random.choice(last_names),
        'number': f"+7{random.randint(900, 999)}{random.randint(1000000, 9999999)}",
        'password': 'TestPass123!'
    }


def generate_random_screening_time(movie_duration=120):
    """Генерация случайного времени для сеанса"""
    now = timezone.now()

    # Сеанс в течение следующих 7 дней, в рабочее время (8:00 - 22:00)
    days_offset = random.randint(0, 7)
    hour = random.randint(10, 21)

    start_time = now.replace(
        day=now.day + days_offset,
        hour=hour,
        minute=0,
        second=0,
        microsecond=0
    )

    if start_time < now:
        start_time += timedelta(days=1)

    return start_time


def get_date_filter_data():
    """Генерация данных для фильтрации по дате"""
    now = timezone.now()
    dates = []

    for i in range(5):
        date = now + timedelta(days=i)
        dates.append({
            'date': date.strftime('%Y-%m-%d'),
            'label': ['Сегодня', 'Завтра', 'Послезавтра', 'Через 3 дня', 'Через 4 дня'][i]
        })

    return dates


def get_genre_filter_data():
    """Список жанров для фильтрации"""
    return [
        {'id': 1, 'name': 'Боевик'},
        {'id': 2, 'name': 'Комедия'},
        {'id': 3, 'name': 'Драма'},
        {'id': 4, 'name': 'Фантастика'},
        {'id': 5, 'name': 'Триллер'},
        {'id': 6, 'name': 'Ужасы'},
        {'id': 7, 'name': 'Мелодрама'},
        {'id': 8, 'name': 'Приключения'},
    ]