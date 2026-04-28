"""
Сервис для работы с реальным API YooKassa
"""
import uuid
import logging
from datetime import timedelta
from decimal import Decimal
from django.conf import settings
from django.utils import timezone
from yookassa import Configuration, Payment as YooPayment, Refund

logger = logging.getLogger(__name__)


class YooKassaService:
    """Сервис для работы с реальным API YooKassa"""

    @staticmethod
    def _configure():
        """Настройка конфигурации YooKassa"""
        Configuration.account_id = settings.YOOKASSA_SHOP_ID
        Configuration.secret_key = settings.YOOKASSA_SECRET_KEY

    @staticmethod
    def create_payment(ticket_group, return_url):
        """
        Создание платежа в YooKassa

        Args:
            ticket_group: TicketGroup объект
            return_url: URL для возврата после оплаты

        Returns:
            dict с данными платежа
        """
        from .models import Payment as PaymentModel

        YooKassaService._configure()

        # Генерируем уникальный ключ идемпотентности
        idempotence_key = f"cinema-{ticket_group.group_uuid}-{uuid.uuid4().hex[:8]}"

        # Формируем чек для 54-ФЗ
        receipt_items = []
        for ticket in ticket_group.tickets.all():
            receipt_items.append({
                "description": f"Билет: {ticket_group.screening.movie.title} (Ряд {ticket.seat.row}, Место {ticket.seat.number})",
                "quantity": "1.00",
                "amount": {
                    "value": str(ticket.price),
                    "currency": "RUB"
                },
                "vat_code": 1,  # Без НДС для кинотеатров
                "payment_mode": "full_prepayment",
                "payment_subject": "service"
            })

        # Данные платежа
        payment_data = {
            "amount": {
                "value": str(ticket_group.total_amount),
                "currency": "RUB"
            },
            "confirmation": {
                "type": "redirect",
                "return_url": return_url
            },
            "capture": True,
            "description": f"Билеты на фильм «{ticket_group.screening.movie.title}»",
            "receipt": {
                "customer": {
                    "email": ticket_group.user.email,
                    "phone": ticket_group.user.number if ticket_group.user.number else None
                },
                "items": receipt_items
            },
            "metadata": {
                "ticket_group_uuid": str(ticket_group.group_uuid),
                "tickets_count": str(ticket_group.tickets_count),
                "movie": ticket_group.screening.movie.title,
                "user_email": ticket_group.user.email
            }
        }

        try:
            # Создаём платёж через API YooKassa
            yoo_payment = YooPayment.create(payment_data, idempotence_key)

            logger.info(f"✅ Платёж создан в YooKassa: {yoo_payment.id}")
            logger.info(f"📝 Статус: {yoo_payment.status}")
            logger.info(f"🔗 URL оплаты: {yoo_payment.confirmation.confirmation_url}")

            # Сохраняем платёж в БД
            payment = PaymentModel.objects.create(
                ticket_group=ticket_group,
                payment_id=yoo_payment.id,
                idempotence_key=idempotence_key,
                status=yoo_payment.status,
                amount=ticket_group.total_amount,
                currency='RUB',
                description=payment_data['description'],
                confirmation_url=yoo_payment.confirmation.confirmation_url,
                payment_data={
                    'yookassa_payment_id': yoo_payment.id,
                    'status': yoo_payment.status,
                    'created_at': yoo_payment.created_at,
                },
                expires_at=timezone.now() + timedelta(hours=1)
            )

            # Обновляем статус группы билетов
            ticket_group.payment_status = 'pending_payment'
            ticket_group.expires_at = payment.expires_at
            ticket_group.save(update_fields=['payment_status', 'expires_at'])

            # Логируем
            from .logging_utils import OperationLogger
            OperationLogger.log_system_operation(
                action_type='CREATE',
                module_type='TICKETS',
                description=f'Создан платёж YooKassa {yoo_payment.id}',
                object_id=payment.id,
                object_repr=str(payment),
                additional_data={
                    'payment_id': yoo_payment.id,
                    'amount': str(ticket_group.total_amount),
                    'group_uuid': str(ticket_group.group_uuid),
                    'movie': ticket_group.screening.movie.title,
                    'tickets_count': ticket_group.tickets_count,
                    'confirmation_url': yoo_payment.confirmation.confirmation_url
                }
            )

            return {
                'payment_id': yoo_payment.id,
                'confirmation_url': yoo_payment.confirmation.confirmation_url,
                'amount': str(ticket_group.total_amount),
                'status': yoo_payment.status,
                'success': True
            }

        except Exception as e:
            logger.error(f"❌ Ошибка создания платежа YooKassa: {e}")
            raise

    @staticmethod
    def check_payment(payment_id):
        """
        Проверка статуса платежа в YooKassa

        Args:
            payment_id: ID платежа в YooKassa

        Returns:
            dict с актуальными данными платежа
        """
        from .models import Payment as PaymentModel

        YooKassaService._configure()

        try:
            # Получаем информацию о платеже из YooKassa
            yoo_payment = YooPayment.find_one(payment_id)

            logger.info(f"📊 Проверка платежа {payment_id}:")
            logger.info(f"   Статус: {yoo_payment.status}")

            # Находим платёж в БД
            payment = PaymentModel.objects.get(payment_id=payment_id)

            # Обновляем статус
            old_status = payment.status
            payment.status = yoo_payment.status

            # Обновляем данные платежа
            payment_data = payment.payment_data or {}
            payment_data.update({
                'status': yoo_payment.status,
                'updated_at': str(timezone.now()),
            })

            # Если оплата успешна - сохраняем детали
            if yoo_payment.status == 'succeeded':
                # Информация о способе оплаты
                if hasattr(yoo_payment, 'payment_method') and yoo_payment.payment_method:
                    payment.payment_method = yoo_payment.payment_method.type

                    # Данные карты
                    if hasattr(yoo_payment.payment_method, 'card'):
                        payment.card_last4 = yoo_payment.payment_method.card.last4
                        payment.card_type = yoo_payment.payment_method.card.card_type

                        payment_data['card'] = {
                            'last4': payment.card_last4,
                            'type': payment.card_type,
                            'issuer_country': yoo_payment.payment_method.card.issuer_country if hasattr(yoo_payment.payment_method.card, 'issuer_country') else None
                        }

                # Обновляем группу билетов
                ticket_group = payment.ticket_group
                ticket_group.payment_status = 'paid'
                ticket_group.save(update_fields=['payment_status'])

                # Логируем успешную оплату
                from .logging_utils import OperationLogger
                OperationLogger.log_system_operation(
                    action_type='UPDATE',
                    module_type='TICKETS',
                    description=f'✅ Оплата через YooKassa: {payment.amount} ₽',
                    object_id=payment.id,
                    object_repr=str(payment),
                    additional_data={
                        'payment_id': payment_id,
                        'amount': str(payment.amount),
                        'ticket_group_uuid': str(ticket_group.group_uuid),
                        'movie': ticket_group.screening.movie.title,
                        'tickets_count': ticket_group.tickets_count,
                        'card_last4': payment.card_last4,
                        'card_type': payment.card_type
                    }
                )

            payment.payment_data = payment_data
            payment.save()

            return {
                'payment_id': yoo_payment.id,
                'status': yoo_payment.status,
                'amount': str(payment.amount),
                'card_last4': payment.card_last4,
                'card_type': payment.card_type,
                'success': yoo_payment.status == 'succeeded'
            }

        except PaymentModel.DoesNotExist:
            logger.error(f"Платёж {payment_id} не найден в БД")
            return {'payment_id': payment_id, 'status': 'unknown', 'success': False}
        except Exception as e:
            logger.error(f"❌ Ошибка проверки платежа {payment_id}: {e}")
            raise

    @staticmethod
    def create_refund(payment_id, amount=None):
        """
        Создание возврата в YooKassa

        Args:
            payment_id: ID платежа
            amount: сумма возврата (если None - полный возврат)

        Returns:
            dict с данными возврата
        """
        from .models import Payment as PaymentModel

        YooKassaService._configure()

        try:
            payment = PaymentModel.objects.get(payment_id=payment_id)

            # Если сумма не указана - полный возврат
            if amount is None:
                amount = payment.amount

            refund_data = {
                "amount": {
                    "value": str(amount),
                    "currency": "RUB"
                },
                "payment_id": payment_id,
                "description": f"Возврат билетов на фильм «{payment.ticket_group.screening.movie.title}»"
            }

            # Создаём возврат через API
            refund = Refund.create(refund_data)

            logger.info(f"✅ Создан возврат {refund.id} для платежа {payment_id}")
            logger.info(f"   Сумма: {amount} ₽")
            logger.info(f"   Статус: {refund.status}")

            # Сохраняем информацию о возврате
            payment.refund_id = refund.id
            payment.refund_status = refund.status
            payment.save()

            # Логируем возврат
            from .logging_utils import OperationLogger
            OperationLogger.log_system_operation(
                action_type='UPDATE',
                module_type='TICKETS',
                description=f'Создан возврат YooKassa {refund.id} на сумму {amount} ₽',
                object_id=payment.id,
                object_repr=str(payment),
                additional_data={
                    'payment_id': payment_id,
                    'refund_id': refund.id,
                    'amount': str(amount),
                    'status': refund.status
                }
            )

            return {
                'refund_id': refund.id,
                'status': refund.status,
                'amount': str(amount),
                'success': True
            }

        except PaymentModel.DoesNotExist:
            return {'success': False, 'error': 'Платёж не найден'}
        except Exception as e:
            logger.error(f"❌ Ошибка создания возврата для {payment_id}: {e}")
            return {'success': False, 'error': str(e)}