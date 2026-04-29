"""
FPOS-01-тест-аутентификации-1
Успешная регистрация и верификация пользователя
"""
import json
from datetime import timedelta
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from ticket.models import User, PendingRegistration
from ticket.forms import RegistrationForm


class AuthenticationTest(TestCase):
    """Тестирование системы аутентификации"""

    def setUp(self):
        """Настройка тестовых данных"""
        self.client = Client()
        self.test_email = "testuser@example.com"
        self.test_password = "TestPassword123"
        self.test_data = {
            'email': self.test_email,
            'name': 'Иван',
            'surname': 'Иванов',
            'number': '+79123456789',
            'password1': self.test_password,
            'password2': self.test_password
        }

        # Очищаем тестовые данные перед каждым тестом
        User.objects.filter(email=self.test_email).delete()
        PendingRegistration.objects.filter(email=self.test_email).delete()

    def test_fpos_01_registration_success(self):
        """FPOS-01: Успешная регистрация с верификацией email"""
        print("\n" + "=" * 60)
        print("FPOS-01-тест-аутентификации-1")
        print("Тест: Успешная регистрация пользователя")
        print("=" * 60)

        # Шаг 1: Отправка формы регистрации
        print("Шаг 1: Отправка формы регистрации...")
        response = self.client.post(reverse('register'), self.test_data)

        # Проверяем редирект на страницу верификации
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('verify_email'))
        print("✓ Форма регистрации отправлена успешно")

        # Проверяем создание временной записи
        pending_reg = PendingRegistration.objects.filter(email=self.test_email).first()
        self.assertIsNotNone(pending_reg)
        self.assertEqual(pending_reg.email, self.test_email)
        self.assertEqual(pending_reg.name, 'Иван')
        print("✓ Создана временная запись регистрации")

        # Шаг 2: Проверка сессии
        print("Шаг 2: Проверка данных сессии...")
        session = self.client.session
        self.assertIn('pending_registration_id', session)
        self.assertEqual(session['pending_registration_email'], self.test_email)
        print("✓ Данные сессии сохранены корректно")

        # Шаг 3: Верификация email
        print("Шаг 3: Верификация email...")
        verification_data = {
            'verification_code': pending_reg.verification_code
        }
        response = self.client.post(reverse('verify_email'), verification_data)

        # Проверяем редирект на домашнюю страницу
        self.assertEqual(response.status_code, 302)
        print("✓ Код верификации принят")

        # Шаг 4: Проверка создания пользователя
        print("Шаг 4: Проверка создания пользователя в БД...")
        user = User.objects.filter(email=self.test_email).first()
        self.assertIsNotNone(user)
        self.assertTrue(user.is_email_verified)
        self.assertEqual(user.name, 'Иван')
        self.assertEqual(user.surname, 'Иванов')
        print(f"✓ Пользователь создан: {user.email}")

        # Шаг 5: Удаление временной записи
        pending_reg_exists = PendingRegistration.objects.filter(email=self.test_email).exists()
        self.assertFalse(pending_reg_exists)
        print("✓ Временная запись удалена после верификации")

        # Шаг 6: Проверка авторизации
        print("Шаг 6: Тест авторизации созданного пользователя...")
        login_data = {
            'email': self.test_email,
            'password': self.test_password
        }
        response = self.client.post(reverse('login'), login_data)
        self.assertEqual(response.status_code, 302)
        print("✓ Авторизация прошла успешно")

        print("\n" + "=" * 60)
        print("РЕЗУЛЬТАТ: ТЕСТ УСПЕШНО ПРОЙДЕН ✅")
        print("=" * 60)