#!/usr/bin/env python
"""
Функциональное тестирование серверной части
Кинотеатр Премьера - Дипломный проект

Запуск: python test_cinema_system.py
Требуется: pytest, django (настроенный проект)
"""

import os
import sys
import django
import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import patch, MagicMock

# Настройка Django окружения
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cinematic.settings.development')
django.setup()

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone
from ticket.models import (
    User, Movie, Hall, HallType, Screening, Seat, Ticket,
    TicketGroup, TicketStatus, ActionType, ModuleType
)
from ticket.forms import RegistrationForm, MovieForm, ScreeningForm
from ticket.views import is_manager

User = get_user_model()


# ═══════════════════════════════════════════════════════════════
# ФИКСТУРЫ ДЛЯ ТЕСТОВ
# ═══════════════════════════════════════════════════════════════

@pytest.fixture
def test_user():
    """Создание тестового пользователя"""
    user = User.objects.create_user(
        email='test@example.com',
        password='TestPassword123',
        name='Иван',
        surname='Тестов',
        number='+79991234567',
        is_email_verified=True
    )
    yield user
    user.delete()


@pytest.fixture
def test_manager():
    """Создание менеджера"""
    manager = User.objects.create_user(
        email='manager@example.com',
        password='ManagerPass123',
        name='Менеджер',
        surname='Тестов',
        number='+79990000000',
        is_email_verified=True,
        is_staff=True
    )
    yield manager
    manager.delete()


@pytest.fixture
def test_hall_type():
    """Создание типа зала"""
    hall_type = HallType.objects.create(
        name='Тестовый тип',
        base_price=Decimal('300.00'),
        price_coefficient=Decimal('1.0')
    )
    yield hall_type
    hall_type.delete()


@pytest.fixture
def test_hall(test_hall_type):
    """Создание зала"""
    hall = Hall.objects.create(
        name='Тестовый зал',
        rows=5,
        seats_per_row=8,
        hall_type=test_hall_type
    )
    yield hall
    hall.delete()


@pytest.fixture
def test_movie():
    """Создание фильма"""
    movie = Movie.objects.create(
        title='Тестовый фильм',
        description='Описание тестового фильма',
        duration=120,
        release_year=2024,
        age_rating_id=1  # предполагаем, что есть рейтинг 12+
    )
    yield movie
    movie.delete()


@pytest.fixture
def test_screening(test_movie, test_hall):
    """Создание сеанса"""
    start_time = timezone.now() + timedelta(days=1, hours=10)
    screening = Screening.objects.create(
        movie=test_movie,
        hall=test_hall,
        start_time=start_time,
        ticket_price=Decimal('350.00')
    )
    # Устанавливаем end_time
    duration_timedelta = timedelta(minutes=test_movie.duration)
    screening.end_time = start_time + duration_timedelta + timedelta(minutes=10)
    screening.save()
    yield screening
    screening.delete()


@pytest.fixture
def test_ticket_status():
    """Создание статуса билета"""
    status, _ = TicketStatus.objects.get_or_create(
        code='active',
        defaults={
            'name': 'Активный',
            'description': 'Билет активен',
            'is_active': True,
            'can_be_refunded': True
        }
    )
    return status


# ═══════════════════════════════════════════════════════════════
# ТЕСТ 1: ФУНКЦИОНАЛЬНЫЙ ПОЗИТИВНЫЙ ТЕСТ (FUNC-POS-01)
# Регистрация нового пользователя
# ═══════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestRegistration:
    """Тестирование регистрации пользователей"""

    def test_successful_registration(self):
        """
        ID теста: FUNC-POS-01
        Название: Успешная регистрация нового пользователя
        """
        # Данные для регистрации
        form_data = {
            'email': 'newuser@example.com',
            'name': 'Петр',
            'surname': 'Петров',
            'number': '+79998887766',
            'password1': 'StrongPass123!',
            'password2': 'StrongPass123!'
        }

        form = RegistrationForm(data=form_data)

        # Проверяем валидность формы
        assert form.is_valid(), f"Форма невалидна: {form.errors}"

        # Проверяем, что пользователь не существует до регистрации
        assert not User.objects.filter(email='newuser@example.com').exists()

        # Создаём временную регистрацию
        from ticket.models import PendingRegistration
        pending = PendingRegistration.objects.create(
            email=form_data['email'],
            name=form_data['name'],
            surname=form_data['surname'],
            number=form_data['number'],
            password='hashed_password',
            verification_code='123456'
        )

        assert pending.email == 'newuser@example.com'
        assert not pending.is_expired()

        # Создаём пользователя из временной регистрации
        user = pending.create_user()

        # Проверяем создание пользователя
        assert User.objects.filter(email='newuser@example.com').exists()
        assert user.name == 'Петр'
        assert user.surname == 'Петров'
        assert user.is_email_verified == True

        print("[SUCCESS] FUNC-POS-01: Регистрация пользователя успешно выполнена")


# ═══════════════════════════════════════════════════════════════
# ТЕСТ 2: ФУНКЦИОНАЛЬНЫЙ ПОЗИТИВНЫЙ ТЕСТ (FUNC-POS-02)
# Бронирование билетов и создание платежа
# ═══════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestTicketBooking:
    """Тестирование бронирования билетов"""

    def test_create_booking_and_payment(self, test_user, test_screening, test_ticket_status):
        """
        ID теста: FUNC-POS-02
        Название: Создание бронирования и формирование платежа
        """
        # Получаем места в зале
        seats = Seat.objects.filter(hall=test_screening.hall)[:3]
        assert len(seats) >= 3, "Недостаточно мест для теста"

        seat_ids = [seat.id for seat in seats]
        total_amount = test_screening.ticket_price * len(seat_ids)

        # Создаём группу билетов
        ticket_group = TicketGroup.objects.create(
            user=test_user,
            screening=test_screening,
            purchase_date=timezone.now(),
            total_amount=total_amount,
            tickets_count=len(seat_ids),
            payment_status='pending_payment'
        )

        # Создаём билеты
        for seat in seats:
            Ticket.objects.create(
                user=test_user,
                screening=test_screening,
                seat=seat,
                price=test_screening.ticket_price,
                status=test_ticket_status,
                ticket_group=ticket_group
            )

        # Проверяем создание группы
        assert ticket_group.tickets_count == len(seat_ids)
        assert ticket_group.total_amount == total_amount
        assert ticket_group.payment_status == 'pending_payment'

        # Проверяем создание билетов
        tickets = Ticket.objects.filter(ticket_group=ticket_group)
        assert tickets.count() == len(seat_ids)

        # Проверяем, что места забронированы
        for seat in seats:
            is_booked = Ticket.objects.filter(
                screening=test_screening,
                seat=seat,
                status__code='active'
            ).exists()
            assert is_booked, f"Место {seat.row}-{seat.number} не забронировано"

        # Проверяем генерацию PDF
        from ticket.utils import generate_enhanced_ticket_pdf
        pdf_buffer = generate_enhanced_ticket_pdf(list(tickets))
        assert pdf_buffer is not None
        assert len(pdf_buffer.getvalue()) > 1000  # PDF не пустой

        print(f"[SUCCESS] FUNC-POS-02: Бронирование {len(seat_ids)} билетов успешно создано")
        print(f"         Группа UUID: {ticket_group.group_uuid}")
        print(f"         Общая сумма: {total_amount} ₽")


# ═══════════════════════════════════════════════════════════════
# ТЕСТ 3: ФУНКЦИОНАЛЬНЫЙ ПОЗИТИВНЫЙ ТЕСТ (FUNC-POS-03)
# Возврат билета
# ═══════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestTicketRefund:
    """Тестирование возврата билетов"""

    def test_refund_ticket(self, test_user, test_screening, test_ticket_status):
        """
        ID теста: FUNC-POS-03
        Название: Успешный возврат билета до начала сеанса
        """
        # Получаем место
        seat = Seat.objects.filter(hall=test_screening.hall).first()
        assert seat is not None

        # Убеждаемся, что сеанс в будущем (>30 минут)
        now = timezone.now()
        time_until = test_screening.start_time - now
        assert time_until.total_seconds() > 1800, "Сеанс слишком близко для теста возврата"

        # Создаём билет
        ticket = Ticket.objects.create(
            user=test_user,
            screening=test_screening,
            seat=seat,
            price=test_screening.ticket_price,
            status=test_ticket_status
        )

        # Проверяем возможность возврата
        can_refund, message = ticket.can_be_refunded()
        assert can_refund, f"Возврат невозможен: {message}"

        # Выполняем возврат
        success, result_message = ticket.request_refund()

        # Проверяем результат
        assert success, f"Возврат не удался: {result_message}"

        # Обновляем билет из БД
        ticket.refresh_from_db()

        # Проверяем, что статус изменился на refunded
        assert ticket.status.code == 'refunded'
        assert ticket.refund_processed_at is not None

        print(f"[SUCCESS] FUNC-POS-03: Билет успешно возвращён")
        print(f"         Статус билета: {ticket.status.name}")
        print(f"         Дата возврата: {ticket.refund_processed_at}")


# ═══════════════════════════════════════════════════════════════
# ТЕСТ 4: НЕГАТИВНЫЙ ТЕСТ НА ВАЛИДАЦИЮ (FUNC-NEG-01)
# Попытка бронирования уже занятого места
# ═══════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestBookingValidation:
    """Тестирование валидации при бронировании"""

    def test_book_already_taken_seat(self, test_user, test_screening, test_ticket_status):
        """
        ID теста: FUNC-NEG-01
        Название: Попытка бронирования уже занятого места
        Ожидаемый результат: Ошибка валидации
        """
        # Получаем место
        seat = Seat.objects.filter(hall=test_screening.hall).first()
        assert seat is not None

        # Создаём первый билет (занимаем место)
        first_ticket = Ticket.objects.create(
            user=test_user,
            screening=test_screening,
            seat=seat,
            price=test_screening.ticket_price,
            status=test_ticket_status
        )

        # Пытаемся создать второй билет на то же место
        try:
            second_ticket = Ticket(
                user=test_user,
                screening=test_screening,
                seat=seat,
                price=test_screening.ticket_price
            )
            second_ticket.save()
            assert False, "Ожидалась ValidationError, но билет создался"
        except ValidationError as e:
            # Ожидаемая ошибка
            assert "уже занято" in str(e) or "already" in str(e)
            print(f"[SUCCESS] FUNC-NEG-01: Ошибка валидации корректно обработана")
            print(f"         Сообщение об ошибке: {e}")
        except Exception as e:
            assert False, f"Неожиданное исключение: {e}"


# ═══════════════════════════════════════════════════════════════
# ТЕСТ 5: НЕГАТИВНЫЙ ТЕСТ НА ПРОВЕРКУ РОЛЕЙ (FUNC-NEG-02)
# Попытка доступа к админ-панели обычным пользователем
# ═══════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestRoleAccess:
    """Тестирование разграничения прав доступа"""

    def test_regular_user_cannot_access_admin(self, test_user):
        """
        ID теста: FUNC-NEG-02
        Название: Попытка обычного пользователя получить доступ к админ-панели
        Ожидаемый результат: Отказ в доступе
        """
        # Проверяем, что пользователь не является staff/superuser
        assert not test_user.is_staff
        assert not test_user.is_superuser

        # Проверяем декоратор staff_member_required
        from django.contrib.admin.views.decorators import staff_member_required

        # Симулируем проверку доступа
        def protected_view(request):
            return True

        wrapped = staff_member_required(protected_view)

        # Создаём mock-request
        class MockRequest:
            def __init__(self, user):
                self.user = user
                self.META = {}
                self.path = '/admin/'

        request = MockRequest(test_user)

        # Проверяем, что доступ запрещён
        from django.core.exceptions import PermissionDenied
        try:
            wrapped(request)
            assert False, "Ожидался PermissionDenied, но доступ был разрешён"
        except PermissionDenied:
            print("[SUCCESS] FUNC-NEG-02: Обычный пользователь не может получить доступ к админ-панели")
        except Exception as e:
            assert False, f"Неожиданное исключение: {e}"

    def test_manager_can_access_manager_panel(self, test_manager):
        """
        ID теста: FUNC-NEG-03
        Название: Проверка доступа менеджера к панели менеджера
        Ожидаемый результат: Доступ разрешён
        """
        # Проверяем, что пользователь является staff
        assert test_manager.is_staff

        # Проверяем функцию is_manager
        class MockRequest:
            def __init__(self, user):
                self.user = user
                self.META = {}

        request = MockRequest(test_manager)

        # Менеджер должен иметь доступ
        assert is_manager(request.user) == True

        # Проверяем декоратор user_passes_test
        from django.contrib.auth.decorators import user_passes_test

        def protected_view(request):
            return True

        wrapped = user_passes_test(is_manager)(protected_view)

        # Доступ должен быть разрешён
        result = wrapped(request)
        assert result == True

        print("[SUCCESS] FUNC-NEG-03: Менеджер имеет доступ к панели менеджера")


# ═══════════════════════════════════════════════════════════════
# ТЕСТ 6: ТЕСТИРОВАНИЕ API ДЛЯ ИМПОРТА (FUNC-API-01)
# ═══════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestAPIImport:
    """Тестирование API для импорта фильмов"""

    @patch('ticket.tmdb_client.KinopoiskDevClient')
    def test_search_movie_api_success(self, mock_client_class, test_manager):
        """
        ID теста: FUNC-API-01
        Название: Поиск фильма через API Poiskkino.dev
        Ожидаемый результат: Успешный поиск и возврат данных
        """
        from ticket.views import search_movie_api
        from django.http import HttpRequest

        # Настройка мока
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        # Мок-ответ от API
        mock_client.search_movies.return_value = {
            'docs': [
                {
                    'id': 1,
                    'name': 'Тестовый фильм',
                    'year': 2024,
                    'movieLength': 120,
                    'description': 'Тестовое описание',
                    'poster': {'url': 'https://example.com/poster.jpg'},
                    'rating': {'kp': 8.5},
                    'genres': [{'name': 'Драма'}]
                }
            ]
        }

        # Создаём запрос
        request = HttpRequest()
        request.user = test_manager
        request.GET = {'query': 'Тестовый фильм'}

        # Вызываем view
        response = search_movie_api(request)

        # Проверяем ответ
        assert response.status_code == 200
        import json
        data = json.loads(response.content)

        assert data['success'] == True
        assert len(data['movies']) == 1
        assert data['movies'][0]['title'] == 'Тестовый фильм'

        print("[SUCCESS] FUNC-API-01: API поиска фильмов работает корректно")


# ═══════════════════════════════════════════════════════════════
# ЗАПУСК ТЕСТОВ
# ═══════════════════════════════════════════════════════════════

def run_tests():
    """Запуск всех тестов с выводом отчёта"""
    print("\n" + "=" * 70)
    print("🧪 ФУНКЦИОНАЛЬНОЕ ТЕСТИРОВАНИЕ СЕРВЕРНОЙ ЧАСТИ")
    print("   Система управления кинотеатром «Кинотеатр Премьера»")
    print("=" * 70 + "\n")

    # Инициализируем тесты
    test_reg = TestRegistration()
    test_booking = TestTicketBooking()
    test_refund = TestTicketRefund()
    test_validation = TestBookingValidation()
    test_roles = TestRoleAccess()
    test_api = TestAPIImport()

    results = []

    # Запуск тестов
    print("📋 Результаты тестирования:\n")

    try:
        test_reg.test_successful_registration()
        results.append(("FUNC-POS-01", "PASS", "Регистрация пользователя"))
    except Exception as e:
        results.append(("FUNC-POS-01", "FAIL", str(e)))

    try:
        test_booking.test_create_booking_and_payment(None, None, None)
        results.append(("FUNC-POS-02", "PASS", "Бронирование билетов"))
    except Exception as e:
        results.append(("FUNC-POS-02", "FAIL", str(e)))

    try:
        test_refund.test_refund_ticket(None, None, None)
        results.append(("FUNC-POS-03", "PASS", "Возврат билета"))
    except Exception as e:
        results.append(("FUNC-POS-03", "FAIL", str(e)))

    try:
        test_validation.test_book_already_taken_seat(None, None, None)
        results.append(("FUNC-NEG-01", "PASS", "Валидация занятого места"))
    except Exception as e:
        results.append(("FUNC-NEG-01", "FAIL", str(e)))

    try:
        test_roles.test_regular_user_cannot_access_admin(None)
        results.append(("FUNC-NEG-02", "PASS", "Доступ к админ-панели"))
    except Exception as e:
        results.append(("FUNC-NEG-02", "FAIL", str(e)))

    try:
        test_roles.test_manager_can_access_manager_panel(None)
        results.append(("FUNC-NEG-03", "PASS", "Доступ менеджера"))
    except Exception as e:
        results.append(("FUNC-NEG-03", "FAIL", str(e)))

    try:
        test_api.test_search_movie_api_success(None, None)
        results.append(("FUNC-API-01", "PASS", "API поиска фильмов"))
    except Exception as e:
        results.append(("FUNC-API-01", "FAIL", str(e)))

    # Вывод результатов
    print("\n" + "-" * 70)
    print("📊 СВОДНАЯ ТАБЛИЦА РЕЗУЛЬТАТОВ")
    print("-" * 70)
    print(f"{'ID теста':<15} {'Статус':<10} {'Описание':<40}")
    print("-" * 70)

    passed = 0
    for test_id, status, description in results:
        status_icon = "✅" if status == "PASS" else "❌"
        print(f"{test_id:<15} {status_icon} {status:<7} {description:<40}")
        if status == "PASS":
            passed += 1

    print("-" * 70)
    print(f"\n📈 ИТОГО: {passed}/{len(results)} тестов пройдено успешно")

    if passed == len(results):
        print("\n🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
    else:
        print(f"\n⚠️ {len(results) - passed} тестов не пройдено. Требуется доработка.")

    print("\n" + "=" * 70)
    print("🏁 ТЕСТИРОВАНИЕ ЗАВЕРШЕНО")
    print("=" * 70)

    return results


if __name__ == '__main__':
    run_tests()