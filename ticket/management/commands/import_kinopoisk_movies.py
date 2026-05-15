import requests
from django.core.management.base import BaseCommand
from django.conf import settings
from django.utils import timezone
from django.core.files.base import ContentFile
from datetime import datetime, timedelta
import random
import logging
import time
import re
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from ticket.models import (
    Movie, Genre, AgeRating, Director, Actor, Country,
    MovieDirector, MovieActor, MovieGenre, Hall, Screening
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Импорт фильмов из API Poiskkino.dev'

    def add_arguments(self, parser):
        parser.add_argument('--pages', type=int, default=3)
        parser.add_argument('--screening-days', type=int, default=30)
        parser.add_argument('--verbose', action='store_true')
        parser.add_argument('--skip-posters', action='store_true')
        parser.add_argument('--skip-persons', action='store_true')

    def handle(self, *args, **options):
        api_key_raw = getattr(settings, 'KINOPOISK_API_KEY', None)
        if not api_key_raw:
            self.stderr.write(self.style.ERROR('ОШИБКА: KINOPOISK_API_KEY не найден!'))
            return

        if isinstance(api_key_raw, list):
            api_key = api_key_raw[0] if api_key_raw else None
        else:
            api_key = api_key_raw

        if not api_key:
            self.stderr.write(self.style.ERROR('ОШИБКА: Нет валидного API ключа!'))
            return

        self.verbose = options.get('verbose', False)
        self.skip_posters = options.get('skip_posters', False)
        self.skip_persons = options.get('skip_persons', False)
        self.screening_days = options.get('screening_days', 30)
        pages = options.get('pages', 3)

        # Создаём залы если нет
        if Hall.objects.count() == 0:
            self.stdout.write("🏗️ Создаём залы...")
            hall_type, _ = HallType.objects.get_or_create(name="Стандартный", defaults={'capacity': 100})
            Hall.objects.get_or_create(name="Зал 1", defaults={'rows': 10, 'seats_per_row': 10, 'hall_type': hall_type})
            Hall.objects.get_or_create(name="Зал 2", defaults={'rows': 8, 'seats_per_row': 12, 'hall_type': hall_type})
            Hall.objects.get_or_create(name="Зал 3", defaults={'rows': 12, 'seats_per_row': 10, 'hall_type': hall_type})
            self.stdout.write(self.style.SUCCESS('✅ Залы созданы'))

        self.halls = list(Hall.objects.all())

        # Кэши
        self.existing_countries = {c.name.lower(): c for c in Country.objects.all()}
        self.existing_genres = {g.name.lower(): g for g in Genre.objects.all()}
        self.existing_directors = {}
        self.existing_actors = {}

        self.session = requests.Session()
        retry_strategy = Retry(total=3, backoff_factor=1)
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        self.stdout.write(self.style.SUCCESS('🎬 ИМПОРТ ФИЛЬМОВ'))
        self.stdout.write('=' * 50)

        stats = {
            'movies': 0, 'posters': 0, 'countries': 0,
            'directors': 0, 'actors': 0, 'screenings': 0,
            'errors': 0
        }

        base_url = "https://api.poiskkino.dev/v1.4"
        headers = {"X-API-KEY": api_key, "accept": "application/json"}
        current_year = datetime.now().year

        for page in range(1, pages + 1):
            self.stdout.write(f"\n📄 Страница {page}/{pages}...")

            params = {
                "page": page, "limit": 50,
                "sortField": "votes.kp", "sortType": "-1",
                "type": "movie", "year": f"{current_year-2}-{current_year}",
            }

            try:
                response = self.session.get(f"{base_url}/movie", headers=headers, params=params, timeout=30)
                if response.status_code != 200:
                    self.stderr.write(f'❌ Ошибка API: {response.status_code}')
                    continue

                data = response.json()
                movies = data.get('docs', [])
                if not movies:
                    break

                for movie_data in movies:
                    try:
                        result = self.process_movie(movie_data, headers, stats)
                        if result == 'new':
                            stats['movies'] += 1
                            if self.verbose:
                                self.stdout.write(f"  ✅ {movie_data.get('name', 'Unknown')[:50]}")
                    except Exception as e:
                        stats['errors'] += 1
                        if self.verbose:
                            self.stderr.write(f"  ❌ Ошибка: {str(e)[:100]}")
                    time.sleep(0.2)

            except Exception as e:
                self.stderr.write(f'Ошибка: {e}')

        self.print_stats(stats)

    def get_movie_details(self, movie_id, headers):
        """Получение полной информации о фильме"""
        if not movie_id:
            return None
        try:
            response = self.session.get(
                f"https://api.poiskkino.dev/v1.4/movie/{movie_id}",
                headers=headers, timeout=15
            )
            if response.status_code == 200:
                return response.json()
        except Exception:
            pass
        return None

    def get_or_create_country(self, country_name):
        """Создание страны"""
        if not country_name or len(country_name) > 20:
            return None

        country_lower = country_name.lower().strip()
        if country_lower in self.existing_countries:
            return self.existing_countries[country_lower]

        known = {'россия': 'RU', 'сша': 'US', 'великобритания': 'GB', 'германия': 'DE',
                'франция': 'FR', 'италия': 'IT', 'испания': 'ES', 'япония': 'JP',
                'китай': 'CN', 'южная корея': 'KR', 'канада': 'CA', 'австралия': 'AU'}

        for name_ru, code in known.items():
            if name_ru in country_lower:
                country, _ = Country.objects.get_or_create(name=name_ru.capitalize(), defaults={'code': code})
                self.existing_countries[country_lower] = country
                return country
        return None

    def get_or_create_genre(self, genre_name):
        """Создание жанра"""
        if not genre_name:
            return None
        name_lower = genre_name.lower().strip()
        if name_lower in self.existing_genres:
            return self.existing_genres[name_lower]
        genre, _ = Genre.objects.get_or_create(name=genre_name.capitalize())
        self.existing_genres[name_lower] = genre
        return genre

    def process_person(self, person_data, role, headers):
        """Обработка персоны (актёр или режиссёр)"""
        name = person_data.get('name', '')
        if not name or len(name) < 2:
            return None

        name_parts = name.split(' ', 1)
        first_name = name_parts[0][:20]
        last_name = name_parts[1][:20] if len(name_parts) > 1 else ''
        key = f"{first_name.lower()}{last_name.lower()}"

        if role == 'director':
            if key in self.existing_directors:
                return self.existing_directors[key]
            director, created = Director.objects.get_or_create(name=first_name, surname=last_name)
            self.existing_directors[key] = director
            return director
        else:
            if key in self.existing_actors:
                return self.existing_actors[key]
            actor, created = Actor.objects.get_or_create(name=first_name, surname=last_name)
            self.existing_actors[key] = actor
            return actor

    def download_poster(self, url, title):
        """Скачивание постера"""
        if not url:
            return None
        try:
            response = self.session.get(url, timeout=20)
            if response.status_code == 200:
                safe_title = re.sub(r'[^\w\s-]', '', title)[:50]
                return ContentFile(response.content, name=f"{safe_title}.jpg")
        except Exception:
            pass
        return None

    def create_screenings(self, movie, stats):
        """Создание сеансов для фильма"""
        if not self.halls:
            return 0

        created = 0
        today = timezone.now().date()
        time_slots = [10, 12, 14, 16, 18, 20]

        for _ in range(random.randint(2, 4)):
            hall = random.choice(self.halls)
            day_offset = random.randint(0, self.screening_days)
            session_date = today + timedelta(days=day_offset)
            hour = random.choice(time_slots)
            start_time = timezone.make_aware(datetime.combine(session_date, datetime.min.time().replace(hour=hour)))
            end_time = start_time + timedelta(minutes=movie.duration + 20)

            if not Screening.objects.filter(hall=hall, start_time__lt=end_time, end_time__gt=start_time).exists():
                Screening.objects.create(
                    movie=movie, hall=hall, start_time=start_time,
                    end_time=end_time, price=random.randint(250, 500)
                )
                created += 1

        stats['screenings'] += created
        return created

    def process_movie(self, movie_data, headers, stats):
        """Обработка одного фильма со всеми данными"""
        title = movie_data.get('name')
        movie_id = movie_data.get('id')
        duration = movie_data.get('movieLength', 0)

        if not title or duration < 60:
            return 'skipped'

        # Получаем детальную информацию
        details = self.get_movie_details(movie_id, headers) if movie_id else movie_data
        if not details:
            details = movie_data

        # Проверяем существует ли фильм
        movie = Movie.objects.filter(title=title).first()
        is_new = movie is None

        if is_new:
            # Возрастной рейтинг
            age_str = f"{details.get('ageRating', 16)}+"
            age_rating, _ = AgeRating.objects.get_or_create(name=age_str)

            # Описание
            description = details.get('description', '') or details.get('shortDescription', 'Описание отсутствует')
            description = description[:1000]

            # Создаём фильм
            movie = Movie.objects.create(
                title=title[:100],
                short_description=description[:200] if description else '',
                description=description,
                duration=duration,
                release_year=details.get('year', datetime.now().year),
                age_rating=age_rating
            )

            # Жанры
            for genre_data in details.get('genres', []):
                genre_name = genre_data.get('name')
                if genre_name:
                    genre = self.get_or_create_genre(genre_name)
                    if genre:
                        MovieGenre.objects.get_or_create(movie=movie, genre=genre)

            # Страны
            for country_data in details.get('countries', []):
                country_name = country_data.get('name')
                if country_name:
                    country = self.get_or_create_country(country_name)
                    if country:
                        movie.countries.add(country)

            # Персоны (актёры и режиссёры)
            if not self.skip_persons:
                for person in details.get('persons', [])[:30]:
                    profession = person.get('profession', '').lower()
                    person_name = person.get('name')
                    if not person_name:
                        continue

                    if 'режисс' in profession:
                        director = self.process_person(person, 'director', headers)
                        if director:
                            MovieDirector.objects.get_or_create(movie=movie, director=director)
                    elif 'акт' in profession:
                        actor = self.process_person(person, 'actor', headers)
                        if actor:
                            MovieActor.objects.get_or_create(movie=movie, actor=actor)

            # Постер
            if not self.skip_posters:
                poster_url = None
                poster_data = details.get('poster', {})
                if isinstance(poster_data, dict):
                    poster_url = poster_data.get('url') or poster_data.get('previewUrl')
                if poster_url:
                    poster_content = self.download_poster(poster_url, title)
                    if poster_content:
                        movie.poster.save(f"{title[:50]}.jpg", poster_content, save=True)
                        stats['posters'] += 1

            # Сеансы
            if self.screening_days > 0:
                self.create_screenings(movie, stats)

            return 'new'

        return 'skipped'

    def print_stats(self, stats):
        self.stdout.write(self.style.SUCCESS('\n' + '=' * 50))
        self.stdout.write(self.style.SUCCESS('📊 ИТОГИ ИМПОРТА:'))
        self.stdout.write(f'   🎬 Фильмов: {stats["movies"]}')
        self.stdout.write(f'   🖼️ Постеров: {stats["posters"]}')
        self.stdout.write(f'   🎭 Сеансов: {stats["screenings"]}')
        if stats['errors'] > 0:
            self.stdout.write(self.style.WARNING(f'   ⚠️ Ошибок: {stats["errors"]}'))
        self.stdout.write(self.style.SUCCESS('=' * 50))
