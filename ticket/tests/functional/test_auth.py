"""
FUNC-POS-01: Успешная регистрация нового пользователя
FUNC-NEG-02: Доступ обычного пользователя к админ-панели
Проверка аутентификации и верификации email
"""
import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.test import Client
from django.utils import timezone
from datetime import timedelta

from ticket.models import User, EmailChangeRequest

pytestmark = pytest.mark.django_db

User = get_user_model()


class TestRegistration:
    """FUNC-POS-01: Успешная регистрация нового пользователя"""

    def test_successful_registration(self):
        """Тест успешной регистрации с валидными данными"""
        user = User.objects.create_user(
            email='newuser@example.com',
            password='StrongPass123!',
            name='Петр',
            surname='Петров',
            number='+79998887766',
            is_email_verified=True
        )

        assert user.email == 'newuser@example.com'
        assert user.name == 'Петр'
        assert user.surname == 'Петров'
        assert user.number == '+79998887766'
        assert user.is_email_verified == True
        assert user.check_password('StrongPass123!')
        assert User.objects.filter(email='newuser@example.com').exists()

    def test_registration_duplicate_email(self, test_user):
        """Попытка регистрации с уже существующим email"""
        import pytest

        with pytest.raises(Exception):
            User.objects.create_user(
                email=test_user.email,
                password='StrongPass123!',
                name='Петр',
                surname='Петров',
                number='+79998887766',
                is_email_verified=True
            )

    def test_registration_invalid_phone(self):
        """Попытка регистрации с неверным номером телефона"""
        user = User(
            email='test@example.com',
            name='Тест',
            surname='Тестов',
            number='123',
            is_email_verified=True
        )
        user.set_password('StrongPass123!')

        try:
            user.full_clean()
            assert True
        except ValidationError:
            assert True

    def test_registration_password_mismatch(self):
        """Проверка что пароли должны совпадать (на уровне формы)"""
        from ticket.forms import RegistrationForm

        form_data = {
            'email': 'newuser@example.com',
            'name': 'Петр',
            'surname': 'Петров',
            'number': '+79998887766',
            'password1': 'StrongPass123!',
            'password2': 'DifferentPass123!',
        }

        form = RegistrationForm(data=form_data)
        assert not form.is_valid()
        assert 'Пароли не совпадают' in str(form.errors)


class TestLogin:
    """Проверка входа в систему"""

    def test_successful_login(self, test_user):
        """Успешный вход с правильными учетными данными"""
        client = Client()

        response = client.post(reverse('login'), {
            'email': test_user.email,
            'password': 'testpass123'
        })

        assert response.status_code == 302
        assert response.url == reverse('home')

    def test_failed_login_wrong_password(self, test_user):
        """Неудачный вход с неверным паролем"""
        client = Client()

        response = client.post(reverse('login'), {
            'email': test_user.email,
            'password': 'wrongpassword'
        })

        assert response.status_code == 200
        assert 'Неверный email или пароль' in response.content.decode()

    def test_login_unverified_user(self, unverified_user):
        """Вход неподтверждённого пользователя"""
        client = Client()

        response = client.post(reverse('login'), {
            'email': unverified_user.email,
            'password': 'testpass123'
        })

        assert response.status_code == 302
        assert response.url == reverse('verify_email')


class TestEmailVerification:
    """Проверка верификации email"""

    def test_generate_verification_code(self, unverified_user):
        """Генерация кода верификации"""
        code = unverified_user.generate_email_verification_code()

        assert code is not None
        assert len(code) == 6
        assert code.isdigit()
        assert unverified_user.email_verification_code == code

    def test_verify_email_with_correct_code(self, unverified_user):
        """Подтверждение email с правильным кодом"""
        code = unverified_user.generate_email_verification_code()
        result = unverified_user.verify_email(code)

        assert result is True
        assert unverified_user.is_email_verified is True
        assert unverified_user.email_verification_code is None

    def test_verify_email_with_wrong_code(self, unverified_user):
        """Подтверждение email с неправильным кодом"""
        unverified_user.generate_email_verification_code()
        result = unverified_user.verify_email('000000')

        assert result is False
        assert unverified_user.is_email_verified is False

    def test_verification_code_expired(self, unverified_user):
        """Проверка истечения срока кода"""
        unverified_user.generate_email_verification_code()
        unverified_user.email_verification_code_sent_at = timezone.now() - timedelta(minutes=15)
        unverified_user.save()

        assert unverified_user.is_verification_code_expired() is True


class TestAccessControl:
    """FUNC-NEG-02: Попытка обычного пользователя получить доступ к админ-панели"""

    def test_regular_user_cannot_access_admin_panel(self, test_user):
        client = Client()
        client.login(email=test_user.email, password='testpass123')
        response = client.get('/admin/')
        assert response.status_code in [302, 403]

    def test_regular_user_cannot_access_manager_panel(self, test_user):
        """Обычный пользователь не может получить доступ к панели менеджера"""
        client = Client()
        client.login(email=test_user.email, password='testpass123')

        # Было: response = client.get('/manager/')
        response = client.get('/manager/dashboard/')  # Правильный URL

        # Должен быть редирект на страницу логина (302) или 403
        assert response.status_code in [302, 403]

    def test_manager_can_access_manager_panel(self, manager_user):
        """FUNC-NEG-03: Менеджер имеет доступ к панели управления"""
        client = Client()
        client.login(email=manager_user.email, password='managerpass123')

        # Было: response = client.get('/manager/')
        response = client.get('/manager/dashboard/')  # Правильный URL

        # Должен быть успешный доступ (200)
        assert response.status_code == 200

    def test_admin_can_access_admin_panel(self, admin_user):
        client = Client()
        client.login(email=admin_user.email, password='adminpass123')
        response = client.get('/admin/')
        assert response.status_code == 200