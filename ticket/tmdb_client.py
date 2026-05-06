import requests
import logging
import time
from datetime import datetime
from django.conf import settings
from django.utils import timezone
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


class KinopoiskDevClient:
    """Клиент для работы с API Poiskkino.dev с ротацией токенов"""

    BASE_URL = "https://api.poiskkino.dev"

    def __init__(self, token_model=None):
        """
        Инициализация клиента.
        token_model — модель APIToken для отслеживания использования (опционально)
        """
        self._token_model = token_model
        self._api_key = self._get_api_key()

        if not self._api_key:
            raise ValueError("Нет доступных API токенов!")

        self.headers = {
            "X-API-KEY": self._api_key,
            "accept": "application/json"
        }

        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def _get_api_key(self):
        """Получить API ключ: сначала из модели токена, затем из settings"""
        if self._token_model and self._token_model.can_make_request():
            return self._token_model.token

        # Ищем активный токен в БД
        try:
            from ticket.models import APIToken
            active_token = APIToken.objects.filter(is_active=True).first()
            if active_token and active_token.can_make_request():
                self._token_model = active_token
                return active_token.token
        except Exception:
            pass

        # Fallback на settings
        return getattr(settings, 'KINOPOISK_API_KEY', None)

    def _register_request(self, success=True):
        """Зарегистрировать запрос в статистике"""
        if self._token_model:
            try:
                self._token_model.register_request()
            except Exception as e:
                logger.warning(f"Ошибка регистрации запроса: {e}")

    def _log_request(self, endpoint, params, status_code, success, duration_ms, response_size=None, error=None):
        """Логировать запрос в БД"""
        try:
            from ticket.models import APIRequestLog
            APIRequestLog.objects.create(
                token=self._token_model,
                endpoint=endpoint,
                params=params or {},
                status_code=status_code,
                success=success,
                response_size=response_size,
                duration_ms=duration_ms,
                error_message=error[:500] if error else ''
            )
        except Exception as e:
            logger.warning(f"Ошибка логирования запроса: {e}")

    def _make_request(self, endpoint, params=None):
        """Базовый метод для выполнения запросов к API"""
        url = f"{self.BASE_URL}/{endpoint.lstrip('/')}"
        start_time = time.time()

        try:
            response = self.session.get(
                url,
                headers=self.headers,
                params=params,
                timeout=15
            )
            duration_ms = int((time.time() - start_time) * 1000)

            success = response.status_code == 200
            self._register_request(success=success)
            self._log_request(
                endpoint=endpoint,
                params=params,
                status_code=response.status_code,
                success=success,
                duration_ms=duration_ms,
                response_size=len(response.content) if response.content else None
            )

            if response.status_code == 429:
                logger.warning("Rate limit превышен, ждём 5 секунд...")
                time.sleep(5)
                return None

            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            duration_ms = int((time.time() - start_time) * 1000)
            self._register_request(success=False)
            self._log_request(
                endpoint=endpoint,
                params=params,
                status_code=getattr(e.response, 'status_code', None) if hasattr(e, 'response') else None,
                success=False,
                duration_ms=duration_ms,
                error=str(e)
            )
            logger.error(f"Ошибка запроса к API Poiskkino: {e}")
            return None

    # ═══ Методы API ═══

    def get_movie_by_id(self, movie_id):
        """Получить фильм по ID"""
        return self._make_request(f"/v1.4/movie/{movie_id}")

    def get_person_details(self, person_id):
        """Получить информацию о персоне"""
        return self._make_request(f"/v1.4/person/{person_id}")

    def search_movies(self, query, page=1, limit=10):
        """Поиск фильмов"""
        return self._make_request("/v1.4/movie/search", params={
            "query": query, "page": page, "limit": limit
        })

    def get_movies_page(self, page=1, limit=50, year_from=2020, year_to=2025, sort_field="votes.kp", genres=None):
        """Получить страницу фильмов с фильтрацией"""
        params = {
            "page": page,
            "limit": limit,
            "sortField": sort_field,
            "sortType": "-1",
            "type": "movie",
            "year": f"{year_from}-{year_to}"
        }
        if genres:
            params["genres.name"] = genres
        return self._make_request("/v1.4/movie", params=params)

    def download_image(self, image_url):
        """Скачать изображение"""
        if not image_url:
            return None
        try:
            response = self.session.get(image_url, timeout=15)
            if response.status_code == 200:
                return response.content
        except Exception as e:
            logger.error(f"Ошибка скачивания изображения {image_url}: {e}")
        return None

    def get_available_genres(self):
        """Получить список доступных жанров из API"""
        return self._make_request("/v1.4/movie/possible-values", params={"field": "genres.name"})

    @classmethod
    def get_total_available_tokens(cls):
        """Получить общее количество доступных токенов и запросов"""
        try:
            from ticket.models import APIToken
            tokens = APIToken.objects.filter(is_active=True)
            total_remaining = sum(t.remaining_today() for t in tokens)
            total_limit = sum(t.daily_limit for t in tokens)
            return {
                'tokens_count': tokens.count(),
                'total_remaining': total_remaining,
                'total_limit': total_limit,
                'tokens': [
                    {
                        'label': t.label,
                        'remaining': t.remaining_today(),
                        'limit': t.daily_limit,
                        'is_active': t.is_active
                    } for t in tokens
                ]
            }
        except Exception:
            return {'tokens_count': 0, 'total_remaining': 0, 'total_limit': 0, 'tokens': []}