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
    MovieDirector, MovieActor, MovieGenre, APIToken, Country,
    MovieCountry
)
from ticket.tmdb_client import KinopoiskDevClient

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Импорт фильмов из API Poiskkino.dev (без создания сеансов)'

    def add_arguments(self, parser):
        parser.add_argument('--pages', type=int, default=3, help='Количество страниц (по 50 фильмов)')
        parser.add_argument('--year-from', type=int, default=datetime.now().year - 2, help='Год начала')
        parser.add_argument('--year-to', type=int, default=datetime.now().year, help='Год конца')
        parser.add_argument('--min-duration', type=int, default=60, help='Минимальная длительность фильма')
        parser.add_argument('--dry-run', action='store_true', help='Пробный запуск без сохранения')
        parser.add_argument('--verbose', action='store_true', help='Подробный вывод')
        parser.add_argument('--no-posters', action='store_true', help='Не скачивать постеры')
        parser.add_argument('--no-persons', action='store_true', help='Не импортировать персон')

    def handle(self, *args, **options):
        self.pages = options['pages']
        self.year_from = options['year_from']
        self.year_to = options['year_to']
        self.min_duration = options['min_duration']
        self.dry_run = options['dry_run']
        self.verbose = options['verbose']
        self.import_posters = not options['no_posters']
        self.import_persons = not options['no_persons']

        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS('🎬 ИМПОРТ ФИЛЬМОВ (БЕЗ СЕАНСОВ)'))
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(f"📅 Годы: {self.year_from}-{self.year_to}")
        self.stdout.write(f"📄 Страниц: {self.pages}")
        self.stdout.write(f"🎬 Мин. длительность: {self.min_duration} мин")
        self.stdout.write(f"🖼️ Постеры: {'да' if self.import_posters else 'нет'}")
        self.stdout.write(f"👥 Персоны: {'да' if self.import_persons else 'нет'}")
        self.stdout.write(f"🧪 Тестовый режим: {'да' if self.dry_run else 'нет'}")
        self.stdout.write('=' * 60)

        # Получаем активный токен
        token = APIToken.objects.filter(is_active=True).first()
        if not token:
            self.stdout.write(self.style.ERROR('❌ Нет активных API токенов!'))
            self.stdout.write('   Добавьте токены через админ-панель или команду init_tokens')
            return
        self.stdout.write(
            f"🔑 Используем токен: {token.label} (осталось: {token.remaining_today()}/{token.daily_limit})")

        self.client = KinopoiskDevClient(token_model=token)

        # Кэши для существующих данных
        self.existing_countries = {c.name.lower(): c for c in Country.objects.all()}
        self.existing_directors = {}
        self.existing_actors = {}
        self.existing_genres = {g.name.lower(): g for g in Genre.objects.all()}
        self.existing_movies = {m.title: m for m in Movie.objects.all()}  # Теперь храним объекты

        self.stats = {
            'movies_new': 0,
            'movies_updated': 0,
            'movies_skipped': 0,
            'genres_created': 0,
            'countries_created': 0,
            'directors_created': 0,
            'actors_created': 0,
            'posters': 0,
            'api_requests': 0,
            'errors': 0
        }

        self.known_countries = {
            'россия': 'RU', 'рф': 'RU', 'russia': 'RU',
            'сша': 'US', 'usa': 'US', 'united states': 'US', 'america': 'US',
            'великобритания': 'GB', 'uk': 'GB', 'united kingdom': 'GB',
            'германия': 'DE', 'germany': 'DE',
            'франция': 'FR', 'france': 'FR',
            'италия': 'IT', 'italy': 'IT',
            'испания': 'ES', 'spain': 'ES',
            'япония': 'JP', 'japan': 'JP',
            'китай': 'CN', 'china': 'CN',
            'южная корея': 'KR', 'korea': 'KR', 'south korea': 'KR',
            'канада': 'CA', 'canada': 'CA',
            'австралия': 'AU', 'australia': 'AU',
            'индия': 'IN', 'india': 'IN',
            'казахстан': 'KZ', 'kazakhstan': 'KZ',
        }

        for page in range(1, self.pages + 1):
            # Проверяем остаток запросов
            if token.remaining_today() < 5:
                self.stdout.write(self.style.WARNING(
                    f'\n⚠️ У токена {token.label} осталось {token.remaining_today()} запросов. Остановка.'))
                break

            self.stdout.write(f"\n📄 Страница {page}/{self.pages}...")

            result = self.client.get_movies_page(
                page=page, limit=50,
                year_from=self.year_from,
                year_to=self.year_to
            )
            self.stats['api_requests'] += 1

            if not result or 'docs' not in result:
                self.stdout.write(self.style.WARNING('  Нет данных'))
                continue

            movies_data = result.get('docs', [])
            self.stdout.write(f"  Получено {len(movies_data)} фильмов")

            for movie_data in movies_data:
                try:
                    self.process_movie(movie_data)
                    time.sleep(0.2)
                except Exception as e:
                    self.stats['errors'] += 1
                    if self.verbose:
                        self.stderr.write(f"  Ошибка: {str(e)[:100]}")
                    time.sleep(0.5)

        self.print_stats()

    def get_or_create_country(self, country_name):
        """Создать или получить страну"""
        if not country_name or len(country_name) > 20:
            return None
        country_lower = country_name.lower().strip()
        if country_lower in self.existing_countries:
            return self.existing_countries[country_lower]

        for name_ru, code in self.known_countries.items():
            if name_ru in country_lower:
                if not self.dry_run:
                    country, created = Country.objects.get_or_create(
                        name=name_ru.capitalize(),
                        defaults={'code': code}
                    )
                else:
                    country = type('obj', (), {})()
                    created = False
                self.existing_countries[country_lower] = country
                if created:
                    self.stats['countries_created'] += 1
                    if self.verbose:
                        self.stdout.write(f"    🌍 Создана страна: {country.name}")
                return country
        return None

    def get_or_create_genre(self, genre_name):
        """Создать или получить жанр"""
        if not genre_name:
            return None
        name_lower = genre_name.lower().strip()
        if name_lower in self.existing_genres:
            return self.existing_genres[name_lower]
        if not self.dry_run:
            genre, created = Genre.objects.get_or_create(name=genre_name.capitalize())
        else:
            genre = type('obj', (), {})()
            created = False
        self.existing_genres[name_lower] = genre
        if created:
            self.stats['genres_created'] += 1
            if self.verbose:
                self.stdout.write(f"    🎭 Создан жанр: {genre.name}")
        return genre

    def get_or_create_person(self, person_data, role):
        """Создать или получить актёра или режиссёра"""
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
                person_obj, created = Director.objects.get_or_create(name=first_name, surname=last_name)
                if created:
                    self.stats['directors_created'] += 1
            else:
                person_obj = type('obj', (), {})()
                created = False
            self.existing_directors[key] = person_obj
            return person_obj
        else:
            if key in self.existing_actors:
                return self.existing_actors[key]
            if not self.dry_run:
                person_obj, created = Actor.objects.get_or_create(name=first_name, surname=last_name)
                if created:
                    self.stats['actors_created'] += 1
            else:
                person_obj = type('obj', (), {})()
                created = False
            self.existing_actors[key] = person_obj
            return person_obj

    def download_poster(self, url, title):
        """Скачать постер"""
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

    def update_movie_fields(self, movie, details):
        """Обновление полей фильма"""
        updated = False

        # Описание
        new_description = details.get('description', '') or details.get('shortDescription', '')
        if new_description and movie.description != new_description[:1000]:
            movie.description = new_description[:1000]
            updated = True

        # Короткое описание
        if new_description and not movie.short_description:
            movie.short_description = new_description[:197] + '...' if len(new_description) > 200 else new_description
            updated = True

        # Год выпуска
        new_year = details.get('year', datetime.now().year)
        if movie.release_year != new_year:
            movie.release_year = new_year
            updated = True

        # Длительность (если изменилась)
        new_duration = details.get('movieLength', movie.duration)
        if new_duration and movie.duration != new_duration:
            movie.duration = new_duration
            updated = True

        # Возрастной рейтинг
        age_str = f"{details.get('ageRating', 16)}+"
        if not self.dry_run:
            new_age_rating, _ = AgeRating.objects.get_or_create(name=age_str)
            if movie.age_rating != new_age_rating:
                movie.age_rating = new_age_rating
                updated = True

        if updated and not self.dry_run:
            movie.save(update_fields=['description', 'short_description', 'release_year', 'duration', 'age_rating'])
            if self.verbose:
                self.stdout.write(f"    📝 Обновлены поля фильма")

        return updated

    def update_movie_relations(self, movie, details):
        """Обновление связей фильма (жанры, страны, персоны)"""
        if self.dry_run:
            return

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
                    MovieCountry.objects.get_or_create(movie=movie, country=country)

        # Персоны
        if self.import_persons:
            for person in details.get('persons', [])[:30]:
                profession = person.get('profession', '').lower()
                person_name = person.get('name')
                if not person_name:
                    continue

                if 'режисс' in profession:
                    director = self.get_or_create_person(person, 'director')
                    if director:
                        MovieDirector.objects.get_or_create(movie=movie, director=director)
                elif 'акт' in profession:
                    actor = self.get_or_create_person(person, 'actor')
                    if actor:
                        MovieActor.objects.get_or_create(movie=movie, actor=actor)

    def process_movie(self, movie_data):
        """Обработать один фильм"""
        title = movie_data.get('name')
        movie_id = movie_data.get('id')
        duration = movie_data.get('movieLength', 0)

        if not title or duration < self.min_duration:
            self.stats['movies_skipped'] += 1
            return

        # Получаем детальную информацию
        details = self.client.get_movie_by_id(movie_id)
        self.stats['api_requests'] += 1

        if not details:
            details = movie_data

        # Проверяем существование фильма
        existing_movie = self.existing_movies.get(title)

        if existing_movie:
            # Обновляем существующий фильм
            self.update_movie_fields(existing_movie, details)
            self.update_movie_relations(existing_movie, details)
            self.stats['movies_updated'] += 1
            if self.verbose:
                self.stdout.write(f"  🔄 Обновлён: {title[:40]}")

            # Постер (если нет)
            if self.import_posters and not existing_movie.poster:
                poster_url = None
                poster_data = details.get('poster', {})
                if isinstance(poster_data, dict):
                    poster_url = poster_data.get('url') or poster_data.get('previewUrl')
                if poster_url:
                    poster_content = self.download_poster(poster_url, title)
                    if poster_content:
                        existing_movie.poster.save(f"{title[:50]}.jpg", poster_content, save=True)
                        self.stats['posters'] += 1
                        if self.verbose:
                            self.stdout.write(f"    🖼️ Добавлен постер")
        else:
            # Создаём новый фильм
            age_str = f"{details.get('ageRating', 16)}+"
            if not self.dry_run:
                age_rating, _ = AgeRating.objects.get_or_create(name=age_str)

            description = details.get('description', '') or details.get('shortDescription', f'Фильм {title}')
            description = description[:1000]
            short_desc = description[:197] + '...' if len(description) > 200 else description

            if not self.dry_run:
                movie = Movie.objects.create(
                    title=title[:50],
                    short_description=short_desc,
                    description=description,
                    duration=duration,
                    release_year=details.get('year', datetime.now().year),
                    age_rating=age_rating
                )
                self.stats['movies_new'] += 1
                self.existing_movies[title] = movie
                if self.verbose:
                    self.stdout.write(f"  ✅ Создан: {title[:40]} (ID: {movie.id})")
            else:
                movie = type('obj', (), {'id': None, 'poster': None})()

            # Жанры, страны, персоны
            self.update_movie_relations(movie, details)

            # Постер
            if self.import_posters and not self.dry_run and not movie.poster:
                poster_url = None
                poster_data = details.get('poster', {})
                if isinstance(poster_data, dict):
                    poster_url = poster_data.get('url') or poster_data.get('previewUrl')
                if poster_url:
                    poster_content = self.download_poster(poster_url, title)
                    if poster_content:
                        movie.poster.save(f"{title[:50]}.jpg", poster_content, save=True)
                        self.stats['posters'] += 1
                        if self.verbose:
                            self.stdout.write(f"    🖼️ Постер скачан")

    def print_stats(self):
        self.stdout.write(self.style.SUCCESS('\n' + '=' * 60))
        self.stdout.write(self.style.SUCCESS('📊 ИТОГИ ИМПОРТА'))
        self.stdout.write('=' * 60)
        self.stdout.write(f"   🎬 Фильмов создано: {self.stats['movies_new']}")
        self.stdout.write(f"   🔄 Фильмов обновлено: {self.stats['movies_updated']}")
        self.stdout.write(f"   ⏭️ Фильмов пропущено: {self.stats['movies_skipped']}")
        self.stdout.write(f"   🎭 Жанров создано: {self.stats['genres_created']}")
        self.stdout.write(f"   🌍 Стран создано: {self.stats['countries_created']}")
        self.stdout.write(f"   👤 Режиссёров создано: {self.stats['directors_created']}")
        self.stdout.write(f"   🎭 Актёров создано: {self.stats['actors_created']}")
        self.stdout.write(f"   🖼️ Постеров скачано: {self.stats['posters']}")
        self.stdout.write(f"   🔌 API запросов: {self.stats['api_requests']}")
        if self.stats['errors'] > 0:
            self.stdout.write(self.style.WARNING(f"   ⚠️ Ошибок: {self.stats['errors']}"))
        self.stdout.write('=' * 60)

        if self.dry_run:
            self.stdout.write(self.style.WARNING('\n⚠️ ПРОБНЫЙ ЗАПУСК. Удалите --dry-run для реального импорта.'))