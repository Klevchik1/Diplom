# ticket/management/commands/import_kinopoisk_movies.py
# ПОЛНАЯ ВЕРСИЯ С ЗАПРОСОМ ДЕТАЛЕЙ ФИЛЬМА

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
    help = 'Импорт фильмов из API Poiskkino.dev с автоматическим обновлением'

    def add_arguments(self, parser):
        parser.add_argument('--pages', type=int, default=2)
        parser.add_argument('--min-duration', type=int, default=60)
        parser.add_argument('--no-screenings', action='store_true', default=False)
        parser.add_argument('--screening-days', type=int, default=30)
        parser.add_argument('--verbose', action='store_true')
        parser.add_argument('--quiet', action='store_true')
        parser.add_argument('--force-update', action='store_true')
        parser.add_argument('--skip-persons', action='store_true', default=False,
                            help='Пропустить загрузку персон (для ускорения)')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.person_cache = {}
        self.session = None
        self.existing_countries = {}
        self.existing_directors = {}
        self.existing_actors = {}

        # Список известных стран (только на русском)
        self.known_countries = {
            'россия': 'RU', 'сша': 'US', 'великобритания': 'GB',
            'германия': 'DE', 'франция': 'FR', 'италия': 'IT',
            'испания': 'ES', 'япония': 'JP', 'китай': 'CN',
            'южная корея': 'KR', 'канада': 'CA', 'австралия': 'AU',
            'индия': 'IN', 'бразилия': 'BR', 'мексика': 'MX',
            'украина': 'UA', 'беларусь': 'BY', 'казахстан': 'KZ',
            'польша': 'PL', 'чехия': 'CZ', 'швеция': 'SE',
            'норвегия': 'NO', 'финляндия': 'FI', 'дания': 'DK',
            'нидерланды': 'NL', 'бельгия': 'BE', 'швейцария': 'CH',
            'австрия': 'AT', 'венгрия': 'HU', 'румыния': 'RO',
            'болгария': 'BG', 'сербия': 'RS', 'хорватия': 'HR',
            'словения': 'SI', 'словакия': 'SK', 'эстония': 'EE',
            'латвия': 'LV', 'литва': 'LT', 'грузия': 'GE',
            'армения': 'AM', 'азербайджан': 'AZ', 'узбекистан': 'UZ',
            'таджикистан': 'TJ', 'туркменистан': 'TM', 'кыргызстан': 'KG',
            'молдова': 'MD', 'турция': 'TR', 'израиль': 'IL',
            'египет': 'EG', 'юар': 'ZA', 'аргентина': 'AR',
            'чили': 'CL', 'колумбия': 'CO', 'перу': 'PE',
            'венесуэла': 'VE', 'португалия': 'PT', 'греция': 'GR',
            'ирландия': 'IE', 'исландия': 'IS', 'иран': 'IR',
            'ирак': 'IQ', 'сирия': 'SY', 'ливан': 'LB',
            'иордания': 'JO', 'саудовская аравия': 'SA', 'оаэ': 'AE',
            'катар': 'QA', 'кувейт': 'KW', 'оман': 'OM',
            'йемен': 'YE', 'пакистан': 'PK', 'афганистан': 'AF',
            'монголия': 'MN', 'северная корея': 'KP', 'вьетнам': 'VN',
            'таиланд': 'TH', 'малайзия': 'MY', 'индонезия': 'ID',
            'филиппины': 'PH', 'сингапур': 'SG', 'новая зеландия': 'NZ',
            'марокко': 'MA', 'алжир': 'DZ', 'тунис': 'TN',
            'ливия': 'LY', 'судан': 'SD', 'эфиопия': 'ET',
            'кения': 'KE', 'нигерия': 'NG', 'гана': 'GH',
            'ангола': 'AO', 'конго': 'CG', 'танзания': 'TZ',
            'куба': 'CU', 'ямайка': 'JM', 'панама': 'PA',
            'коста-рика': 'CR', 'гватемала': 'GT', 'гондурас': 'HN',
            'сальвадор': 'SV', 'никарагуа': 'NI', 'боливия': 'BO',
            'парагвай': 'PY', 'уругвай': 'UY', 'эквадор': 'EC',
        }

        # Города и регионы, которые НЕ являются странами
        self.non_countries = {
            'лос-анджелес', 'лос анджелес', 'нижний новгород', 'реутов', 'ереван',
            'москва', 'переславль-залесский', 'бжег', 'таганрог', 'херсон',
            'волжский', 'париж', 'кировск', 'бийск', 'новгород', 'красногорск',
            'хабаровск', 'кутулик', 'тула', 'санкт-петербург', 'ленинград',
            'соликамск', 'каневская', 'клин', 'села', 'ширбрук', 'виргиния',
            'тегеран', 'юнион', 'констанц', 'кент', 'хьюстон', 'манчестер',
            'торонто', 'сидней', 'шампейн', 'розуэлл', 'лилль', 'бакэу',
            'квебек', 'рим', 'труа', 'авиньон', 'нью-йорк', 'ростов',
            'казань', 'новосибирск', 'екатеринбург', 'омск', 'самара', 'уфа',
            'красноярск', 'воронеж', 'пермь', 'волгоград', 'саратов',
            'тюмень', 'ижевск', 'барнаул', 'иркутск', 'ульяновск',
            'владивосток', 'ярославль', 'махачкала', 'томск', 'оренбург',
            'кемерово', 'новокузнецк', 'рязань', 'астрахань', 'пенза',
            'липецк', 'киров', 'чебоксары', 'калининград', 'брянск',
            'иваново', 'магнитогорск', 'курск', 'тверь', 'нижний тагил',
            'ставрополь', 'архангельск', 'белгород', 'сочи', 'севастополь',
            'симферополь', 'лондон', 'берлин', 'мадрид', 'пекин', 'токио',
            'сеул', 'дели', 'каир', 'лагос', 'мехико', 'сан-паулу',
            'буэнос-айрес', 'рио-де-жанейро', 'дубай', 'стамбул', 'бангкок',
        }

    def handle(self, *args, **options):
        api_key = getattr(settings, 'KINOPOISK_API_KEY', None)
        if not api_key:
            self.stderr.write(self.style.ERROR('ОШИБКА: KINOPOISK_API_KEY не найден!'))
            return

        self.verbose = options.get('verbose', False)
        self.quiet = options.get('quiet', False)
        self.min_duration = options.get('min_duration', 60)
        self.create_screenings = not options.get('no_screenings', False)
        self.screening_days = options.get('screening_days', 30)
        self.force_update = options.get('force_update', False)
        self.skip_persons = options.get('skip_persons', False)

        self.download_posters = True
        self.min_screenings = 3
        self.max_screenings = 5

        if self.skip_persons:
            self.stdout.write(self.style.WARNING('⚠️ Загрузка персон ОТКЛЮЧЕНА'))

        # Загружаем существующие данные
        self.existing_countries = {c.name.lower(): c for c in Country.objects.all()}
        self.existing_directors = {f"{d.name.lower()} {d.surname.lower()}": d for d in Director.objects.all()}
        self.existing_actors = {f"{a.name.lower()} {a.surname.lower()}": a for a in Actor.objects.all()}

        # Настраиваем сессию
        self.session = requests.Session()
        retry_strategy = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        self.stdout.write(self.style.SUCCESS('🎬 ИМПОРТ ФИЛЬМОВ ИЗ POISKKINO.DEV'))
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(f'📚 Стран в БД: {len(self.existing_countries)}')
        self.stdout.write(f'👤 Режиссёров в БД: {len(self.existing_directors)}')
        self.stdout.write(f'🎭 Актёров в БД: {len(self.existing_actors)}')
        self.stdout.write(self.style.SUCCESS('=' * 60))

        current_year = datetime.now().year
        start_year = current_year - 2
        self.stdout.write(f'🎯 Импорт фильмов за {start_year}-{current_year} гг.')

        pages = options['pages']

        self.genre_priority = [
            'боевик', 'комедия', 'драма', 'фантастика', 'триллер',
            'ужасы', 'мелодрама', 'детектив', 'приключения', 'фэнтези',
            'криминал', 'вестерн', 'военный', 'исторический', 'биография',
            'мультфильм', 'аниме'
        ]

        existing_genres = {g.name.lower(): g for g in Genre.objects.all()}
        if 'неизвестно' not in existing_genres:
            unknown_genre, _ = Genre.objects.get_or_create(
                name="Неизвестно", defaults={'description': 'Жанр не определен'}
            )
            existing_genres['неизвестно'] = unknown_genre

        self.halls = list(Hall.objects.all())
        if not self.halls and self.create_screenings:
            self.stderr.write(self.style.WARNING('⚠️ Нет залов для создания сеансов!'))
            self.create_screenings = False

        stats = {
            'movies_new': 0, 'movies_updated': 0,
            'posters_added': 0, 'posters_updated': 0,
            'directors_created': 0, 'directors_updated': 0,
            'actors_created': 0, 'actors_updated': 0,
            'countries_created': 0,
            'movie_directors_added': 0, 'movie_actors_added': 0,
            'screenings_created': 0,
            'skipped': 0, 'errors': 0
        }

        base_url = "https://api.poiskkino.dev/v1.4"
        headers = {"X-API-KEY": api_key, "accept": "application/json"}

        for page in range(1, pages + 1):
            if not self.quiet:
                self.stdout.write(f"\n📄 Страница {page} из {pages}...")

            params = {
                "page": page, "limit": 50,
                "sortField": "votes.kp", "sortType": "-1",
                "type": "movie", "year": f"{start_year}-{current_year}",
            }

            try:
                response = self.session.get(f"{base_url}/movie", headers=headers, params=params, timeout=30)
                if response.status_code != 200:
                    self.stderr.write(self.style.ERROR(f'❌ Ошибка API: {response.status_code}'))
                    continue

                data = response.json()
                movies = data.get('docs', [])
                if not movies:
                    break

                long_movies = [m for m in movies if m.get('movieLength', 0) >= self.min_duration]
                if not self.quiet:
                    self.stdout.write(f"  📊 Найдено {len(movies)} фильмов, отобрано {len(long_movies)}")

                for movie_data in long_movies:
                    try:
                        result = self.process_movie(movie_data, existing_genres, headers, stats)
                        if result == "new":
                            stats['movies_new'] += 1
                        elif result == "updated":
                            stats['movies_updated'] += 1
                        elif result == "skipped":
                            stats['skipped'] += 1
                        elif result == "error":
                            stats['errors'] += 1
                        time.sleep(0.3)  # Пауза между фильмами
                    except KeyboardInterrupt:
                        self.stdout.write(self.style.WARNING('\n⚠️ Импорт прерван'))
                        self.print_stats(stats)
                        return
                    except Exception as e:
                        stats['errors'] += 1
                        if self.verbose:
                            self.stderr.write(self.style.ERROR(f'  ❌ Ошибка: {str(e)[:100]}'))

            except KeyboardInterrupt:
                self.stdout.write(self.style.WARNING('\n⚠️ Импорт прерван'))
                self.print_stats(stats)
                return
            except Exception as e:
                self.stderr.write(self.style.ERROR(f'Ошибка на странице {page}: {e}'))
                continue

        self.print_stats(stats)

    def print_stats(self, stats):
        self.stdout.write(self.style.SUCCESS(f'\n{"=" * 60}'))
        self.stdout.write(self.style.SUCCESS(f'✅ ИМПОРТ ЗАВЕРШЕН!'))
        self.stdout.write(self.style.SUCCESS(f'{"=" * 60}'))
        self.stdout.write(self.style.SUCCESS(f'📊 СТАТИСТИКА ПО ФИЛЬМАМ:'))
        self.stdout.write(f'   • Новых фильмов: {stats["movies_new"]}')
        self.stdout.write(f'   • Обновлено фильмов: {stats["movies_updated"]}')
        self.stdout.write(f'   • Постеров добавлено: {stats["posters_added"]}')
        self.stdout.write(f'   • Постеров обновлено: {stats["posters_updated"]}')
        self.stdout.write(self.style.SUCCESS(f'\n👥 СТАТИСТИКА ПО ПЕРСОНАМ:'))
        self.stdout.write(f'   • Стран создано: {stats["countries_created"]}')
        self.stdout.write(f'   • Режиссёров создано: {stats["directors_created"]}')
        self.stdout.write(f'   • Режиссёров обновлено: {stats["directors_updated"]}')
        self.stdout.write(f'   • Актёров создано: {stats["actors_created"]}')
        self.stdout.write(f'   • Актёров обновлено: {stats["actors_updated"]}')
        self.stdout.write(self.style.SUCCESS(f'\n🔗 СТАТИСТИКА ПО СВЯЗЯМ:'))
        self.stdout.write(f'   • Связей фильм-режиссёр: {stats["movie_directors_added"]}')
        self.stdout.write(f'   • Связей фильм-актёр: {stats["movie_actors_added"]}')
        if self.create_screenings:
            self.stdout.write(self.style.SUCCESS(f'\n🎬 СЕАНСЫ:'))
            self.stdout.write(f'   • Сеансов создано: {stats["screenings_created"]}')
        if stats['skipped'] > 0:
            self.stdout.write(self.style.WARNING(f'\n⚠️ Пропущено фильмов: {stats["skipped"]}'))
        if stats['errors'] > 0:
            self.stdout.write(self.style.ERROR(f'\n❌ Ошибок: {stats["errors"]}'))
        self.stdout.write(self.style.SUCCESS(f'{"=" * 60}'))

    def get_movie_details(self, movie_id, headers):
        """Получение полной информации о фильме включая персон"""
        if not movie_id:
            return None
        try:
            response = self.session.get(
                f"https://api.poiskkino.dev/v1.4/movie/{movie_id}",
                headers=headers, timeout=15
            )
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            if self.verbose:
                logger.warning(f"Ошибка получения деталей фильма {movie_id}: {e}")
        return None

    def get_or_create_country(self, country_name):
        """Получение или создание ТОЛЬКО страны (не города) и только на русском"""
        if not country_name:
            return None, False

        country_lower = country_name.lower().strip()

        # Проверяем кэш
        if country_lower in self.existing_countries:
            return self.existing_countries[country_lower], False

        # Игнорируем если название содержит латиницу (английский)
        if re.search(r'[a-zA-Z]', country_name):
            return None, False

        # Проверяем, не является ли это городом
        for city in self.non_countries:
            if city in country_lower:
                return None, False

        # Дополнительные проверки на регионы
        if any(word in country_lower for word in ['область', 'край', 'республика', 'округ', 'район']):
            return None, False

        # Проверяем длину названия (страны обычно короче 20 символов)
        if len(country_name) > 20:
            return None, False

        # Ищем страну в списке известных
        found_country = None
        for country_ru in self.known_countries:
            if country_ru in country_lower:
                found_country = country_ru
                break

        if not found_country:
            return None, False

        try:
            country_code = self.known_countries[found_country]

            # Приводим имя к правильному регистру
            display_name = found_country.capitalize()

            country, created = Country.objects.get_or_create(
                name=display_name,
                defaults={'code': country_code}
            )

            self.existing_countries[found_country] = country

            if created and self.verbose:
                self.stdout.write(f"     🌍 Новая страна: {display_name} ({country_code})")

            return country, created
        except Exception as e:
            logger.error(f"Ошибка создания страны {found_country}: {e}")
            return None, False

    def get_person_details(self, person_id, headers):
        if person_id in self.person_cache:
            return self.person_cache[person_id]
        try:
            response = self.session.get(
                f"https://api.poiskkino.dev/v1.4/person/{person_id}",
                headers=headers, timeout=15
            )
            if response.status_code == 200:
                person_data = response.json()
                self.person_cache[person_id] = person_data
                return person_data
        except Exception as e:
            if self.verbose:
                logger.warning(f"Ошибка получения данных персоны {person_id}: {e}")
        return None

    def import_person(self, person_data, profession_type, headers, stats):
        try:
            person_name = person_data.get('name')
            person_id = person_data.get('id')
            if not person_name:
                return None

            name_parts = person_name.split(' ', 1)
            first_name = name_parts[0][:20] if name_parts[0] else ""
            last_name = name_parts[1][:20] if len(name_parts) > 1 else ""
            full_name_key = f"{first_name.lower()} {last_name.lower()}"

            if profession_type == 'director':
                if full_name_key in self.existing_directors:
                    return self.existing_directors[full_name_key]
            else:
                if full_name_key in self.existing_actors:
                    return self.existing_actors[full_name_key]

            person_details = self.get_person_details(person_id, headers) if person_id else None
            birth_date = None
            country = None
            birth_place_str = None

            if person_details:
                if person_details.get('birthday'):
                    try:
                        birth_date_str = person_details['birthday']
                        if 'T' in birth_date_str:
                            birth_date = datetime.fromisoformat(birth_date_str.replace('Z', '+00:00')).date()
                        else:
                            birth_date = datetime.strptime(birth_date_str, '%Y-%m-%d').date()
                    except Exception:
                        pass
                if person_details.get('birthPlace'):
                    for place in person_details['birthPlace']:
                        if place.get('value'):
                            birth_place_str = place['value']
                            country_obj, created = self.get_or_create_country(birth_place_str)
                            if country_obj:
                                country = country_obj
                                if created:
                                    stats['countries_created'] += 1
                                break

            if profession_type == 'director':
                person, created = Director.objects.get_or_create(
                    name=first_name, surname=last_name,
                    defaults={'birth_date': birth_date, 'country': country, 'biography': f'Импортировано из API, ID: {person_id}'}
                )
                if not created:
                    updated = False
                    if birth_date and not person.birth_date:
                        person.birth_date = birth_date
                        updated = True
                    if country and not person.country:
                        person.country = country
                        updated = True
                    if updated:
                        person.save()
                        stats['directors_updated'] += 1
                else:
                    stats['directors_created'] += 1
                    if self.verbose:
                        details = []
                        if birth_date: details.append(f"род. {birth_date.strftime('%d.%m.%Y')}")
                        if birth_place_str: details.append(birth_place_str)
                        details_str = f" ({', '.join(details)})" if details else ""
                        self.stdout.write(f"     👤 Новый режиссёр: {first_name} {last_name}{details_str}")
                self.existing_directors[full_name_key] = person
            else:
                person, created = Actor.objects.get_or_create(
                    name=first_name, surname=last_name,
                    defaults={'birth_date': birth_date, 'country': country, 'biography': f'Импортировано из API, ID: {person_id}'}
                )
                if not created:
                    updated = False
                    if birth_date and not person.birth_date:
                        person.birth_date = birth_date
                        updated = True
                    if country and not person.country:
                        person.country = country
                        updated = True
                    if updated:
                        person.save()
                        stats['actors_updated'] += 1
                else:
                    stats['actors_created'] += 1
                    if self.verbose:
                        details = []
                        if birth_date: details.append(f"род. {birth_date.strftime('%d.%m.%Y')}")
                        if birth_place_str: details.append(birth_place_str)
                        details_str = f" ({', '.join(details)})" if details else ""
                        self.stdout.write(f"     👤 Новый актёр: {first_name} {last_name}{details_str}")
                self.existing_actors[full_name_key] = person
            return person
        except Exception as e:
            logger.error(f"Ошибка импорта персоны {person_data.get('name')}: {e}")
            return None

    def update_movie_persons(self, movie, persons_data, headers, stats):
        if not persons_data:
            return
        current_director_ids = set(movie.directors.values_list('id', flat=True))
        current_actor_ids = set(movie.actors.values_list('id', flat=True))
        directors_processed = 0
        actors_processed = 0

        for person in persons_data:
            try:
                profession = person.get('profession', '').lower()
                if profession in ['режиссеры', 'director', 'режиссер', 'режиссёр']:
                    person_obj = self.import_person(person, 'director', headers, stats)
                    if person_obj and person_obj.id not in current_director_ids:
                        MovieDirector.objects.get_or_create(movie=movie, director=person_obj)
                        stats['movie_directors_added'] += 1
                        directors_processed += 1
                elif profession in ['актеры', 'actor', 'актер', 'актёр']:
                    person_obj = self.import_person(person, 'actor', headers, stats)
                    if person_obj and person_obj.id not in current_actor_ids:
                        MovieActor.objects.get_or_create(movie=movie, actor=person_obj)
                        stats['movie_actors_added'] += 1
                        actors_processed += 1
            except Exception as e:
                logger.error(f"Ошибка обработки персоны {person.get('name')}: {e}")
                continue

    def get_genres(self, api_genres, existing_genres):
        """Получить список жанров из API"""
        if not api_genres:
            unknown = existing_genres.get('неизвестно')
            return [unknown] if unknown else []

        result = []
        genre_names = [g.get('name', '').lower() for g in api_genres if g.get('name')]

        for genre_name in genre_names:
            # Ищем существующий жанр по приоритету
            found = None
            for priority_genre in self.genre_priority:
                if priority_genre in genre_name:
                    for db_name, db_genre in existing_genres.items():
                        if priority_genre in db_name:
                            found = db_genre
                            break
                    if found:
                        break

            # Если не нашли по приоритету, ищем точное совпадение
            if not found:
                if genre_name in existing_genres:
                    found = existing_genres[genre_name]

            # Если всё ещё не нашли, создаём новый
            if not found:
                try:
                    found, created = Genre.objects.get_or_create(
                        name=genre_name.capitalize(),
                        defaults={'description': f'Импортировано из API'}
                    )
                    existing_genres[genre_name] = found
                except Exception:
                    continue

            if found and found not in result:
                result.append(found)

        if not result:
            unknown = existing_genres.get('неизвестно')
            if unknown:
                result.append(unknown)

        return result

    def download_poster(self, poster_url, movie_title):
        if not poster_url:
            return None
        try:
            response = self.session.get(poster_url, timeout=20)
            if response.status_code == 200:
                safe_title = re.sub(r'[^\w\s-]', '', movie_title)[:50].strip()
                filename = f"{safe_title}_{int(time.time())}.jpg"
                return ContentFile(response.content, name=filename)
        except Exception as e:
            logger.error(f"Ошибка скачивания постера для {movie_title}: {e}")
        return None

    def find_movie_by_title(self, title):
        movie = Movie.objects.filter(title=title).first()
        if movie: return movie
        movie = Movie.objects.filter(title__iexact=title).first()
        if movie: return movie
        if len(title) > 47 and title.endswith('...'):
            movie = Movie.objects.filter(title__startswith=title[:-3]).first()
        return movie

    def create_movie(self, data, title, existing_genres):
        try:
            age_str = f"{data.get('ageRating', 16)}+"
            try:
                age_rating, _ = AgeRating.objects.get_or_create(name=age_str)
            except Exception:
                age_rating = AgeRating.objects.filter(name="16+").first() or AgeRating.objects.first()
            description = data.get('description', '')
            if not description or len(description.strip()) < 10:
                description = data.get('shortDescription', 'Описание отсутствует')
            description = description[:997] + "..." if len(description) > 1000 else description
            short_description = data.get('shortDescription', '')
            if not short_description and description:
                short_description = description[:197] + "..." if len(description) > 200 else description
            short_description = short_description[:197] + "..." if len(short_description) > 200 else short_description
            movie = Movie(
                title=title,
                short_description=short_description,
                description=description,
                duration=data.get('movieLength', 90),
                release_year=data.get('year', datetime.now().year),
                age_rating=age_rating
            )
            movie.save()

            # Добавляем жанры после сохранения
            genres = self.get_genres(data.get('genres', []), existing_genres)
            for genre in genres:
                MovieGenre.objects.get_or_create(movie=movie, genre=genre)

            return movie
        except Exception as e:
            logger.error(f"Ошибка создания фильма {title}: {e}")
            return None

    def process_movie(self, data, existing_genres, headers, stats):
        name = data.get('name')
        movie_id = data.get('id')
        if not name:
            return "skipped"
        duration = data.get('movieLength', 0)
        if duration < self.min_duration:
            return "skipped"
        display_name = name
        if len(name) > 50:
            name = name[:47] + "..."

        # ВАЖНО: Получаем полные данные о фильме
        full_movie_data = data
        if movie_id and not self.skip_persons:
            details = self.get_movie_details(movie_id, headers)
            if details:
                full_movie_data = details
                if self.verbose:
                    persons_count = len(details.get('persons', []))
                    if persons_count > 0:
                        self.stdout.write(f"     📋 Получены полные данные: {persons_count} персон")
            elif self.verbose:
                self.stdout.write(f"     ⚠️ Не удалось получить полные данные")

        movie = self.find_movie_by_title(name)
        is_new = movie is None

        if is_new:
            movie = self.create_movie(full_movie_data, name, existing_genres)
            if not movie: return "error"
            movie.save()
            status = "new"
        else:
            status = "updated"
            if self.force_update or not movie.description or movie.description == 'Описание отсутствует':
                desc = full_movie_data.get('description', '')
                if desc and len(desc) > 10:
                    movie.description = desc[:997] + "..." if len(desc) > 1000 else desc
                    movie.short_description = desc[:197] + "..." if len(desc) > 200 else desc
                    movie.save()

        # Постер
        poster_url = None
        poster_data = full_movie_data.get('poster', {})
        if isinstance(poster_data, dict):
            poster_url = poster_data.get('url') or poster_data.get('previewUrl')
        elif isinstance(poster_data, str):
            poster_url = poster_data
        if poster_url and (is_new or not movie.poster or self.force_update):
            try:
                poster_content = self.download_poster(poster_url, display_name)
                if poster_content:
                    safe_title = re.sub(r'[^\w\s-]', '', display_name)[:50].strip()
                    movie.poster.save(f"{safe_title}.jpg", poster_content, save=True)
                    if is_new:
                        stats['posters_added'] += 1
                    else:
                        stats['posters_updated'] += 1
                    if self.verbose:
                        self.stdout.write(f"     🖼️ Постер {'добавлен' if is_new else 'обновлен'}: {display_name}")
            except Exception as e:
                logger.error(f"Ошибка сохранения постера: {e}")

                # Жанры
                self.update_movie_genres(movie, full_movie_data.get('genres', []), existing_genres)

        # Персоны
        if not self.skip_persons:
            persons_data = full_movie_data.get('persons', [])
            if persons_data:
                if self.verbose:
                    d_count = sum(1 for p in persons_data if p.get('profession', '').lower() in ['режиссеры', 'director', 'режиссер', 'режиссёр'])
                    a_count = sum(1 for p in persons_data if p.get('profession', '').lower() in ['актеры', 'actor', 'актер', 'актёр'])
                    self.stdout.write(f"     👥 Обработка персон: режиссёров {d_count}, актёров {a_count}")
                self.update_movie_persons(movie, persons_data, headers, stats)
            elif self.verbose:
                self.stdout.write(f"     ⚠️ Нет данных о персонах")

        # Сеансы
        if is_new and self.create_screenings and self.halls:
            created = self.create_screenings_for_movie(movie, stats)
            if self.verbose and created > 0:
                self.stdout.write(f"     🎬 Создано сеансов: {created}")

        if self.verbose:
            if is_new:
                self.stdout.write(f"  🆕 {'🖼️' if movie.poster else '❌'} {display_name} ({duration} мин)")
            elif status == "updated":
                self.stdout.write(f"  🔄 {display_name}")
        return status

    def update_movie_genres(self, movie, api_genres, existing_genres):
        if not api_genres:
            return False

        new_genres = self.get_genres(api_genres, existing_genres)
        current_genre_ids = set(movie.genres.values_list('id', flat=True))
        new_genre_ids = {g.id for g in new_genres}

        if current_genre_ids != new_genre_ids or not current_genre_ids:
            # Удаляем старые связи
            MovieGenre.objects.filter(movie=movie).delete()
            # Создаём новые
            for genre in new_genres:
                MovieGenre.objects.create(movie=movie, genre=genre)
            if self.verbose:
                self.stdout.write(f"     🔄 Жанры обновлены: {', '.join(g.name for g in new_genres)}")
            return True
        return False

    def create_screenings_for_movie(self, movie, stats):
        if not self.halls: return 0
        created = 0
        today = timezone.now().date()
        time_slots = [9, 11, 13, 15, 17, 19, 21]
        for day_offset in range(min(random.randint(20, 45), self.screening_days)):
            current_date = today + timedelta(days=day_offset)
            for hour in random.sample(time_slots, min(random.randint(self.min_screenings, self.max_screenings), len(time_slots))):
                hall = random.choice(self.halls)
                start_time = timezone.make_aware(datetime.combine(current_date, datetime.min.time().replace(hour=hour)))
                end_time = start_time + timedelta(minutes=movie.duration + 20)
                if end_time.hour >= 24 or (end_time.hour == 23 and end_time.minute > 30):
                    continue
                if not Screening.objects.filter(hall=hall, start_time__lt=end_time, end_time__gt=start_time).exists():
                    try:
                        Screening.objects.create(movie=movie, hall=hall, start_time=start_time, end_time=end_time, ticket_price=0)
                        created += 1
                    except Exception:
                        continue
        stats['screenings_created'] += created
        return created