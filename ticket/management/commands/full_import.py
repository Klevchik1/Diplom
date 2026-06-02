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
    MovieDirector, MovieActor, MovieGenre, Hall, Screening, APIToken, Country,
    MovieCountry  # ДОБАВЛЕНО
)
from ticket.tmdb_client import KinopoiskDevClient

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Полный импорт фильмов с сеансами'

    def add_arguments(self, parser):
        parser.add_argument('--pages', type=int, default=3, help='Количество страниц (по 50 фильмов)')
        parser.add_argument('--min-duration', type=int, default=60, help='Минимальная длительность фильма')
        parser.add_argument('--dry-run', action='store_true', help='Пробный запуск без сохранения')
        parser.add_argument('--verbose', action='store_true', help='Подробный вывод')
        parser.add_argument('--screening-days', type=int, default=30, help='На сколько дней вперёд создавать сеансы')
        parser.add_argument('--min-screenings', type=int, default=3, help='Минимум сеансов на фильм')
        parser.add_argument('--max-screenings', type=int, default=6, help='Максимум сеансов на фильм')

    def handle(self, *args, **options):
        pages = options['pages']
        min_duration = options['min_duration']
        self.dry_run = options['dry_run']
        self.verbose = options['verbose']
        self.screening_days = options['screening_days']
        self.min_screenings_per_movie = options['min_screenings']
        self.max_screenings_per_movie = options['max_screenings']

        self.time_slots = [10, 12, 14, 16, 18, 20, 22]  # Часы начала сеансов
        self.screening_interval = 20  # Минут между сеансами

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

        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS('🎬 ПОЛНЫЙ ИМПОРТ ФИЛЬМОВ С СЕАНСАМИ'))
        self.stdout.write(self.style.SUCCESS('=' * 60))

        # Получаем залы
        self.halls = list(Hall.objects.all())
        if not self.halls:
            self.stdout.write(self.style.ERROR('❌ Нет залов! Сначала создайте залы через админ-панель.'))
            return
        self.stdout.write(f"🏗️ Залов: {len(self.halls)}")

        # Получаем активный токен
        token = APIToken.objects.filter(is_active=True).first()
        if not token:
            self.stdout.write(self.style.ERROR('❌ Нет активных API токенов!'))
            self.stdout.write('   Добавьте токены через админ-панель или команду init_tokens')
            return
        self.stdout.write(f"🔑 Используем токен: {token.label} (осталось: {token.remaining_today()}/{token.daily_limit})")

        self.client = KinopoiskDevClient(token_model=token)

        # Кэши для существующих данных
        self.existing_countries = {c.name.lower(): c for c in Country.objects.all()}
        self.existing_directors = {}
        self.existing_actors = {}
        self.existing_genres = {g.name.lower(): g for g in Genre.objects.all()}
        self.existing_movies = set(Movie.objects.values_list('title', flat=True))

        self.stats = {
            'movies': 0, 'genres': 0, 'countries': 0,
            'directors': 0, 'actors': 0, 'posters': 0,
            'screenings': 0, 'errors': 0, 'api_requests': 0
        }

        current_year = datetime.now().year

        for page in range(1, pages + 1):
            # Проверяем остаток запросов
            if token.remaining_today() < 5:
                self.stdout.write(self.style.WARNING(f'\n⚠️ У токена {token.label} осталось {token.remaining_today()} запросов. Остановка.'))
                break

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
                    time.sleep(0.2)  # Пауза между фильмами
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
                    self.stats['countries'] += 1
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
            self.stats['genres'] += 1
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

    def create_screenings(self, movie):
        """Создать сеансы для фильма"""
        created = 0
        today = timezone.now().date()
        num = random.randint(self.min_screenings_per_movie, self.max_screenings_per_movie)

        for _ in range(num):
            hall = random.choice(self.halls)
            day_offset = random.randint(0, self.screening_days)
            session_date = today + timedelta(days=day_offset)
            hour = random.choice(self.time_slots)
            minute = random.choice([0, 10, 20, 30, 40, 50])  # Разные минуты
            start_time = timezone.make_aware(datetime(
                session_date.year, session_date.month, session_date.day, hour, minute
            ))
            end_time = start_time + timedelta(minutes=movie.duration + self.screening_interval)

            # Проверяем пересечение с другими сеансами
            if not Screening.objects.filter(hall=hall, start_time__lt=end_time, end_time__gt=start_time).exists():
                if not self.dry_run:
                    # Цена рассчитается автоматически при сохранении
                    screening = Screening(movie=movie, hall=hall, start_time=start_time)
                    screening.save()  # Триггеры сами рассчитают цену и end_time
                created += 1
        return created

    def process_movie(self, movie_data, min_duration):
        """Обработать один фильм"""
        title = movie_data.get('name')
        movie_id = movie_data.get('id')
        duration = movie_data.get('movieLength', 0)

        if not title or duration < min_duration:
            return

        # Пропускаем уже существующие
        if title in self.existing_movies:
            if self.verbose:
                self.stdout.write(f"  ⏭️ Пропущен: {title[:40]} (уже есть)")
            return

        # Получаем детальную информацию о фильме
        details = self.client.get_movie_by_id(movie_id)
        self.stats['api_requests'] += 1

        if not details:
            details = movie_data

        if self.verbose:
            self.stdout.write(f"\n  🎬 {title[:40]}...")

        # Возрастной рейтинг
        age_str = f"{details.get('ageRating', 16)}+"
        if not self.dry_run:
            age_rating, _ = AgeRating.objects.get_or_create(name=age_str)

        # Описание
        description = details.get('description', '') or details.get('shortDescription', f'Фильм {title}')

        # Создаём фильм
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
            self.existing_movies.add(title)
            if self.verbose:
                self.stdout.write(f"    ✅ Создан фильм ID: {movie.id}")
        else:
            movie = type('obj', (), {'duration': duration, 'id': None})()

        # Жанры
        for genre_data in details.get('genres', []):
            genre_name = genre_data.get('name')
            if genre_name:
                genre = self.get_or_create_genre(genre_name)
                if genre and not self.dry_run:
                    MovieGenre.objects.get_or_create(movie=movie, genre=genre)

        # СТРАНЫ (добавлено!)
        for country_data in details.get('countries', []):
            country_name = country_data.get('name')
            if country_name:
                country = self.get_or_create_country(country_name)
                if country and not self.dry_run:
                    MovieCountry.objects.get_or_create(movie=movie, country=country)
                    if self.verbose:
                        self.stdout.write(f"    🌍 Добавлена страна: {country.name}")

        # Персоны (актёры и режиссёры)
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

        # Постер
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
                    if self.verbose:
                        self.stdout.write(f"    🖼️ Постер скачан")

            # Сеансы
            screenings = self.create_screenings(movie)
            self.stats['screenings'] += screenings
            if self.verbose and screenings > 0:
                self.stdout.write(f"    🎬 Создано сеансов: {screenings}")

        if self.verbose:
            self.stdout.write(f"    ✅ Готово")

    def print_stats(self):
        self.stdout.write(self.style.SUCCESS('\n' + '=' * 60))
        self.stdout.write(self.style.SUCCESS('📊 ИТОГИ ИМПОРТА'))
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