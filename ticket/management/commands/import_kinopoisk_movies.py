# ticket/management/commands/import_kinopoisk_movies.py

import requests
from django.core.management.base import BaseCommand
from django.conf import settings
from django.db import IntegrityError, DataError
from django.utils import timezone
from django.core.files.base import ContentFile
from datetime import datetime, timedelta, date
import random
import logging
import time
import os
from io import BytesIO
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from ticket.models import (
    Movie, Genre, AgeRating, Director, Actor, Country,
    MovieDirector, MovieActor, Hall, Screening, HallType
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Импорт полнометражных фильмов из API Poiskkino.dev с созданием сеансов'

    def add_arguments(self, parser):
        parser.add_argument(
            '--pages',
            type=int,
            default=3,
            help='Количество страниц для импорта (по 50 фильмов на странице)'
        )
        parser.add_argument(
            '--min-duration',
            type=int,
            default=80,
            help='Минимальная длительность фильма в минутах'
        )
        parser.add_argument(
            '--create-screenings',
            action='store_true',
            default=True,
            help='Создавать сеансы для импортированных фильмов'
        )
        parser.add_argument(
            '--screening-days',
            type=int,
            default=30,
            help='На сколько дней вперёд создавать сеансы'
        )
        parser.add_argument(
            '--min-screenings-per-day',
            type=int,
            default=3,
            help='Минимум сеансов в день'
        )
        parser.add_argument(
            '--max-screenings-per-day',
            type=int,
            default=5,
            help='Максимум сеансов в день'
        )
        parser.add_argument(
            '--download-posters',
            action='store_true',
            default=True,
            help='Скачивать постеры фильмов'
        )
        parser.add_argument(
            '--update-existing',
            action='store_true',
            default=True,
            help='Обновлять существующие фильмы'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Подробный вывод для отладки'
        )
        parser.add_argument(
            '--quiet',
            action='store_true',
            help='Скрыть предупреждения'
        )
        parser.add_argument(
            '--skip-person-details',
            action='store_true',
            default=False,
            help='Пропустить получение детальной информации о персонах'
        )

    def handle(self, *args, **options):
        api_key = getattr(settings, 'KINOPOISK_API_KEY', None)
        if not api_key:
            self.stderr.write(
                self.style.ERROR('ОШИБКА: KINOPOISK_API_KEY не найден в settings.py!')
            )
            return

        self.verbose = options.get('verbose', False)
        self.quiet = options.get('quiet', False)
        self.min_duration = options.get('min_duration', 80)
        self.create_screenings = options.get('create_screenings', True)
        self.screening_days = options.get('screening_days', 30)
        self.min_screenings = options.get('min_screenings_per_day', 3)
        self.max_screenings = options.get('max_screenings_per_day', 5)
        self.download_posters = options.get('download_posters', True)
        self.skip_person_details = options.get('skip_person_details', False)

        if self.skip_person_details:
            self.stdout.write(self.style.WARNING('⚠️ Детальная информация о персонах НЕ будет загружаться'))

        self.stdout.write(self.style.SUCCESS(f'✅ API ключ загружен: {api_key[:5]}...'))

        # Рассчитываем год для фильтра (последний год)
        current_year = datetime.now().year
        last_year = current_year - 1
        self.stdout.write(f'🎬 Импортирую фильмы за {last_year}-{current_year} год')
        self.stdout.write(f'🎬 Только фильмы длиннее {self.min_duration} минут')

        pages = options['pages']

        base_url = "https://api.poiskkino.dev/v1.4"
        headers = {
            "X-API-KEY": api_key,
            "accept": "application/json"
        }

        # Настраиваем сессию с повторными попытками
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        # Приоритеты жанров
        self.genre_priority = [
            'боевик', 'комедия', 'драма', 'фантастика', 'триллер',
            'ужасы', 'мелодрама', 'детектив', 'приключения', 'фэнтези',
            'криминал', 'вестерн', 'военный', 'исторический', 'биография',
            'мультфильм', 'аниме'
        ]

        # Список известных стран (для фильтрации городов)
        self.known_countries = {
            'россия', 'сша', 'великобритания', 'германия', 'франция', 'италия',
            'испания', 'япония', 'китай', 'южная корея', 'канада', 'австралия',
            'индия', 'бразилия', 'мексика', 'украина', 'беларусь', 'казахстан',
            'польша', 'чехия', 'швеция', 'норвегия', 'финляндия', 'дания',
            'нидерланды', 'бельгия', 'швейцария', 'австрия', 'венгрия',
            'румыния', 'болгария', 'сербия', 'хорватия', 'словения',
            'словакия', 'эстония', 'латвия', 'литва', 'грузия', 'армения',
            'азербайджан', 'узбекистан', 'таджикистан', 'туркменистан',
            'кыргызстан', 'молдова', 'турция', 'израиль', 'египет',
            'юар', 'аргентина', 'чили', 'колумбия', 'перу', 'венесуэла'
        }

        # Получаем существующие данные
        existing_genres = {g.name.lower(): g for g in Genre.objects.all()}
        existing_countries = {c.name.lower(): c for c in Country.objects.all()}

        # Создаём жанр "Неизвестно" если его нет
        if 'неизвестно' not in existing_genres:
            unknown_genre, _ = Genre.objects.get_or_create(
                name="Неизвестно",
                defaults={'description': 'Жанр не определен'}
            )
            existing_genres['неизвестно'] = unknown_genre

        self.stdout.write(f"📚 В БД найдено жанров: {len(existing_genres)}")
        self.stdout.write(f"🌍 В БД найдено стран: {len(existing_countries)}")

        # Получаем все залы для создания сеансов
        self.halls = list(Hall.objects.all())
        if not self.halls and self.create_screenings:
            self.stderr.write(self.style.ERROR('❌ Нет залов для создания сеансов!'))
            self.create_screenings = False

        stats = {
            'new': 0,
            'updated': 0,
            'skipped_duration': 0,
            'skipped_other': 0,
            'errors': 0,
            'genres_fixed': 0,
            'descriptions_fixed': 0,
            'posters_added': 0,
            'directors_added': 0,
            'actors_added': 0,
            'screenings_created': 0
        }

        for page in range(1, pages + 1):
            self.stdout.write(f"\n📄 Импорт страницы {page} из {pages}...")

            # Упрощенные параметры запроса
            params = {
                "page": page,
                "limit": 50,
                "sortField": "votes.kp",
                "sortType": "-1",
                "type": "movie",
                "year": f"{last_year}-{current_year}",
                # Убрали selectFields, так как он может вызывать ошибку
            }

            try:
                response = self.session.get(
                    f"{base_url}/movie",
                    headers=headers,
                    params=params,
                    timeout=30
                )

                # Проверяем статус ответа
                if response.status_code == 403:
                    error_data = response.json()
                    self.stderr.write(self.style.ERROR(f'❌ {error_data.get("message", "Ошибка доступа")}'))
                    self.stderr.write(self.style.ERROR('Обновите тариф в боте @poiskkinodev_bot'))
                    break

                response.raise_for_status()
                data = response.json()

                movies = data.get('docs', [])
                if not movies:
                    break

                # Фильтруем по длительности
                long_movies = []
                for m in movies:
                    duration = m.get('movieLength', 0)
                    if duration and duration >= self.min_duration:
                        long_movies.append(m)
                    else:
                        stats['skipped_duration'] += 1

                self.stdout.write(f"  Найдено {len(movies)} фильмов, отобрано {len(long_movies)} полнометражных")

                for movie_data in long_movies:
                    try:
                        result = self.process_movie(
                            movie_data,
                            existing_genres,
                            existing_countries,
                            stats
                        )

                        if result == "new":
                            stats['new'] += 1
                        elif result == "updated":
                            stats['updated'] += 1
                        elif result == "skipped":
                            stats['skipped_other'] += 1
                        elif result == "error":
                            stats['errors'] += 1

                        time.sleep(0.3)

                    except KeyboardInterrupt:
                        self.stdout.write(self.style.WARNING('\n⚠️ Импорт прерван пользователем'))
                        self.print_stats(stats)
                        return
                    except Exception as e:
                        stats['errors'] += 1
                        if self.verbose:
                            self.stderr.write(self.style.ERROR(f'  ❌ Ошибка: {str(e)[:100]}'))

            except KeyboardInterrupt:
                self.stdout.write(self.style.WARNING('\n⚠️ Импорт прерван пользователем'))
                self.print_stats(stats)
                return
            except requests.exceptions.RequestException as e:
                self.stderr.write(self.style.ERROR(f'Ошибка запроса к API: {e}'))
                if hasattr(e.response, 'text'):
                    self.stderr.write(self.style.ERROR(f'Ответ: {e.response.text}'))
                continue

        self.print_stats(stats)

    def print_stats(self, stats):
        """Вывод статистики"""
        self.stdout.write(self.style.SUCCESS(f'\n{"=" * 50}'))
        self.stdout.write(self.style.SUCCESS(f'✅ ИМПОРТ ЗАВЕРШЕН!'))
        self.stdout.write(self.style.SUCCESS(f'📊 Статистика:'))
        self.stdout.write(self.style.SUCCESS(f'   • Новых фильмов: {stats["new"]}'))
        self.stdout.write(self.style.SUCCESS(f'   • Обновлено фильмов: {stats["updated"]}'))
        self.stdout.write(self.style.SUCCESS(f'   • Пропущено (короткие): {stats["skipped_duration"]}'))
        self.stdout.write(self.style.SUCCESS(f'   • Пропущено (другое): {stats["skipped_other"]}'))
        self.stdout.write(self.style.SUCCESS(f'   • Ошибок: {stats["errors"]}'))
        self.stdout.write(self.style.SUCCESS(f'   • Добавлено постеров: {stats["posters_added"]}'))
        self.stdout.write(self.style.SUCCESS(f'   • Добавлено режиссёров: {stats["directors_added"]}'))
        self.stdout.write(self.style.SUCCESS(f'   • Добавлено актёров: {stats["actors_added"]}'))
        if self.create_screenings:
            self.stdout.write(self.style.SUCCESS(f'   • Создано сеансов: {stats["screenings_created"]}'))
        self.stdout.write(self.style.SUCCESS(f'{"=" * 50}'))

    def is_valid_country(self, country_name):
        """Проверка, является ли название страной (не городом/регионом)"""
        if not country_name:
            return False

        country_lower = country_name.lower().strip()

        # Проверяем длину
        if len(country_name) > 30:
            return False

        # Игнорируем слова, указывающие на города/регионы
        ignore_words = ['село', 'поселок', 'деревня', 'город', 'область', 'край', 'район', 'станция']
        for word in ignore_words:
            if word in country_lower:
                return False

        # Проверяем по списку известных стран
        if country_lower in self.known_countries:
            return True

        # Если страна уже существует в БД
        if country_lower in [c.lower() for c in Country.objects.values_list('name', flat=True)]:
            return True

        return False

    def get_or_create_country(self, country_name, existing_countries):
        """Получение или создание страны"""
        if not country_name or not self.is_valid_country(country_name):
            return None

        country_lower = country_name.lower().strip()
        if country_lower in existing_countries:
            return existing_countries[country_lower]

        try:
            # Создаём уникальный код страны
            base_code = country_name[:2].upper()

            # Обработка особых случаев
            special_codes = {
                'сша': 'US',
                'великобритания': 'GB',
                'россия': 'RU',
                'германия': 'DE',
                'франция': 'FR',
                'италия': 'IT',
                'испания': 'ES',
                'япония': 'JP',
                'китай': 'CN',
                'южная корея': 'KR',
                'северная корея': 'KP',
                'юар': 'ZA',
                'оаэ': 'AE',
                'саудовская аравия': 'SA'
            }

            if country_lower in special_codes:
                country_code = special_codes[country_lower]
            else:
                # Проверяем уникальность кода
                country_code = base_code
                counter = 1
                while Country.objects.filter(code=country_code).exists():
                    country_code = f"{base_code}{counter}"
                    counter += 1
                    if counter > 10:
                        country_code = base_code + str(int(time.time()))[:2]
                        break

            country, created = Country.objects.get_or_create(
                name=country_name,
                defaults={'code': country_code}
            )
            existing_countries[country_lower] = country
            if created and self.verbose:
                self.stdout.write(f"     🌍 Создана страна: {country_name} ({country_code})")
            return country
        except Exception as e:
            if self.verbose:
                logger.error(f"Ошибка создания страны {country_name}: {e}")
            return None

    def get_best_genre(self, api_genres, existing_genres):
        """Выбор наилучшего жанра из списка"""
        if not api_genres:
            return existing_genres.get('неизвестно')

        genre_names = []
        for g in api_genres:
            name = g.get('name')
            if name:
                genre_names.append(name.lower())

        if not genre_names:
            return existing_genres.get('неизвестно')

        # Ищем по приоритету
        for priority_genre in self.genre_priority:
            for genre_name in genre_names:
                if priority_genre in genre_name:
                    for db_name, db_genre in existing_genres.items():
                        if priority_genre in db_name:
                            return db_genre

        # Если не нашли, берём первый существующий
        for genre_name in genre_names:
            if genre_name in existing_genres:
                return existing_genres[genre_name]

        # Если ничего не нашли, создаём новый
        for genre_name in genre_names:
            try:
                genre, created = Genre.objects.get_or_create(
                    name=genre_name.capitalize(),
                    defaults={'description': f'Импортировано из API'}
                )
                existing_genres[genre_name] = genre
                return genre
            except Exception:
                continue

        return existing_genres.get('неизвестно')

    def download_poster(self, poster_url, movie_title):
        """Скачивание постера фильма"""
        if not poster_url:
            return None

        try:
            response = self.session.get(poster_url, timeout=20)
            if response.status_code == 200:
                # Создаем безопасное имя файла
                safe_title = ''.join(c for c in movie_title if c.isalnum() or c in (' ', '-', '_')).rstrip()
                safe_title = safe_title[:50]
                filename = f"{safe_title}_{int(time.time())}.jpg"

                return ContentFile(response.content, name=filename)
        except Exception as e:
            logger.error(f"Ошибка скачивания постера для {movie_title}: {e}")

        return None

    def get_person_details(self, person_id, api_key):
        """Получение детальной информации о персоне"""
        if self.skip_person_details:
            return None

        try:
            headers = {"X-API-KEY": api_key}
            url = f"https://api.poiskkino.dev/v1.4/person/{person_id}"

            response = self.session.get(url, headers=headers, timeout=15)
            if response.status_code == 200:
                return response.json()
        except requests.exceptions.Timeout:
            if self.verbose:
                logger.warning(f"Таймаут при получении данных персоны {person_id}")
        except Exception as e:
            if self.verbose:
                logger.error(f"Ошибка получения данных персоны {person_id}: {e}")

        return None

    def import_person(self, person_data, profession_type, existing_countries):
        """Импорт персоны (режиссёра или актёра) с полными данными"""
        try:
            person_name = person_data.get('name')
            person_id = person_data.get('id')

            if not person_name:
                return None

            # Разделяем имя и фамилию
            name_parts = person_name.split(' ', 1)
            first_name = name_parts[0]
            last_name = name_parts[1] if len(name_parts) > 1 else ''

            # Получаем детальную информацию о персоне
            api_key = getattr(settings, 'KINOPOISK_API_KEY', None)
            person_details = None
            birth_date = None
            country = None

            if api_key and person_id and not self.skip_person_details:
                person_details = self.get_person_details(person_id, api_key)

                if person_details:
                    # Получаем дату рождения
                    if person_details.get('birthday'):
                        try:
                            birth_date = datetime.fromisoformat(person_details['birthday'].replace('Z', '+00:00')).date()
                        except:
                            pass

                    # Получаем страну
                    if person_details.get('birthPlace'):
                        for place in person_details['birthPlace']:
                            if place.get('value'):
                                country = self.get_or_create_country(place['value'], existing_countries)
                                if country:
                                    break

            # Базовые данные
            person_data_dict = {
                'biography': f'Импортировано из API, ID: {person_id}'
            }

            if birth_date:
                person_data_dict['birth_date'] = birth_date
            if country:
                person_data_dict['country'] = country

            if profession_type == 'director':
                person, created = Director.objects.get_or_create(
                    name=first_name,
                    surname=last_name,
                    defaults=person_data_dict
                )
                # Обновляем существующего, если есть новые данные
                if not created and (birth_date or country):
                    if birth_date and not person.birth_date:
                        person.birth_date = birth_date
                    if country and not person.country:
                        person.country = country
                    person.save()
                return person, created
            else:
                person, created = Actor.objects.get_or_create(
                    name=first_name,
                    surname=last_name,
                    defaults=person_data_dict
                )
                # Обновляем существующего, если есть новые данные
                if not created and (birth_date or country):
                    if birth_date and not person.birth_date:
                        person.birth_date = birth_date
                    if country and not person.country:
                        person.country = country
                    person.save()
                return person, created

        except Exception as e:
            logger.error(f"Ошибка импорта персоны {person_data.get('name')}: {e}")
            return None

    def update_movie_persons(self, movie, persons_data, existing_countries, stats):
        """Обновление режиссёров и актёров фильма"""
        if not persons_data:
            return 0, 0

        directors_added = 0
        actors_added = 0

        current_directors = set(movie.directors.values_list('id', flat=True))
        current_actors = set(movie.actors.values_list('id', flat=True))

        for person in persons_data:
            try:
                profession = person.get('profession')

                if profession in ['режиссеры', 'director', 'режиссер']:
                    result = self.import_person(person, 'director', existing_countries)
                    if result:
                        director, created = result
                        if director.id not in current_directors:
                            MovieDirector.objects.get_or_create(movie=movie, director=director)
                            directors_added += 1
                            if created and self.verbose:
                                self.stdout.write(f"     ➕ Новый режиссёр: {director.name} {director.surname}")

                elif profession in ['актеры', 'actor', 'актер']:
                    result = self.import_person(person, 'actor', existing_countries)
                    if result:
                        actor, created = result
                        if actor.id not in current_actors:
                            MovieActor.objects.get_or_create(movie=movie, actor=actor)
                            actors_added += 1
                            if created and self.verbose:
                                self.stdout.write(f"     ➕ Новый актёр: {actor.name} {actor.surname}")

            except Exception as e:
                logger.error(f"Ошибка импорта персоны: {e}")
                continue

        stats['directors_added'] += directors_added
        stats['actors_added'] += actors_added

        return directors_added, actors_added

    def process_movie(self, data, existing_genres, existing_countries, stats):
        """Обработка одного фильма"""
        name = data.get('name')
        if not name:
            return "skipped"

        # Проверяем длительность ещё раз
        duration = data.get('movieLength', 0)
        if not duration or duration < self.min_duration:
            return "skipped"

        display_name = name
        if len(name) > 50:
            name = name[:47] + "..."

        # Ищем существующий фильм
        movie = self.find_movie_by_title(name)
        is_new = movie is None

        if is_new:
            movie = self.create_movie(data, name, existing_genres)
            if not movie:
                return "error"

            # Скачиваем постер
            if self.download_posters and data.get('poster', {}).get('url'):
                try:
                    poster_content = self.download_poster(data['poster']['url'], name)
                    if poster_content:
                        movie.poster.save(f"{name[:50]}.jpg", poster_content, save=False)
                        stats['posters_added'] += 1
                except Exception as e:
                    logger.error(f"Ошибка сохранения постера: {e}")

            movie.save()
            status = "new"
            if self.verbose:
                self.stdout.write(f"  🆕 Новый фильм: {display_name} ({duration} мин)")
        else:
            status = "updated"
            if self.verbose:
                self.stdout.write(f"  🔄 Обновление: {display_name}")

        # Обновляем жанр
        if self.update_movie_genre(movie, data.get('genres', []), existing_genres, stats):
            movie.save()

        # Обновляем режиссёров и актёров
        if data.get('persons'):
            self.update_movie_persons(movie, data['persons'], existing_countries, stats)

        # Создаём сеансы для новых фильмов
        if is_new and self.create_screenings and self.halls:
            created = self.create_screenings_for_movie(movie, stats)
            if self.verbose and created > 0:
                self.stdout.write(f"     🎬 Создано сеансов: {created}")

        return status

    def create_screenings_for_movie(self, movie, stats):
        """Создание сеансов для фильма"""
        if not self.halls:
            return 0

        screenings_created = 0
        today = timezone.now().date()

        # Случайное количество дней показа
        days_to_show = random.randint(20, 45)

        # Временные слоты для сеансов
        time_slots = [9, 11, 13, 15, 17, 19, 21]

        for day_offset in range(min(days_to_show, self.screening_days)):
            current_date = today + timedelta(days=day_offset)

            # Случайное количество сеансов в этот день
            daily_screenings = random.randint(self.min_screenings, self.max_screenings)

            # Выбираем случайные временные слоты
            selected_slots = random.sample(time_slots, min(daily_screenings, len(time_slots)))
            selected_slots.sort()

            for hour in selected_slots:
                # Выбираем случайный зал
                hall = random.choice(self.halls)

                # Время начала сеанса
                start_time = timezone.make_aware(
                    datetime.combine(current_date, datetime.min.time().replace(hour=hour))
                )

                # Время окончания
                end_time = start_time + timedelta(minutes=movie.duration + 20)

                # Проверяем, что сеанс заканчивается до 24:00
                if end_time.hour >= 24 or (end_time.hour == 23 and end_time.minute > 30):
                    continue

                # Проверяем, нет ли пересечений
                conflicting = Screening.objects.filter(
                    hall=hall,
                    start_time__lt=end_time,
                    end_time__gt=start_time
                ).exists()

                if not conflicting:
                    try:
                        screening = Screening(
                            movie=movie,
                            hall=hall,
                            start_time=start_time,
                            end_time=end_time,
                            ticket_price=0
                        )
                        screening.save()
                        screenings_created += 1
                    except Exception as e:
                        logger.error(f"Ошибка создания сеанса: {e}")
                        continue

            if day_offset % 7 == 0 and self.verbose:
                self.stdout.write(f"       Создано сеансов на {current_date.strftime('%d.%m')}: {daily_screenings}")

        stats['screenings_created'] += screenings_created
        return screenings_created

    def update_movie_genre(self, movie, api_genres, existing_genres, stats):
        """Обновление жанра фильма"""
        if not api_genres:
            return False

        new_genre = self.get_best_genre(api_genres, existing_genres)

        if not new_genre:
            new_genre = existing_genres.get('неизвестно')

        if not movie.genre or movie.genre.name == "Неизвестно" or movie.genre != new_genre:
            old_genre = movie.genre.name if movie.genre else "None"
            movie.genre = new_genre
            stats['genres_fixed'] += 1
            if self.verbose:
                self.stdout.write(f"     🔄 Жанр: {old_genre} -> {new_genre.name}")
            return True
        return False

    def find_movie_by_title(self, title):
        """Поиск фильма по названию"""
        movie = Movie.objects.filter(title=title).first()
        if movie:
            return movie

        movie = Movie.objects.filter(title__iexact=title).first()
        if movie:
            return movie

        if len(title) > 47 and title.endswith('...'):
            base_title = title[:-3]
            movie = Movie.objects.filter(title__startswith=base_title).first()
            if movie:
                return movie

        return None

    def create_movie(self, data, title, existing_genres):
        """Создание нового фильма"""
        try:
            genre = self.get_best_genre(data.get('genres', []), existing_genres)
            if not genre:
                genre = existing_genres.get('неизвестно')

            age_rating = None
            age_rating_value = data.get('ageRating')
            if age_rating_value:
                age_str = f"{age_rating_value}+"
            else:
                age_str = "16+"

            try:
                age_rating, _ = AgeRating.objects.get_or_create(name=age_str)
            except Exception:
                age_rating = AgeRating.objects.filter(name="16+").first()
                if not age_rating:
                    age_rating = AgeRating.objects.first()

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

            duration = data.get('movieLength', 90)
            year = data.get('year', datetime.now().year)

            movie = Movie(
                title=title,
                short_description=short_description,
                description=description,
                duration=duration,
                release_year=year,
                genre=genre,
                age_rating=age_rating
            )

            return movie

        except Exception as e:
            logger.error(f"Ошибка создания фильма {title}: {e}")
            return None