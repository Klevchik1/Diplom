# ticket/management/commands/import_kinopoisk_movies.py

import requests
from django.core.management.base import BaseCommand
from django.conf import settings
from django.db import IntegrityError, DataError
from ticket.models import Movie, Genre, AgeRating, Director, Actor, Country
from datetime import datetime
import os
from django.core.files import File
from django.core.files.temp import NamedTemporaryFile
import logging
import traceback

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
        parser.add_argument(
            '--skip-existing',
            action='store_true',
            help='Пропускать существующие фильмы (не считать ошибкой)'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Подробный вывод для отладки'
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

        self.verbose = options.get('verbose', False)

        self.stdout.write(self.style.SUCCESS(f'✅ API ключ загружен: {api_key[:5]}...'))
        self.stdout.write('Начинаю импорт фильмов...')

        pages = options['pages']
        year_start = options['year_start']
        download_posters = options['download_posters']
        skip_existing = options['skip_existing']

        # Базовый URL API
        base_url = "https://api.poiskkino.dev/v1.4"
        headers = {
            "X-API-KEY": api_key,
            "accept": "application/json"
        }

        # Получаем все существующие жанры из БД для быстрой проверки
        existing_genres = {g.name: g for g in Genre.objects.all()}
        self.stdout.write(f"📚 В БД найдено жанров: {len(existing_genres)}")

        total_imported = 0
        total_skipped = 0
        total_errors = 0
        total_processed = 0

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
                    total_processed += 1
                    try:
                        result = self.import_movie(
                            movie_data,
                            download_posters,
                            skip_existing,
                            existing_genres
                        )

                        if result == "imported":
                            total_imported += 1
                            name = movie_data.get("name", "Без названия")
                            year = movie_data.get("year", "")
                            self.stdout.write(self.style.SUCCESS(f'  ✅ {name} ({year})'))
                        elif result == "skipped_exists":
                            total_skipped += 1
                            if self.verbose:
                                name = movie_data.get("name", "Без названия")
                                self.stdout.write(self.style.WARNING(f'  ⏭️ {name} (уже есть)'))
                        elif result == "skipped_no_name":
                            total_skipped += 1
                        elif result == "error":
                            total_errors += 1

                    except Exception as e:
                        total_errors += 1
                        error_msg = str(e)[:100]
                        if self.verbose:
                            self.stderr.write(self.style.ERROR(f'  ❌ Ошибка: {error_msg}'))
                            if self.verbose:
                                traceback.print_exc(limit=1)

            except requests.exceptions.RequestException as e:
                self.stderr.write(self.style.ERROR(f'Ошибка запроса к API: {e}'))
                continue

        # Итоговая статистика
        self.stdout.write(self.style.SUCCESS(f'\n{"=" * 50}'))
        self.stdout.write(self.style.SUCCESS(f'✅ ИМПОРТ ЗАВЕРШЕН!'))
        self.stdout.write(self.style.SUCCESS(f'📊 Статистика:'))
        self.stdout.write(self.style.SUCCESS(f'   • Обработано фильмов: {total_processed}'))
        self.stdout.write(self.style.SUCCESS(f'   • Импортировано новых: {total_imported}'))
        self.stdout.write(self.style.SUCCESS(f'   • Пропущено (уже есть): {total_skipped}'))
        self.stdout.write(self.style.SUCCESS(f'   • Ошибок: {total_errors}'))
        self.stdout.write(self.style.SUCCESS(f'{"=" * 50}'))

    def get_or_create_genre_safe(self, genre_name, existing_genres):
        """Безопасное получение или создание жанра без исключений"""
        if not genre_name:
            return None

        # Проверяем в существующих
        if genre_name in existing_genres:
            return existing_genres[genre_name]

        # Пробуем создать
        try:
            genre, created = Genre.objects.get_or_create(
                name=genre_name,
                defaults={'description': f'Импортировано из API'}
            )
            existing_genres[genre_name] = genre
            return genre
        except IntegrityError:
            # Возможно, жанр был создан в другом потоке
            genre = Genre.objects.filter(name=genre_name).first()
            if genre:
                existing_genres[genre_name] = genre
                return genre
        except Exception as e:
            logger.error(f"Ошибка создания жанра {genre_name}: {e}")
            return None

    def import_movie(self, data, download_posters=False, skip_existing=False, existing_genres=None):
        """Импорт одного фильма в базу данных"""

        if existing_genres is None:
            existing_genres = {}

        # Проверяем обязательные поля
        name = data.get('name')
        if not name:
            return "skipped_no_name"

        # Ограничиваем длину названия (ваше поле title = max_length=50)
        original_name = name
        if len(name) > 50:
            name = name[:47] + "..."

        # Проверяем, есть ли уже такой фильм
        if Movie.objects.filter(title=name).exists():
            return "skipped_exists"

        # ПОЛУЧАЕМ ЖАНР - теперь без исключений
        genre = None
        if data.get('genres') and len(data['genres']) > 0:
            genre_name = data['genres'][0].get('name')
            if genre_name:
                genre = self.get_or_create_genre_safe(genre_name, existing_genres)

        if not genre:
            # Жанр по умолчанию
            genre = self.get_or_create_genre_safe("Неизвестно", existing_genres)
            if not genre:
                # Если даже неизвестный жанр не создался, пробуем найти любой
                genre = Genre.objects.first()

        # Получаем возрастной рейтинг
        age_rating = None
        age_rating_value = data.get('ageRating')
        if age_rating_value:
            age_str = f"{age_rating_value}+"
        else:
            age_str = "0+"

        try:
            age_rating, _ = AgeRating.objects.get_or_create(name=age_str)
        except Exception:
            age_rating = AgeRating.objects.filter(name="0+").first()

        # Подготовка описания
        description = data.get('description', '')
        if not description or len(description.strip()) < 10:
            description = data.get('shortDescription', 'Описание отсутствует')
        if len(description) > 1000:
            description = description[:997] + "..."

        short_description = data.get('shortDescription', '')
        if not short_description and description:
            short_description = description[:197] + "..." if len(description) > 200 else description
        if len(short_description) > 200:
            short_description = short_description[:197] + "..."

        # Длительность фильма
        duration = data.get('movieLength', 90)
        if not duration or duration < 1:
            duration = 90

        # Год выпуска
        year = data.get('year', 2024)
        if not year or year < 1900:
            year = 2024

        # Создаем фильм
        try:
            movie = Movie(
                title=name,
                short_description=short_description,
                description=description,
                duration=duration,
                release_year=year,
                genre=genre,
                age_rating=age_rating
            )

            # Если нужно скачать постер
            if download_posters and data.get('poster') and data['poster'].get('url'):
                poster_url = data['poster']['url']
                if poster_url and not poster_url.endswith('null'):
                    try:
                        self.download_poster(movie, poster_url, original_name)
                    except Exception as e:
                        logger.error(f"Не удалось скачать постер для {name}: {e}")

            movie.save()

            # Импортируем страны (опционально)
            if data.get('countries'):
                for country_data in data['countries']:
                    country_name = country_data.get('name')
                    if country_name and len(country_name) < 20:
                        try:
                            Country.objects.get_or_create(
                                name=country_name,
                                defaults={'code': country_name[:2].upper()}
                            )
                        except Exception:
                            pass

            return "imported"

        except DataError as e:
            if "value too long" in str(e):
                logger.error(f"Слишком длинное значение для {name}: {e}")
            return "error"
        except IntegrityError as e:
            if "already exists" in str(e):
                return "skipped_exists"
            logger.error(f"Ошибка целостности для {name}: {e}")
            return "error"
        except Exception as e:
            logger.error(f"Неизвестная ошибка для {name}: {e}")
            return "error"

    def download_poster(self, movie, poster_url, movie_name):
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

            # Создаем безопасное имя файла
            safe_name = "".join(c for c in movie_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
            safe_name = safe_name.replace(' ', '_')[:50]
            filename = f"{safe_name}.{ext}"

            movie.poster.save(filename, ContentFile(response.content), save=False)

        except Exception as e:
            logger.error(f"Ошибка скачивания постера: {e}")
            raise