#!/usr/bin/env python
"""
Функциональное тестирование веб-интерфейса
Кинотеатр Премьера - Дипломный проект

Запуск: python test_web_interface.py
Требуется: selenium, webdriver-manager, django
"""

import os
import sys
import time
import logging
from datetime import datetime

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def setup_selenium():
    """Настройка Selenium WebDriver"""
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from webdriver_manager.chrome import ChromeDriverManager
    from selenium.webdriver.chrome.service import Service

    chrome_options = Options()
    chrome_options.add_argument('--headless')  # Для CI/CD, можно убрать для визуального просмотра
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--window-size=1920,1080')

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)

    return driver


class WebInterfaceTest:
    """
    Тестирование веб-интерфейса
    Сценарий: Полный пользовательский путь
    """

    def __init__(self, base_url='http://localhost:8000'):
        self.base_url = base_url
        self.driver = None
        self.test_data = {
            'email': f'test_user_{int(time.time())}@example.com',
            'name': 'Тест',
            'surname': 'Тестовый',
            'phone': '+79991234567',
            'password': 'TestPassword123!'
        }
        self.logs = []

    def log_step(self, step, status, details=''):
        """Логирование шага теста"""
        entry = {
            'timestamp': datetime.now().strftime('%H:%M:%S'),
            'step': step,
            'status': status,
            'details': details
        }
        self.logs.append(entry)

        if status == 'SUCCESS':
            logger.info(f"✅ {step}: {details}")
        else:
            logger.error(f"❌ {step}: {details}")

    def run(self):
        """Запуск теста"""
        logger.info("=" * 70)
        logger.info("🧪 НАЧАЛО ТЕСТИРОВАНИЯ ВЕБ-ИНТЕРФЕЙСА")
        logger.info("   Полный пользовательский путь: Регистрация → Выбор фильма → Оплата")
        logger.info("=" * 70)

        try:
            self.driver = setup_selenium()
            self.driver.implicitly_wait(10)

            # =========================================================
            # ШАГ 1: Открытие главной страницы
            # =========================================================
            self.log_step("Шаг 1", "INFO", "Открытие главной страницы")
            self.driver.get(self.base_url)
            time.sleep(2)

            if "Кинотеатр" in self.driver.title or "Премьера" in self.driver.title:
                self.log_step("Открытие главной страницы", "SUCCESS",
                              f"Заголовок: {self.driver.title}")
            else:
                self.log_step("Открытие главной страницы", "FAIL",
                              f"Неожиданный заголовок: {self.driver.title}")
                return

            # =========================================================
            # ШАГ 2: Переход на страницу регистрации
            # =========================================================
            self.log_step("Шаг 2", "INFO", "Переход на страницу регистрации")

            # Ищем ссылку регистрации
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC

            try:
                register_link = self.driver.find_element(By.LINK_TEXT, "Регистрация")
                register_link.click()
                time.sleep(2)

                # Проверяем, что мы на странице регистрации
                if "register" in self.driver.current_url.lower():
                    self.log_step("Переход к регистрации", "SUCCESS",
                                  f"URL: {self.driver.current_url}")
                else:
                    raise Exception("Не удалось перейти на страницу регистрации")
            except Exception as e:
                self.log_step("Переход к регистрации", "FAIL", str(e))
                return

            # =========================================================
            # ШАГ 3: Заполнение формы регистрации
            # =========================================================
            self.log_step("Шаг 3", "INFO", "Заполнение формы регистрации")

            try:
                # Заполняем поля
                email_input = self.driver.find_element(By.NAME, "email")
                email_input.send_keys(self.test_data['email'])

                name_input = self.driver.find_element(By.NAME, "name")
                name_input.send_keys(self.test_data['name'])

                surname_input = self.driver.find_element(By.NAME, "surname")
                surname_input.send_keys(self.test_data['surname'])

                number_input = self.driver.find_element(By.NAME, "number")
                number_input.send_keys(self.test_data['phone'])

                password_input = self.driver.find_element(By.NAME, "password1")
                password_input.send_keys(self.test_data['password'])

                confirm_input = self.driver.find_element(By.NAME, "password2")
                confirm_input.send_keys(self.test_data['password'])

                self.log_step("Заполнение формы", "SUCCESS",
                              f"Email: {self.test_data['email']}, Имя: {self.test_data['name']}")
            except Exception as e:
                self.log_step("Заполнение формы", "FAIL", str(e))
                return

            # =========================================================
            # ШАГ 4: Отправка формы
            # =========================================================
            self.log_step("Шаг 4", "INFO", "Отправка формы регистрации")

            try:
                # Находим кнопку отправки
                submit_button = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
                submit_button.click()
                time.sleep(2)

                self.log_step("Отправка формы", "SUCCESS", "Форма отправлена")
            except Exception as e:
                self.log_step("Отправка формы", "FAIL", str(e))
                return

            # =========================================================
            # ШАГ 5: Ожидание страницы верификации
            # =========================================================
            self.log_step("Шаг 5", "INFO", "Ожидание страницы верификации")

            try:
                WebDriverWait(self.driver, 10).until(
                    EC.url_contains("verify-email")
                )
                self.log_step("Верификация email", "SUCCESS",
                              f"Текущий URL: {self.driver.current_url}")
            except Exception as e:
                self.log_step("Верификация email", "FAIL",
                              f"Не удалось перейти на страницу верификации: {e}")
                return

            # =========================================================
            # ШАГ 6: Переход на главную страницу после регистрации
            # =========================================================
            self.log_step("Шаг 6", "INFO", "Переход на главную страницу")

            try:
                # Ищем ссылку на главную
                home_link = self.driver.find_element(By.LINK_TEXT, "Главная")
                home_link.click()
                time.sleep(2)

                self.log_step("Переход на главную", "SUCCESS",
                              f"URL: {self.driver.current_url}")
            except Exception as e:
                self.log_step("Переход на главную", "WARNING",
                              f"Не удалось найти ссылку: {e}")
                # Пытаемся перейти напрямую
                self.driver.get(self.base_url)
                time.sleep(2)

            # =========================================================
            # ШАГ 7: Поиск фильма на главной странице
            # =========================================================
            self.log_step("Шаг 7", "INFO", "Поиск доступных фильмов")

            try:
                # Ищем все карточки фильмов
                movie_cards = self.driver.find_elements(By.CSS_SELECTOR, ".movie-card, .movie-item, .film-card")

                if len(movie_cards) > 0:
                    self.log_step("Поиск фильмов", "SUCCESS",
                                  f"Найдено {len(movie_cards)} фильмов")

                    # Кликаем на первый фильм
                    first_movie = movie_cards[0]
                    first_movie.click()
                    time.sleep(2)

                    self.log_step("Выбор фильма", "SUCCESS", "Переход на страницу фильма")
                else:
                    self.log_step("Поиск фильмов", "WARNING", "Фильмы не найдены. Пропускаем выбор.")
                    return

            except Exception as e:
                self.log_step("Поиск фильмов", "WARNING", f"Ошибка: {e}")
                return

            # =========================================================
            # ШАГ 8: Выбор сеанса
            # =========================================================
            self.log_step("Шаг 8", "INFO", "Поиск доступных сеансов")

            try:
                # Ищем кнопки или блоки сеансов
                screening_buttons = self.driver.find_elements(
                    By.CSS_SELECTOR,
                    ".screening-item, .btn-screening, [onclick*='screening']"
                )

                if len(screening_buttons) > 0:
                    # Кликаем на первый сеанс
                    screening_buttons[0].click()
                    time.sleep(2)

                    self.log_step("Выбор сеанса", "SUCCESS",
                                  f"Выбран {len(screening_buttons)}-й сеанс")
                else:
                    self.log_step("Выбор сеанса", "WARNING", "Активные сеансы не найдены")
                    return

            except Exception as e:
                self.log_step("Выбор сеанса", "WARNING", f"Ошибка: {e}")
                return

            # =========================================================
            # ШАГ 9: Выбор места в зале
            # =========================================================
            self.log_step("Шаг 9", "INFO", "Выбор свободного места")

            try:
                # Ищем все незабронированные места
                available_seats = self.driver.find_elements(
                    By.CSS_SELECTOR,
                    ".seat:not(.booked):not(.taken), .seat-available"
                )

                if len(available_seats) > 0:
                    available_seats[0].click()
                    time.sleep(1)

                    self.log_step("Выбор места", "SUCCESS",
                                  f"Выбрано место #1 из {len(available_seats)} доступных")
                else:
                    self.log_step("Выбор места", "WARNING", "Свободные места не найдены")
                    return

            except Exception as e:
                self.log_step("Выбор места", "WARNING", f"Ошибка: {e}")
                return

            # =========================================================
            # ШАГ 10: Переход к оплате
            # =========================================================
            self.log_step("Шаг 10", "INFO", "Подтверждение выбора и переход к оплате")

            try:
                # Ищем кнопку "Купить" или "Оплатить"
                buy_button = self.driver.find_element(
                    By.CSS_SELECTOR,
                    "button[type='submit'], .btn-buy, .btn-pay, #book-tickets"
                )
                buy_button.click()
                time.sleep(3)

                self.log_step("Переход к оплате", "SUCCESS",
                              f"Текущий URL: {self.driver.current_url}")
            except Exception as e:
                self.log_step("Переход к оплате", "FAIL", f"Ошибка: {e}")
                return

            # =========================================================
            # ИТОГИ ТЕСТА
            # =========================================================
            logger.info("\n" + "=" * 70)
            logger.info("✅ ТЕСТИРОВАНИЕ ВЕБ-ИНТЕРФЕЙСА УСПЕШНО ЗАВЕРШЕНО")
            logger.info("   Все шаги пользовательского пути выполнены")
            logger.info("=" * 70)

            self.print_log()

        except Exception as e:
            logger.error(f"❌ КРИТИЧЕСКАЯ ОШИБКА: {e}")
            self.print_log()

        finally:
            if self.driver:
                self.driver.quit()

    def print_log(self):
        """Вывод лога выполнения"""
        print("\n" + "=" * 70)
        print("📋 ЛОГ ВЫПОЛНЕНИЯ ТЕСТА")
        print("=" * 70)
        print(f"{'Время':<12} {'Статус':<10} {'Шаг/Действие':<35} {'Детали':<30}")
        print("-" * 70)

        for log in self.logs:
            status_icon = "✅" if log['status'] == "SUCCESS" else "❌" if log['status'] == "FAIL" else "ℹ️"
            print(
                f"{log['timestamp']:<12} {status_icon} {log['status']:<7} {log['step']:<35} {log['details'][:30]:<30}")

        print("=" * 70)


def run_web_test():
    """Запуск тестирования веб-интерфейса"""
    tester = WebInterfaceTest(base_url='http://localhost:8000')
    tester.run()


if __name__ == '__main__':
    run_web_test()