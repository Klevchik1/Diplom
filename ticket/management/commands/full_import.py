import logging
import time
import random
import re
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.core.files.base import ContentFile
from ticket.models import (
    Movie, Genre, AgeRating, Director, Actor,
    MovieDirector, MovieActor, MovieGenre, Hall, Screening, APIToken, Country
)
from ticket.tmdb_client import KinopoiskDevClient

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Полный импорт фильмов с сеансами'

    def add_arguments(self, parser):
        parser.add_argument('--pages', type=int, default=3)
        parser.add_argument('--min-duration', type=int, default=60)
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--verbose', action='store_true')

    def handle(self, *args, **options):
        pages = options['pages']
        min_duration = options['min_duration']
        self.dry_run = options['dry_run']
        self.verbose = options['verbose']

        self.time_slots = [10, 12, 14, 16, 18, 20]
        self.screening_days = 30
        self.screening_interval = 20
        self.min_screenings_per_movie = 3
        self.max_screenings_per_movie = 6

        self.known_countries = {
            'россия': 'RU', 'сша': 'US', 'великобритания': 'GB', 'германия': 'DE',
            'франция': 'FR', 'италия': 'IT', 'испания': 'ES', 'япония': 'JP',
            'китай': 'CN', 'южная корея': 'KR', 'канада': 'CA', 'австралия': 'AU',
        }

        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS('🎬 ПОЛНЫЙ ИМПОРТ ФИЛЬМОВ'))
        self.stdout.write(self.style.SUCCESS('=' * 60))

        self.halls = list(Hall.objects.all())
        if not self.halls:
            self.stdout.write(self.style.ERROR('❌ Нет залов!'))
            return
        self.stdout.write(f"🏗️ Залов: {len(self.halls)}")

        token = APIToken.objects.filter(is_active=True, label='Резервный 4').first()
        if not token:
            token = APIToken.objects.filter(is_active=True).first()
        if not token:
            self.stdout.write(self.style.ERROR('❌ Нет активных API токенов!'))
            return
        self.stdout.write(f"🔑 Используем токен: {token.label}")

        self.client = KinopoiskDevClient(token_model=token)

        self.existing_countries = {c.name.lower(): c for c in Country.objects.all()}
        self.existing_directors = {}
        self.existing_actors = {}
        self.existing_genres = {g.name.lower(): g for g in Genre.objects.all()}

        self.stats = {
            'movies': 0, 'genres': 0, 'countries': 0,
            'directors': 0, 'actors': 0, 'posters': 0,
            'screenings': 0, 'errors': 0, 'api_requests': 0
        }

        current_year = datetime.now().year

        for page in range(1, pages + 1):
            self.stdout.write(f"\n📄 Страница {page}/{pages}...")

            result = self.client.get_movies_page(
                page=page, limit=50,
                year_from=current_year - 2,
                year_to=current_year
            )
            self.stats['api_requests'] += 1

            if not result or 'docs' not in result:
                self.stdout.write(self.style.WARNING('  Нет данных'))
                continue

            movies_data = result.get('docs', [])
            self.stdout.write(f"  Получено {len(movies_data)} фильмов")

            for movie_data in movies_data:
                try:
                    self.process_movie(movie_data, min_duration)
                    time.sleep(0.2)
                except Exception as e:
                    self.stats['errors'] += 1
                    if self.verbose:
                        self.stderr.write(f"  Ошибка: {str(e)[:100]}")
                    time.sleep(0.5)

        self.print_stats()

    def get_or_create_country(self, country_name):
        if not country_name or len(country_name) > 20:
            return None
        country_lower = country_name.lower().strip()
        if country_lower in self.existing_countries:
            return self.existing_countries[country_lower]
        for name_ru, code in self.known_countries.items():
            if name_ru in country_lower:
                if not self.dry_run:
                    country, _ = Country.objects.get_or_create(name=name_ru.capitalize(), defaults={'code': code})
                else:
                    country = type('obj', (), {})()
                self.existing_countries[country_lower] = country
                self.stats['countries'] += 1
                return country
        return None

    def get_or_create_genre(self, genre_name):
        if not genre_name:
            return None
        name_lower = genre_name.lower().strip()
        if name_lower in self.existing_genres:
            return self.existing_genres[name_lower]
        if not self.dry_run:
            genre, _ = Genre.objects.get_or_create(name=genre_name.capitalize())
        else:
            genre = type('obj', (), {})()
        self.existing_genres[name_lower] = genre
        self.stats['genres'] += 1
        return genre

    def get_or_create_person(self, person_data, role):
        name = person_data.get('name', '')
        if not name or len(name) < 2:
            return None
        name_parts = name.split(' ', 1)
        first_name = name_parts[0][:20]
        last_name = name_parts[1][:20] if len(name_parts) > 1 else ""
        key = f"{first_name.lower()}_{last_name.lower()}"

        if role == 'director':
            if key in self.existing_directors:
                return self.existing_directors[key]
            if not self.dry_run:
                person_obj, _ = Director.objects.get_or_create(name=first_name, surname=last_name)
            else:
                person_obj = type('obj', (), {})()
            self.existing_directors[key] = person_obj
            self.stats['directors'] += 1
            return person_obj
        else:
            if key in self.existing_actors:
                return self.existing_actors[key]
            if not self.dry_run:
                person_obj, _ = Actor.objects.get_or_create(name=first_name, surname=last_name)
            else:
                person_obj = type('obj', (), {})()
            self.existing_actors[key] = person_obj
            self.stats['actors'] += 1
            return person_obj

    def download_poster(self, url, title):
        if not url:
            return None
        try:
            content = self.client.download_image(url)
            if content:
                safe_title = re.sub(r'[^\w\s-]', '', title)[:50]
                return ContentFile(content, name=f"{safe_title}.jpg")
        except Exception:
            pass
        return None

    def create_screenings(self, movie):
        created = 0
        today = timezone.now().date()
        num = random.randint(self.min_screenings_per_movie, self.max_screenings_per_movie)

        for _ in range(num):
            hall = random.choice(self.halls)
            day_offset = random.randint(0, self.screening_days)
            session_date = today + timedelta(days=day_offset)
            hour = random.choice(self.time_slots)
            start_time = timezone.make_aware(datetime(session_date.year, session_date.month, session_date.day, hour, 0))
            end_time = start_time + timedelta(minutes=movie.duration + self.screening_interval)

            if not Screening.objects.filter(hall=hall, start_time__lt=end_time, end_time__gt=start_time).exists():
                if not self.dry_run:
                    Screening.objects.create(movie=movie, hall=hall, start_time=start_time, end_time=end_time)
                created += 1
        return created

    def process_movie(self, movie_data, min_duration):
        title = movie_data.get('name')
        movie_id = movie_data.get('id')
        duration = movie_data.get('movieLength', 0)

        if not title or duration < min_duration:
            return

        if Movie.objects.filter(title=title).exists():
            if self.verbose:
                self.stdout.write(f"  ⏭️ Пропущен: {title[:40]}")
            return

        details = self.client.get_movie_by_id(movie_id)
        self.stats['api_requests'] += 1

        if not details:
            details = movie_data

        if self.verbose:
            self.stdout.write(f"\n  🎬 {title[:40]}...")

        age_str = f"{details.get('ageRating', 16)}+"
        if not self.dry_run:
            age_rating, _ = AgeRating.objects.get_or_create(name=age_str)

        description = details.get('description', '') or details.get('shortDescription', f'Фильм {title}')

        if not self.dry_run:
            movie = Movie.objects.create(
                title=title[:50],
                short_description=description[:197] + '...' if len(description) > 200 else description[:200],
                description=description[:1000],
                duration=duration,
                release_year=details.get('year', datetime.now().year),
                age_rating=age_rating
            )
            self.stats['movies'] += 1
        else:
            movie = type('obj', (), {'duration': duration, 'id': None})()

        for genre_data in details.get('genres', []):
            genre_name = genre_data.get('name')
            if genre_name:
                genre = self.get_or_create_genre(genre_name)
                if genre and not self.dry_run:
                    MovieGenre.objects.get_or_create(movie=movie, genre=genre)

        for person in details.get('persons', [])[:30]:
            profession = person.get('profession', '').lower()
            person_name = person.get('name')
            if not person_name:
                continue

            if 'режисс' in profession:
                director = self.get_or_create_person(person, 'director')
                if director and not self.dry_run:
                    MovieDirector.objects.get_or_create(movie=movie, director=director)
            elif 'акт' in profession:
                actor = self.get_or_create_person(person, 'actor')
                if actor and not self.dry_run:
                    MovieActor.objects.get_or_create(movie=movie, actor=actor)

        if not self.dry_run:
            poster_url = None
            poster_data = details.get('poster', {})
            if isinstance(poster_data, dict):
                poster_url = poster_data.get('url') or poster_data.get('previewUrl')
            if poster_url and not movie.poster:
                poster_content = self.download_poster(poster_url, title)
                if poster_content:
                    movie.poster.save(f"{title[:50]}.jpg", poster_content, save=True)
                    self.stats['posters'] += 1

            screenings = self.create_screenings(movie)
            self.stats['screenings'] += screenings
            if self.verbose:
                self.stdout.write(f"    🎬 Сеансов: {screenings}")

        if self.verbose:
            self.stdout.write(f"    ✅ Готово")

    def print_stats(self):
        self.stdout.write(self.style.SUCCESS('\n' + '=' * 60))
        self.stdout.write(self.style.SUCCESS('📊 ИТОГИ'))
        self.stdout.write('=' * 60)
        self.stdout.write(f"   🎬 Фильмов: {self.stats['movies']}")
        self.stdout.write(f"   🎭 Жанров создано: {self.stats['genres']}")
        self.stdout.write(f"   🌍 Стран создано: {self.stats['countries']}")
        self.stdout.write(f"   👤 Режиссёров: {self.stats['directors']}")
        self.stdout.write(f"   🎭 Актёров: {self.stats['actors']}")
        self.stdout.write(f"   🖼️ Постеров: {self.stats['posters']}")
        self.stdout.write(f"   🎬 Сеансов: {self.stats['screenings']}")
        self.stdout.write(f"   🔌 API запросов: {self.stats['api_requests']}")
        if self.stats['errors'] > 0:
            self.stdout.write(self.style.WARNING(f"   ⚠️ Ошибок: {self.stats['errors']}"))
        self.stdout.write(self.style.SUCCESS('=' * 60))

        if self.dry_run:
            self.stdout.write(self.style.WARNING('\n⚠️ ПРОБНЫЙ ЗАПУСК. Удалите --dry-run для реального импорта.'))
