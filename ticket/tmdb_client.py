import requests
import logging
from django.conf import settings
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


class KinopoiskDevClient:
    """Клиент для работы с API Poiskkino.dev (бывший Kinopoisk.dev)"""

    BASE_URL = "https://api.poiskkino.dev"

    def __init__(self):
        self.api_key = settings.KINOPOISK_API_KEY
        if not self.api_key:
            raise ValueError("KINOPOISK_API_KEY не найден в настройках!")

        self.headers = {
            "X-API-KEY": self.api_key,
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

    def _make_request(self, endpoint, params=None):
        """Базовый метод для выполнения запросов к API"""
        url = f"{self.BASE_URL}/{endpoint.lstrip('/')}"
        try:
            response = self.session.get(
                url,
                headers=self.headers,
                params=params,
                timeout=15
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка запроса к API Poiskkino: {e}")
            return None

    def get_movie_by_id(self, movie_id):
        """Получить фильм по его ID"""
        return self._make_request(f"/v1.4/movie/{movie_id}")

    def get_person_details(self, person_id):
        """Получить детальную информацию о персоне (актёре/режиссёре)"""
        return self._make_request(f"/v1.4/person/{person_id}")

    def download_image(self, image_url):
        """Скачать изображение по URL и вернуть bytes"""
        if not image_url:
            return None
        try:
            response = self.session.get(image_url, timeout=15)
            if response.status_code == 200:
                return response.content
            else:
                logger.warning(f"Ошибка скачивания изображения {image_url}: статус {response.status_code}")
        except Exception as e:
            logger.error(f"Ошибка скачивания изображения {image_url}: {e}")
        return None

    def search_movies(self, query, page=1, limit=10):
        """Поиск фильмов по названию"""
        params = {
            "query": query,
            "page": page,
            "limit": limit
        }
        return self._make_request("/v1.4/movie/search", params=params)

    def get_popular_movies(self, page=1, limit=50):
        """Получение популярных фильмов"""
        params = {
            "page": page,
            "limit": limit,
            "sortField": "rating.kp",
            "sortType": "-1",
            "type": "movie",
            "year": "2020-2025"
        }
        return self._make_request("/v1.4/movie", params=params)

    def get_movie_with_details(self, movie_id):
        """Получить фильм со всеми связанными данными"""
        return self.get_movie_by_id(movie_id)