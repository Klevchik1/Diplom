"""
Полный тестовый импорт фильмов с датами рождения и странами для актёров и режиссёров.
Запуск: python manage.py test_import_countries --pages=1 --limit=3 --verbose
"""

import logging
import re
import time
import requests
from datetime import datetime
from django.core.management.base import BaseCommand
from django.core.files.base import ContentFile
from django.utils import timezone

from ticket.models import (
    Movie, Genre, AgeRating, Director, Actor, Country, MovieCountry,
    MovieDirector, MovieActor, MovieGenre
)
from ticket.tmdb_client import KinopoiskDevClient

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Тестовый импорт фильмов (даты и страны для актёров и режиссёров)'

    def add_arguments(self, parser):
        parser.add_argument('--pages', type=int, default=1, help='Количество страниц')
        parser.add_argument('--limit', type=int, default=3, help='Максимум фильмов')
        parser.add_argument('--movie-ids', type=str, help='ID фильмов через запятую')
        parser.add_argument('--verbose', action='store_true', help='Подробный вывод')

    def handle(self, *args, **options):
        self.verbose = options['verbose']
        self.client = KinopoiskDevClient()
        self.api_key = self.client._api_key

        # Кэши
        self.existing_countries = {c.name.lower(): c for c in Country.objects.all()}
        self.existing_genres = {g.name.lower(): g for g in Genre.objects.all()}
        self.existing_movies = set(Movie.objects.values_list('title', flat=True))

        # Известные страны для маппинга
        self.known_countries = {
            'россия': 'RU', 'рф': 'RU', 'russia': 'RU', 'russian': 'RU',
            'сша': 'US', 'usa': 'US', 'united states': 'US', 'america': 'US', 'american': 'US',
            'великобритания': 'GB', 'uk': 'GB', 'united kingdom': 'GB', 'britain': 'GB',
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
            'украина': 'UA', 'ukraine': 'UA',
            'беларусь': 'BY', 'belarus': 'BY',
            'польша': 'PL', 'poland': 'PL',
            'турция': 'TR', 'turkey': 'TR',
        }

        self.stats = {
            'movies': 0,
            'countries_created': 0,
            'countries_linked': 0,
            'genres_created': 0,
            'directors_created': 0,
            'actors_created': 0,
            'directors_linked': 0,
            'actors_linked': 0,
            'directors_with_birthdate': 0,
            'actors_with_birthdate': 0,
            'directors_with_country': 0,
            'actors_with_country': 0,
            'posters': 0,
            'api_requests': 0,
        }

        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS('🧪 ТЕСТОВЫЙ ИМПОРТ ФИЛЬМОВ'))
        self.stdout.write(self.style.SUCCESS('=' * 60))

        movies_to_import = []

        if options['movie_ids']:
            ids = [int(x.strip()) for x in options['movie_ids'].split(',')]
            self.stdout.write(f"📋 Импорт по ID: {ids}")
            for movie_id in ids:
                result = self.client.get_movie_by_id(movie_id)
                self.stats['api_requests'] += 1
                if result:
                    movies_to_import.append(result)
                else:
                    self.stdout.write(self.style.WARNING(f"  ⚠️ Фильм с ID {movie_id} не найден"))
        else:
            self.stdout.write(f"📄 Поиск фильмов...")
            imported = 0
            for page in range(1, options['pages'] + 1):
                if imported >= options['limit']:
                    break
                result = self.client.get_movies_page(page=page, limit=50, year_from=2023, year_to=2025)
                self.stats['api_requests'] += 1
                if not result or 'docs' not in result:
                    continue
                for movie_data in result.get('docs', []):
                    if imported >= options['limit']:
                        break
                    duration = movie_data.get('movieLength', 0)
                    title = movie_data.get('name', '')
                    if duration < 60 or not title:
                        continue
                    movie_id = movie_data.get('id')
                    if movie_id:
                        details = self.client.get_movie_by_id(movie_id)
                        self.stats['api_requests'] += 1
                        if details:
                            movies_to_import.append(details)
                            imported += 1
                            if self.verbose:
                                self.stdout.write(f"  📥 {title[:40]}")

        self.stdout.write(f"\n🎬 Найдено фильмов: {len(movies_to_import)}")

        for i, movie_data in enumerate(movies_to_import, 1):
            self.stdout.write(f"\n{'─' * 40}")
            self.stdout.write(f"📽️ Фильм {i}/{len(movies_to_import)}")
            self.process_movie(movie_data)

        self.print_stats()
        self.show_summary()

    def fetch_person_details(self, person_id):
        """Получить полные данные персоны (дата рождения, место рождения)"""
        if not person_id:
            return None

        for attempt in range(2):
            try:
                url = f"https://api.poiskkino.dev/v1.4/person/{person_id}"
                headers = {"X-API-KEY": self.api_key}
                response = requests.get(url, headers=headers, timeout=15)
                self.stats['api_requests'] += 1

                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 429:
                    time.sleep(2)
                else:
                    return None
            except Exception:
                time.sleep(1)
        return None

    def extract_country_from_text(self, text):
        """Извлечь страну из текста"""
        if not text:
            return None
        text_lower = text.lower()
        for country_ru, code in self.known_countries.items():
            if country_ru in text_lower:
                return self.get_or_create_country(country_ru)
        return None

    def get_movie_directors(self, movie_id):
        """Получить режиссёров фильма"""
        if not movie_id:
            return []
        try:
            url = "https://api.poiskkino.dev/v1.5/person"
            params = {
                "movies.id": str(movie_id),
                "profession.value": "Режиссер",
                "limit": 50
            }
            headers = {"X-API-KEY": self.api_key}
            response = requests.get(url, headers=headers, params=params, timeout=15)
            self.stats['api_requests'] += 1
            if response.status_code == 200:
                data = response.json()
                return data.get('docs', [])
            return []
        except Exception as e:
            if self.verbose:
                self.stdout.write(f"     ⚠️ Ошибка запроса режиссёров: {str(e)[:50]}")
            return []

    def get_or_create_country(self, country_name):
        if not country_name:
            return None
        country_lower = country_name.lower().strip()
        if country_lower in self.existing_countries:
            return self.existing_countries[country_lower]

        for known_ru, code in self.known_countries.items():
            if known_ru in country_lower:
                country, created = Country.objects.get_or_create(
                    name=known_ru.capitalize(),
                    defaults={'code': code}
                )
                self.existing_countries[country_lower] = country
                if created:
                    self.stats['countries_created'] += 1
                    if self.verbose:
                        self.stdout.write(f"    🌍 Создана страна: {country.name}")
                return country
        return None

    def get_or_create_genre(self, genre_name):
        if not genre_name:
            return None
        name_lower = genre_name.lower().strip()
        if name_lower in self.existing_genres:
            return self.existing_genres[name_lower]
        genre, created = Genre.objects.get_or_create(name=genre_name.capitalize())
        self.existing_genres[name_lower] = genre
        if created:
            self.stats['genres_created'] += 1
        return genre

    def process_movie(self, movie_data):
        title = movie_data.get('name', '')
        movie_id = movie_data.get('id')
        duration = movie_data.get('movieLength', 0)

        if not title or duration < 60:
            return

        if title in self.existing_movies:
            self.stdout.write(f"  ⏭️ Пропущен (уже есть): {title[:40]}")
            return

        self.stdout.write(f"\n  🎬 {title[:50]}")
        self.stdout.write(f"     ID: {movie_id} | Длит.: {duration} мин")

        # Возрастной рейтинг
        age_str = f"{movie_data.get('ageRating', 16)}+"
        age_rating, _ = AgeRating.objects.get_or_create(name=age_str)

        description = movie_data.get('description', '') or movie_data.get('shortDescription', '')
        description = description[:997] + "..." if len(description) > 1000 else description

        movie = Movie.objects.create(
            title=title[:50],
            short_description=description[:197] + "..." if description else '',
            description=description,
            duration=duration,
            release_year=movie_data.get('year', timezone.now().year),
            age_rating=age_rating
        )
        self.stats['movies'] += 1
        self.existing_movies.add(title)
        self.stdout.write(f"     ✅ Создан фильм ID: {movie.id}")

        # Жанры
        for genre_data in movie_data.get('genres', []):
            genre_name = genre_data.get('name')
            if genre_name:
                genre = self.get_or_create_genre(genre_name)
                if genre:
                    MovieGenre.objects.get_or_create(movie=movie, genre=genre)

        # Страны для фильма
        countries_data = movie_data.get('countries', [])
        if countries_data:
            for country_data in countries_data:
                country_name = country_data.get('name')
                if country_name:
                    country = self.get_or_create_country(country_name)
                    if country:
                        MovieCountry.objects.get_or_create(movie=movie, country=country)
                        self.stats['countries_linked'] += 1

        # ========== АКТЁРЫ ==========
        actors_added = 0
        actors_with_birthdate = 0
        actors_with_country = 0
        actors_data = movie_data.get('persons', [])

        for person in actors_data:
            profession = person.get('profession', '').lower()
            if 'акт' in profession or 'actor' in profession:
                person_name = person.get('name', '')
                person_id = person.get('id')
                if not person_name:
                    continue

                # Получаем детали персоны
                birth_date = None
                country = None

                if person_id:
                    details = self.fetch_person_details(person_id)
                    if details:
                        # Дата рождения
                        birthday = details.get('birthday')
                        if birthday:
                            try:
                                birth_date = datetime.strptime(birthday, '%Y-%m-%d').date()
                                actors_with_birthdate += 1
                            except (ValueError, TypeError):
                                pass

                        # Страна из места рождения
                        birth_places = details.get('birthPlace', [])
                        if birth_places:
                            place_value = birth_places[0].get('value', '') if isinstance(birth_places, list) else ''
                            if place_value:
                                country = self.extract_country_from_text(place_value)
                                if country:
                                    actors_with_country += 1

                name_parts = person_name.split(' ', 1)
                first_name = name_parts[0][:20] if name_parts else ""
                last_name = name_parts[1][:20] if len(name_parts) > 1 else ""

                # Создаём или обновляем актёра
                actor, created = Actor.objects.get_or_create(
                    name=first_name,
                    surname=last_name,
                    defaults={
                        'birth_date': birth_date,
                        'country': country
                    }
                )

                # Обновляем существующего, если нет данных
                if not created:
                    updated = False
                    if birth_date and not actor.birth_date:
                        actor.birth_date = birth_date
                        updated = True
                    if country and not actor.country:
                        actor.country = country
                        updated = True
                    if updated:
                        actor.save()

                if created:
                    self.stats['actors_created'] += 1
                    if self.verbose:
                        date_str = f", р. {birth_date}" if birth_date else ""
                        country_str = f", {country.name}" if country else ""
                        self.stdout.write(f"        → Актёр: {first_name} {last_name}{date_str}{country_str}")

                MovieActor.objects.get_or_create(movie=movie, actor=actor)
                actors_added += 1

        self.stats['actors_linked'] += actors_added
        self.stats['actors_with_birthdate'] += actors_with_birthdate
        self.stats['actors_with_country'] += actors_with_country
        self.stdout.write(f"     🎭 Актёров: {actors_added} (с датами: {actors_with_birthdate}, со странами: {actors_with_country})")

        # ========== РЕЖИССЁРЫ ==========
        directors_data = self.get_movie_directors(movie_id)
        directors_added = 0
        directors_with_birthdate = 0
        directors_with_country = 0

        for person in directors_data:
            person_name = person.get('name', '')
            person_id = person.get('id')
            if not person_name:
                continue

            # Получаем детали персоны
            birth_date = None
            country = None

            if person_id:
                details = self.fetch_person_details(person_id)
                if details:
                    # Дата рождения
                    birthday = details.get('birthday')
                    if birthday:
                        try:
                            birth_date = datetime.strptime(birthday, '%Y-%m-%d').date()
                            directors_with_birthdate += 1
                        except (ValueError, TypeError):
                            pass

                    # Страна из места рождения
                    birth_places = details.get('birthPlace', [])
                    if birth_places:
                        place_value = birth_places[0].get('value', '') if isinstance(birth_places, list) else ''
                        if place_value:
                            country = self.extract_country_from_text(place_value)
                            if country:
                                directors_with_country += 1

            name_parts = person_name.split(' ', 1)
            first_name = name_parts[0][:20] if name_parts else ""
            last_name = name_parts[1][:20] if len(name_parts) > 1 else ""

            # Создаём или обновляем режиссёра
            director, created = Director.objects.get_or_create(
                name=first_name,
                surname=last_name,
                defaults={
                    'birth_date': birth_date,
                    'country': country
                }
            )

            # Обновляем существующего, если нет данных
            if not created:
                updated = False
                if birth_date and not director.birth_date:
                    director.birth_date = birth_date
                    updated = True
                if country and not director.country:
                    director.country = country
                    updated = True
                if updated:
                    director.save()

            if created:
                self.stats['directors_created'] += 1
                if self.verbose:
                    date_str = f", р. {birth_date}" if birth_date else ""
                    country_str = f", {country.name}" if country else ""
                    self.stdout.write(f"        → Режиссёр: {first_name} {last_name}{date_str}{country_str}")

            MovieDirector.objects.get_or_create(movie=movie, director=director)
            directors_added += 1

        self.stats['directors_linked'] += directors_added
        self.stats['directors_with_birthdate'] += directors_with_birthdate
        self.stats['directors_with_country'] += directors_with_country
        self.stdout.write(f"     🎬 Режиссёров: {directors_added} (с датами: {directors_with_birthdate}, со странами: {directors_with_country})")

        # Постер
        poster_url = movie_data.get('poster', {}).get('url') or movie_data.get('poster', {}).get('previewUrl')
        if poster_url:
            try:
                content = self.client.download_image(poster_url)
                if content:
                    safe_title = re.sub(r'[^\w\s-]', '', title)[:50].strip()
                    movie.poster.save(f"{safe_title}.jpg", ContentFile(content), save=True)
                    self.stats['posters'] += 1
                    self.stdout.write(f"     🖼️ Постер скачан")
            except Exception as e:
                if self.verbose:
                    self.stdout.write(f"     ⚠️ Ошибка постера: {e}")

        self.stdout.write(f"     ✅ Импорт завершён")

    def print_stats(self):
        self.stdout.write(self.style.SUCCESS('\n' + '=' * 60))
        self.stdout.write(self.style.SUCCESS('📊 ИТОГИ ИМПОРТА'))
        self.stdout.write('=' * 60)
        self.stdout.write(f"   🎬 Фильмов: {self.stats['movies']}")
        self.stdout.write(f"   🌍 Стран создано: {self.stats['countries_created']}")
        self.stdout.write(f"   🔗 Связей Movie-Страна: {self.stats['countries_linked']}")
        self.stdout.write(f"   🎭 Жанров: {self.stats['genres_created']}")
        self.stdout.write(f"   🎬 Режиссёров: {self.stats['directors_created']} (связей: {self.stats['directors_linked']})")
        self.stdout.write(f"      - с датами: {self.stats['directors_with_birthdate']}")
        self.stdout.write(f"      - со странами: {self.stats['directors_with_country']}")
        self.stdout.write(f"   🎭 Актёров: {self.stats['actors_created']} (связей: {self.stats['actors_linked']})")
        self.stdout.write(f"      - с датами: {self.stats['actors_with_birthdate']}")
        self.stdout.write(f"      - со странами: {self.stats['actors_with_country']}")
        self.stdout.write(f"   🖼️ Постеров: {self.stats['posters']}")
        self.stdout.write(f"   🔌 API запросов: {self.stats['api_requests']}")
        self.stdout.write('=' * 60)

    def show_summary(self):
        self.stdout.write(self.style.SUCCESS(f"\n📽️ ФИЛЬМЫ В БД:"))
        for movie in Movie.objects.all().order_by('-id')[:10]:
            directors = ', '.join(f"{d.surname} {d.name}" for d in movie.directors.all()[:3])
            self.stdout.write(f"   • {movie.title[:40]}")
            self.stdout.write(f"     Режиссёры: {directors or '—'}")

        self.stdout.write(self.style.SUCCESS(f"\n👤 РЕЖИССЁРЫ С ДАННЫМИ:"))
        directors_with_data = Director.objects.filter(birth_date__isnull=False)[:15]
        if directors_with_data:
            for director in directors_with_data:
                country = director.country.name if director.country else '—'
                self.stdout.write(f"   • {director.surname} {director.name} — {director.birth_date} ({country})")
        else:
            self.stdout.write(f"   (нет режиссёров с заполненными данными)")

        self.stdout.write(self.style.SUCCESS(f"\n🎭 АКТЁРЫ С ДАННЫМИ:"))
        actors_with_data = Actor.objects.filter(birth_date__isnull=False)[:15]
        if actors_with_data:
            for actor in actors_with_data:
                country = actor.country.name if actor.country else '—'
                self.stdout.write(f"   • {actor.surname} {actor.name} — {actor.birth_date} ({country})")
        else:
            self.stdout.write(f"   (нет актёров с заполненными данными)")