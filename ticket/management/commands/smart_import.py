"""
Умный импорт с контролем лимитов API, ротацией токенов и сохранением прогресса.
Запуск: python manage.py smart_import --task-id=1
       python manage.py smart_import --type=movies --pages=3 --year-from=2024
"""

import time
import logging
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.core.files.base import ContentFile
import re
import random

from ticket.models import (
    Movie, Genre, AgeRating, Director, Actor, Country,
    MovieDirector, MovieActor, MovieGenre, Hall, Screening,
    APIToken, APIRequestLog, ImportTask, ImportCache
)
from ticket.tmdb_client import KinopoiskDevClient

logger = logging.getLogger(__name__)


class SmartImporter:
    """Умный импортёр с контролем лимитов"""

    def __init__(self, task=None, verbosity=1):
        self.task = task
        self.verbosity = verbosity
        self.stats = {
            'movies_new': 0, 'movies_updated': 0, 'movies_skipped': 0,
            'persons_created': 0, 'genres_created': 0, 'countries_created': 0,
            'posters_downloaded': 0, 'api_requests': 0, 'errors': 0
        }

        # Загружаем существующие данные
        self.existing_countries = {c.name.lower(): c for c in Country.objects.all()}
        self.existing_directors = {}
        self.existing_actors = {}
        self.existing_genres = {g.name.lower(): g for g in Genre.objects.all()}
        self.existing_movies = set(Movie.objects.values_list('title', flat=True))

        # Кэш персон
        self.person_cache = {}

        # Инициализируем клиент
        self.client = KinopoiskDevClient()

        # Список известных стран (сокращённый)
        self.known_countries = {
            'россия': 'RU', 'сша': 'US', 'великобритания': 'GB',
            'германия': 'DE', 'франция': 'FR', 'италия': 'IT',
            'испания': 'ES', 'япония': 'JP', 'китай': 'CN',
            'южная корея': 'KR', 'канада': 'CA', 'австралия': 'AU',
            'индия': 'IN', 'бразилия': 'BR', 'мексика': 'MX',
            'турция': 'TR', 'польша': 'PL', 'швеция': 'SE',
        }

        self.non_countries = {
            'москва', 'санкт-петербург', 'лос-анджелес', 'нью-йорк',
            'париж', 'лондон', 'берлин', 'токио', 'пекин', 'сеул',
            'казань', 'новосибирск', 'екатеринбург'
        }

    def log(self, message, level='info'):
        if self.verbosity >= 1:
            if level == 'success':
                print(f"✅ {message}")
            elif level == 'warning':
                print(f"⚠️ {message}")
            elif level == 'error':
                print(f"❌ {message}")
            else:
                print(f"  {message}")

    def get_or_create_country(self, country_name):
        """Создать страну с проверкой"""
        if not country_name or len(country_name) > 20:
            return None, False

        country_lower = country_name.lower().strip()

        if country_lower in self.existing_countries:
            return self.existing_countries[country_lower], False

        if re.search(r'[a-zA-Z]', country_name):
            return None, False

        for city in self.non_countries:
            if city in country_lower:
                return None, False

        for country_ru, code in self.known_countries.items():
            if country_ru in country_lower:
                country, created = Country.objects.get_or_create(
                    name=country_ru.capitalize(),
                    defaults={'code': code}
                )
                self.existing_countries[country_ru] = country
                if created:
                    self.stats['countries_created'] += 1
                return country, created

        return None, False

    def get_or_create_genre(self, genre_name):
        """Создать жанр"""
        if not genre_name:
            return None

        name_lower = genre_name.lower().strip()

        if name_lower in self.existing_genres:
            return self.existing_genres[name_lower]

        genre, created = Genre.objects.get_or_create(
            name=name_lower.capitalize(),
            defaults={'description': f'Импортировано из API'}
        )
        self.existing_genres[name_lower] = genre
        if created:
            self.stats['genres_created'] += 1
        return genre

    def import_person_basic(self, person_data, profession_type):
        """Импорт персоны без дополнительного запроса к API"""
        person_name = person_data.get('name', '')
        person_id = person_data.get('id')

        if not person_name:
            return None

        name_parts = person_name.split(' ', 1)
        first_name = name_parts[0][:20] if name_parts else ""
        last_name = name_parts[1][:20] if len(name_parts) > 1 else ""
        full_key = f"{first_name.lower()} {last_name.lower()}"

        if profession_type == 'director':
            if full_key in self.existing_directors:
                return self.existing_directors[full_key]

            director, created = Director.objects.get_or_create(
                name=first_name, surname=last_name,
                defaults={'biography': f'ID API: {person_id}'}
            )
            self.existing_directors[full_key] = director
            if created:
                self.stats['persons_created'] += 1
            return director
        else:
            if full_key in self.existing_actors:
                return self.existing_actors[full_key]

            actor, created = Actor.objects.get_or_create(
                name=first_name, surname=last_name,
                defaults={'biography': f'ID API: {person_id}'}
            )
            self.existing_actors[full_key] = actor
            if created:
                self.stats['persons_created'] += 1
            return actor

    def process_movie_basic(self, movie_data, import_posters=True, import_persons=True):
        """Обработка одного фильма (без доп. запросов к API)"""
        title = movie_data.get('name', '')
        movie_id = movie_data.get('id')

        if not title:
            return 'skipped'

        if len(title) > 50:
            title = title[:47] + "..."

        # Проверяем существование
        if self.task and self.task.skip_existing and title in self.existing_movies:
            self.stats['movies_skipped'] += 1
            return 'skipped'

        # Проверяем длительность
        duration = movie_data.get('movieLength', 0)
        if duration < 60:
            return 'skipped'

        # Находим или создаём фильм
        movie = Movie.objects.filter(title=title).first()
        is_new = movie is None

        if is_new:
            # Создаём фильм
            age_str = f"{movie_data.get('ageRating', 16)}+"
            age_rating, _ = AgeRating.objects.get_or_create(name=age_str)

            description = movie_data.get('description', '') or movie_data.get('shortDescription', 'Описание отсутствует')
            description = description[:997] + "..." if len(description) > 1000 else description

            short_desc = movie_data.get('shortDescription', '') or description[:197] + "..."
            short_desc = short_desc[:197] + "..." if len(short_desc) > 200 else short_desc

            movie = Movie.objects.create(
                title=title,
                short_description=short_desc,
                description=description,
                duration=duration,
                release_year=movie_data.get('year', datetime.now().year),
                age_rating=age_rating
            )
            self.stats['movies_new'] += 1
            self.existing_movies.add(title)
        else:
            self.stats['movies_updated'] += 1

        # Жанры
        if movie_data.get('genres'):
            current_genres = set(movie.genres.values_list('id', flat=True))
            for genre_data in movie_data['genres']:
                genre_name = genre_data.get('name', '')
                if genre_name:
                    genre = self.get_or_create_genre(genre_name)
                    if genre and genre.id not in current_genres:
                        MovieGenre.objects.get_or_create(movie=movie, genre=genre)

        # Персоны (базовая информация, без доп. запросов)
        if import_persons and movie_data.get('persons') and is_new:
            current_directors = set(movie.directors.values_list('id', flat=True))
            current_actors = set(movie.actors.values_list('id', flat=True))

            for person in movie_data['persons'][:20]:  # Максимум 20 персон
                profession = person.get('profession', '').lower()
                if profession in ['режиссеры', 'director', 'режиссер', 'режиссёр']:
                    person_obj = self.import_person_basic(person, 'director')
                    if person_obj and person_obj.id not in current_directors:
                        MovieDirector.objects.get_or_create(movie=movie, director=person_obj)
                elif profession in ['актеры', 'actor', 'актер', 'актёр']:
                    person_obj = self.import_person_basic(person, 'actor')
                    if person_obj and person_obj.id not in current_actors:
                        MovieActor.objects.get_or_create(movie=movie, actor=person_obj)

        # Постер
        if import_posters and is_new and not movie.poster:
            poster_url = None
            poster_data = movie_data.get('poster', {})
            if isinstance(poster_data, dict):
                poster_url = poster_data.get('url') or poster_data.get('previewUrl')

            if poster_url:
                try:
                    image_content = self.client.download_image(poster_url)
                    if image_content:
                        safe_title = re.sub(r'[^\w\s-]', '', title)[:50].strip()
                        movie.poster.save(f"{safe_title}.jpg", ContentFile(image_content), save=True)
                        self.stats['posters_downloaded'] += 1
                except Exception as e:
                    logger.error(f"Ошибка скачивания постера: {e}")

        return 'new' if is_new else 'updated'

    def run_import(self, pages=3, year_from=2020, year_to=2025, import_posters=True, import_persons=True):
        """Запуск импорта"""
        self.log(f"🎬 НАЧАЛО УМНОГО ИМПОРТА")
        self.log(f"📊 Страниц: {pages} × 50 фильмов")
        self.log(f"📅 Годы: {year_from}-{year_to}")
        self.log(f"🖼️ Постеры: {'да' if import_posters else 'нет'}")
        self.log(f"👥 Персоны: {'да' if import_persons else 'нет'}")

        # Проверяем доступные токены
        token_info = KinopoiskDevClient.get_total_available_tokens()
        self.log(f"🔑 Доступно токенов: {token_info['tokens_count']} ({token_info['total_remaining']} запросов осталось)")

        if token_info['total_remaining'] < 10:
            self.log("⚠️ Осталось мало запросов! Импорт может не выполниться полностью.", 'warning')

        max_requests = min(token_info['total_remaining'], pages * 3)  # ~3 запроса на страницу
        self.log(f"🎯 Планируемый максимум запросов: {max_requests}")

        for page in range(1, pages + 1):
            self.log(f"\n📄 Страница {page}/{pages}...")

            if token_info['total_remaining'] < 5:
                self.log("❌ Закончились запросы API. Остановка.", 'error')
                break

            result = self.client.get_movies_page(page=page, limit=50, year_from=year_from, year_to=year_to)
            self.stats['api_requests'] += 1

            if not result or 'docs' not in result:
                self.log(f"Ошибка получения страницы {page}", 'error')
                continue

            movies = result.get('docs', [])
            if not movies:
                self.log("Фильмов на странице нет, завершение.")
                break

            self.log(f"Получено {len(movies)} фильмов на странице")

            for i, movie_data in enumerate(movies):
                if i % 10 == 0 and i > 0:
                    self.log(f"  Прогресс: {i}/{len(movies)}")

                try:
                    result = self.process_movie_basic(movie_data, import_posters, import_persons)
                except Exception as e:
                    self.stats['errors'] += 1
                    logger.error(f"Ошибка обработки фильма: {e}")

                # Пауза между фильмами для снижения нагрузки
                time.sleep(0.1)

            # Пауза между страницами
            if page < pages:
                time.sleep(0.5)

        self.print_summary()

    def print_summary(self):
        self.log(f"\n{'='*50}")
        self.log(f"📊 ИТОГИ ИМПОРТА")
        self.log(f"{'='*50}")
        self.log(f"🎬 Фильмов: +{self.stats['movies_new']} новых, {self.stats['movies_updated']} обновлено, {self.stats['movies_skipped']} пропущено")
        self.log(f"👥 Персон создано: {self.stats['persons_created']}")
        self.log(f"🎭 Жанров создано: {self.stats['genres_created']}")
        self.log(f"🌍 Стран создано: {self.stats['countries_created']}")
        self.log(f"🖼️ Постеров: {self.stats['posters_downloaded']}")
        self.log(f"🔌 API запросов: {self.stats['api_requests']}")
        if self.stats['errors'] > 0:
            self.log(f"❌ Ошибок: {self.stats['errors']}", 'error')

        # Обновляем информацию о токенах
        token_info = KinopoiskDevClient.get_total_available_tokens()
        self.log(f"\n🔑 Осталось запросов: {token_info['total_remaining']}/{token_info['total_limit']}")
        self.log(f"{'='*50}")


class Command(BaseCommand):
    help = 'Умный импорт фильмов с контролем лимитов API'

    def add_arguments(self, parser):
        parser.add_argument('--type', type=str, default='movies', choices=['movies', 'genres', 'persons', 'full'],
                           help='Тип импорта')
        parser.add_argument('--pages', type=int, default=3, help='Количество страниц')
        parser.add_argument('--year-from', type=int, default=2024, help='Год от')
        parser.add_argument('--year-to', type=int, default=2025, help='Год до')
        parser.add_argument('--no-posters', action='store_true', help='Без постеров')
        parser.add_argument('--no-persons', action='store_true', help='Без персон')
        parser.add_argument('--task-id', type=int, help='ID задачи импорта')
        parser.add_argument('--token-info', action='store_true', help='Показать информацию о токенах')

    def handle(self, *args, **options):
        if options['token_info']:
            self.print_token_info()
            return

        importer = SmartImporter(verbosity=2)
        importer.run_import(
            pages=options['pages'],
            year_from=options['year_from'],
            year_to=options['year_to'],
            import_posters=not options['no_posters'],
            import_persons=not options['no_persons']
        )

    def print_token_info(self):
        info = KinopoiskDevClient.get_total_available_tokens()
        print(f"\n🔑 ИНФОРМАЦИЯ О ТОКЕНАХ API")
        print(f"{'='*50}")
        print(f"Всего токенов: {info['tokens_count']}")
        print(f"Осталось запросов: {info['total_remaining']}/{info['total_limit']}")
        print(f"\nДетали:")
        for t in info['tokens']:
            print(f"  • {t['label']}: {t['remaining']}/{t['limit']} {'🟢' if t['is_active'] else '🔴'}")
        print(f"{'='*50}\n")
