"""
Нагрузочное тестирование для production-сервера
Предполагается, что на сервере есть тестовые данные (ID начинаются с 1)
Запуск: locust -f ticket/tests/load/locust_server.py --host=http://cinemapremiere.online --headless --users=50 --spawn-rate=10 --run-time=5m --html=load_test_report.html
"""
from locust import HttpUser, task, between
import random
from datetime import datetime, timedelta


class CinemaUser(HttpUser):
    """Пользователь кинотеатра"""
    wait_time = between(0.5, 2)  # 0.5-2 секунды между запросами

    @task(6)
    def home(self):
        """Главная страница"""
        self.client.get("/")

    @task(5)
    def movies_with_date(self):
        """Список фильмов с фильтрацией по дате"""
        days_offset = random.randint(0, 4)
        date_param = (datetime.now() + timedelta(days=days_offset)).strftime('%Y-%m-%d')
        self.client.get(f"/?date={date_param}")

    @task(4)
    def movies_with_genre(self):
        """Список фильмов с фильтрацией по жанру"""
        genres = ['Боевик', 'Комедия', 'Драма', 'Фантастика', 'Триллер']
        genre = random.choice(genres)
        self.client.get(f"/?genre={genre}")

    @task(4)
    def about(self):
        """Страница 'О кинотеатре'"""
        self.client.get("/about/")

    @task(4)
    def movie_detail(self):
        """Страница деталей фильма (ID от 1 до 20, предполагается что есть)"""
        movie_id = random.randint(1, 20)
        self.client.get(f"/movie/{movie_id}/")

    @task(3)
    def screening_detail(self):
        """Страница сеанса (ID от 1 до 30)"""
        screening_id = random.randint(1, 30)
        self.client.get(f"/screening/{screening_id}/")

    @task(2)
    def seating_chart(self):
        """AJAX загрузка схемы зала"""
        screening_id = random.randint(1, 30)
        self.client.get(f"/screening/{screening_id}/partial/")

    @task(1)
    def login_page(self):
        """Страница входа (без отправки формы)"""
        self.client.get("/login/")


class ReadOnlyUser(HttpUser):
    """Только чтение (без POST запросов) — самый безопасный вариант"""
    wait_time = between(1, 3)

    @task(10)
    def home(self):
        self.client.get("/")

    @task(8)
    def movies(self):
        date_param = datetime.now().strftime('%Y-%m-%d')
        self.client.get(f"/?date={date_param}")

    @task(6)
    def about(self):
        self.client.get("/about/")

    @task(5)
    def movie_detail(self):
        movie_id = random.randint(1, 20)
        self.client.get(f"/movie/{movie_id}/")

    @task(3)
    def screening_detail(self):
        screening_id = random.randint(1, 30)
        self.client.get(f"/screening/{screening_id}/")

    @task(2)
    def seating_chart(self):
        screening_id = random.randint(1, 30)
        self.client.get(f"/screening/{screening_id}/partial/")