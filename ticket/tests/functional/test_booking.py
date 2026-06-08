"""
FUNC-POS-02: Создание бронирования и формирование платежа
FUNC-POS-03: Успешный возврат билета до начала сеанса
FUNC-NEG-01: Попытка бронирования уже занятого места
"""
import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.test import Client
from django.utils import timezone
from decimal import Decimal
from datetime import timedelta

from ticket.models import Ticket, TicketGroup, Seat, TicketStatus

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def setup_ticket_statuses(db):
    """Автоматически создаёт статусы билетов перед каждым тестом"""
    statuses = [
        {'code': 'active', 'name': 'Активный', 'can_be_refunded': True},
        {'code': 'refunded', 'name': 'Возвращён', 'can_be_refunded': False},
        {'code': 'used', 'name': 'Использован', 'can_be_refunded': False},
        {'code': 'archived', 'name': 'Архивный', 'can_be_refunded': False},
    ]
    for status_data in statuses:
        TicketStatus.objects.get_or_create(
            code=status_data['code'],
            defaults={
                'name': status_data['name'],
                'can_be_refunded': status_data['can_be_refunded'],
                'is_active': True
            }
        )


class TestBooking:
    """FUNC-POS-02: Создание бронирования"""

    def test_create_ticket_group(self, test_user, screening):
        active_status = TicketStatus.objects.get(code='active')
        seats = Seat.objects.filter(hall=screening.hall)[:3]

        group = TicketGroup.objects.create(
            user=test_user,
            screening=screening,
            purchase_date=timezone.now(),
            total_amount=Decimal('1050.00'),
            tickets_count=3,
            payment_status='paid'
        )

        for seat in seats:
            Ticket.objects.create(
                user=test_user,
                screening=screening,
                seat=seat,
                price=screening.ticket_price,
                status=active_status,
                ticket_group=group
            )

        assert group.id is not None
        assert group.tickets_count == 3
        assert group.total_amount == Decimal('1050.00')
        assert group.tickets.count() == 3

    def test_cannot_book_occupied_seat(self, test_user, screening, seat):
        active_status = TicketStatus.objects.get(code='active')

        Ticket.objects.create(
            user=test_user,
            screening=screening,
            seat=seat,
            price=Decimal('350.00'),
            status=active_status
        )

        with pytest.raises(ValidationError):
            Ticket.objects.create(
                user=test_user,
                screening=screening,
                seat=seat,
                price=Decimal('350.00'),
                status=active_status
            )

    def test_ticket_group_uuid_generation(self, test_user, screening):
        group = TicketGroup.objects.create(
            user=test_user,
            screening=screening,
            purchase_date=timezone.now(),
            total_amount=Decimal('350.00'),
            tickets_count=1,
            payment_status='paid'
        )

        assert group.group_uuid is not None
        assert len(str(group.group_uuid)) == 36


class TestRefund:
    """FUNC-POS-03: Успешный возврат билета"""

    def test_can_be_refunded_true(self, single_ticket):
        can_refund, message = single_ticket.can_be_refunded()
        assert can_refund is True

    def test_can_be_refunded_false_soon(self, test_user, screening_soon, seat, active_ticket_status):
        ticket = Ticket.objects.create(
            user=test_user,
            screening=screening_soon,
            seat=seat,
            price=Decimal('350.00'),
            status=active_ticket_status
        )

        can_refund, message = ticket.can_be_refunded()
        assert can_refund is False
        assert 'минут' in message

    def test_request_refund_success(self, single_ticket):
        refunded_status = TicketStatus.objects.get(code='refunded')
        success, message = single_ticket.request_refund()

        assert success is True
        assert 'успешно возвращен' in message
        single_ticket.refresh_from_db()
        assert single_ticket.status == refunded_status
        assert single_ticket.refund_processed_at is not None

    def test_group_refund_success(self, ticket_group):
        refunded_status = TicketStatus.objects.get(code='refunded')
        success, message = ticket_group.request_refund()

        assert success is True
        assert 'успешно возвращена' in message

        for ticket in ticket_group.tickets.all():
            ticket.refresh_from_db()
            assert ticket.status == refunded_status
            assert ticket.refund_processed_at is not None