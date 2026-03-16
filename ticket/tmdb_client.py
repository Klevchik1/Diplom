import requests
import logging
from django.conf import settings

logger = logging.getLogger(__name__)


class KinopoiskDevClient:
    """Клиент для работы с API Poiskkino.dev (бывший Kinopoisk.dev)"""

    # Базовый URL из документации
    BASE_URL = "https://api.poiskkino.dev"

    def __init__(self):
        # Получаем ключ из настроек Django
        self.api_key = settings.KINOPOISK_API_KEY
        if not self.api_key:
            raise ValueError("KINOPOISK_API_KEY не найден в настройках!")

        self.headers = {
            "X-API-KEY": self.api_key,
            "accept": "application/json"
        }

    def _make_request(self, endpoint, params=None):
        """Базовый метод для выполнения запросов к API"""
        url = f"{self.BASE_URL}/{endpoint.lstrip('/')}"
        try:
            response = requests.get(
                url,
                headers=self.headers,
                params=params,
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка запроса к API Poiskkino: {e}")
            return None

    def get_movie_by_id(self, movie_id):
        """Получить фильм по его ID (эндпоинт: /v1.4/movie/{id})"""
        return self._make_request(f"/v1.4/movie/{movie_id}")

    def search_movies(self, query, page=1, limit=10):
        """Поиск фильмов по названию (эндпоинт: /v1.4/movie/search)"""
        params = {
            "query": query,
            "page": page,
            "limit": limit
        }
        return self._make_request("/v1.4/movie/search", params=params)

    def get_popular_movies(self, page=1, limit=50):
        """Получение популярных фильмов с фильтрацией.
        Используем универсальный поиск (эндпоинт: /v1.4/movie) с сортировкой по рейтингу."""
        params = {
            "page": page,
            "limit": limit,
            "sortField": "rating.kp",
            "sortType": "-1",  # -1 для сортировки по убыванию
            "type": "movie",  # Только фильмы (не сериалы)
            "year": "2020-2025"  # Фильмы последних лет для актуальности
        }
        return self._make_request("/v1.4/movie", params=params)

    def get_movie_with_details(self, movie_id):
        """
        Получить фильм со всеми связанными данными (актеры, режиссеры).
        Используем тот же эндпоинт, так как /v1.4/movie/{id} возвращает всё сразу.
        """
        return self.get_movie_by_id(movie_id)
