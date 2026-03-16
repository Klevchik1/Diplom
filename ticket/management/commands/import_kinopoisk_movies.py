# ticket/management/commands/import_kinopoisk_movies.py

import requests
from django.core.management.base import BaseCommand
from django.conf import settings
from ticket.models import Movie, Genre, AgeRating, Director, Actor, Country
from datetime import datetime
import os
from django.core.files import File
from django.core.files.temp import NamedTemporaryFile
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Импорт фильмов из API Poiskkino.dev'

    def add_arguments(self, parser):
        parser.add_argument(
            '--pages',
            type=int,
            default=2,
            help='Количество страниц для импорта (по 50 фильмов на странице)'
        )
        parser.add_argument(
            '--year-start',
            type=int,
            default=2020,
            help='Начальный год для фильмов'
        )
        parser.add_argument(
            '--download-posters',
            action='store_true',
            help='Скачивать постеры фильмов'
        )

    def handle(self, *args, **options):
        # Проверяем наличие API-ключа
        api_key = getattr(settings, 'KINOPOISK_API_KEY', None)
        if not api_key:
            self.stderr.write(
                self.style.ERROR('ОШИБКА: KINOPOISK_API_KEY не найден в settings.py!')
            )
            self.stderr.write('Добавьте в .env строку: KINOPOISK_API_KEY=ваш_ключ')
            return

        self.stdout.write(self.style.SUCCESS(f'✅ API ключ загружен: {api_key[:5]}...'))
        self.stdout.write(self.style.WARNING('Начинаю импорт фильмов...'))

        pages = options['pages']
        year_start = options['year_start']
        download_posters = options['download_posters']

        # Базовый URL API
        base_url = "https://api.poiskkino.dev/v1.4"
        headers = {
            "X-API-KEY": api_key,
            "accept": "application/json"
        }

        total_imported = 0

        for page in range(1, pages + 1):
            self.stdout.write(f"\n📄 Импорт страницы {page} из {pages}...")

            # Параметры запроса для популярных фильмов
            params = {
                "page": page,
                "limit": 50,
                "sortField": "rating.kp",
                "sortType": "-1",  # по убыванию рейтинга
                "type": "movie",  # только фильмы (не сериалы)
                "year": f"{year_start}-2025",  # фильмы последних лет
                "selectFields": ["id", "name", "description", "shortDescription",
                                 "year", "movieLength", "poster", "genres",
                                 "ageRating", "countries", "persons"]
            }

            try:
                response = requests.get(
                    f"{base_url}/movie",
                    headers=headers,
                    params=params,
                    timeout=15
                )
                response.raise_for_status()
                data = response.json()

                movies = data.get('docs', [])
                if not movies:
                    self.stdout.write(self.style.WARNING('  Нет фильмов на этой странице'))
                    break

                self.stdout.write(f"  Найдено {len(movies)} фильмов")

                for movie_data in movies:
                    try:
                        result = self.import_movie(movie_data, download_posters)
                        if result:
                            total_imported += 1
                            self.stdout.write(self.style.SUCCESS(f'  ✅ {result}'))
                        else:
                            self.stdout.write(self.style.WARNING(f'  ⚠️ Пропущен: {movie_data.get("name", "Без названия")}'))
                    except Exception as e:
                        self.stderr.write(self.style.ERROR(f'  ❌ Ошибка при импорте: {e}'))

            except requests.exceptions.RequestException as e:
                self.stderr.write(self.style.ERROR(f'Ошибка запроса к API: {e}'))
                continue

        self.stdout.write(self.style.SUCCESS(f'\n✅ Импорт завершен! Импортировано фильмов: {total_imported}'))

    def import_movie(self, data, download_posters=False):
        """Импорт одного фильма в базу данных"""

        # Проверяем обязательные поля
        name = data.get('name')
        if not name:
            return None

        # Проверяем, есть ли уже такой фильм
        if Movie.objects.filter(title=name).exists():
            return f"{name} (уже есть в БД)"

        # Получаем или создаем жанр
        genre_name = "Неизвестно"
        if data.get('genres') and len(data['genres']) > 0:
            genre_name = data['genres'][0].get('name', 'Неизвестно')

        genre, _ = Genre.objects.get_or_create(
            name=genre_name,
            defaults={'description': f'Импортировано из API'}
        )

        # Получаем или создаем возрастной рейтинг
        age_rating_value = data.get('ageRating')
        if age_rating_value:
            # Приводим к формату как в БД (например, "16" -> "16+")
            age_str = f"{age_rating_value}+"
        else:
            age_str = "0+"  # По умолчанию

        age_rating, _ = AgeRating.objects.get_or_create(name=age_str)

        # Создаем фильм
        movie = Movie(
            title=name,
            short_description=data.get('shortDescription', '')[:200] or '',
            description=data.get('description', '') or 'Описание отсутствует',
            duration=data.get('movieLength', 90) or 90,  # если нет, ставим 90 минут
            release_year=data.get('year', 2024),
            genre=genre,
            age_rating=age_rating
        )

        # Если нужно скачать постер
        if download_posters and data.get('poster') and data['poster'].get('url'):
            poster_url = data['poster']['url']
            try:
                self.download_poster(movie, poster_url)
            except Exception as e:
                logger.error(f"Не удалось скачать постер для {name}: {e}")

        movie.save()

        # Импортируем страны
        if data.get('countries'):
            for country_data in data['countries']:
                country_name = country_data.get('name')
                if country_name:
                    country, _ = Country.objects.get_or_create(
                        name=country_name,
                        defaults={'code': country_name[:2].upper()}
                    )
                    # Здесь можно добавить связь фильма со страной,
                    # если у вас есть такая модель в проекте

        # Импортируем режиссеров и актеров
        if data.get('persons'):
            directors = []
            actors = []

            for person in data['persons']:
                profession = person.get('profession')
                person_name = person.get('name')

                if not person_name:
                    continue

                # Разделяем имя и фамилию (примерно)
                name_parts = person_name.split(' ', 1)
                first_name = name_parts[0]
                last_name = name_parts[1] if len(name_parts) > 1 else ''

                if profession == 'режиссеры' or profession == 'director':
                    director, _ = Director.objects.get_or_create(
                        name=first_name,
                        surname=last_name
                    )
                    directors.append(director)
                elif profession == 'актеры' or profession == 'actor':
                    actor, _ = Actor.objects.get_or_create(
                        name=first_name,
                        surname=last_name
                    )
                    actors.append(actor)

            # Сохраняем связи (если есть соответствующие through-модели)
            # Раскомментируйте, если у вас есть MovieDirector и MovieActor
            # movie.directors.set(directors)
            # movie.actors.set(actors)

        return f"{movie.title} ({movie.release_year})"

    def download_poster(self, movie, poster_url):
        """Скачивание постера для фильма"""
        import requests
        from django.core.files.base import ContentFile

        try:
            response = requests.get(poster_url, timeout=10)
            response.raise_for_status()

            # Определяем расширение файла
            ext = poster_url.split('.')[-1].split('?')[0]
            if ext not in ['jpg', 'jpeg', 'png', 'webp']:
                ext = 'jpg'

            filename = f"{movie.title.lower().replace(' ', '_')}.{ext}"
            movie.poster.save(filename, ContentFile(response.content), save=False)

        except Exception as e:
            logger.error(f"Ошибка скачивания постера: {e}")
            raise