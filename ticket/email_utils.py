import logging
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


def send_verification_email(pending_registration):
    """Отправка email с кодом подтверждения для временной регистрации"""
    try:
        subject = 'Подтверждение email - Кинотеатр Премьера'

        # HTML версия письма
        html_message = render_to_string('ticket/email_verification.html', {
            'user_name': pending_registration.name,
            'verification_code': pending_registration.verification_code,
        })

        # Текстовая версия письма
        plain_message = f"""
        Подтверждение email - Кинотеатр Премьера

        Здравствуйте, {pending_registration.name}!

        Для завершения регистрации введите следующий код подтверждения:

        {pending_registration.verification_code}

        Код действителен в течение 30 минут.

        Если вы не регистрировались в нашем кинотеатре, просто проигнорируйте это письмо.

        С уважением,
        Команда Кинотеатра Премьера
        """

        # Отправляем email
        result = send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[pending_registration.email],
            html_message=html_message,
            fail_silently=False,
        )

        logger.info(f"Verification email sent to {pending_registration.email}")
        return True

    except Exception as e:
        logger.error(f"Failed to send verification email to {pending_registration.email}: {str(e)}")
        return False


def send_verification_email_to_user(user, code):
    """Отправка кода подтверждения существующему пользователю"""
    subject = 'Подтверждение email - Кинотеатр Премьера'

    html_message = render_to_string('ticket/email_verification.html', {
        'user': user,
        'verification_code': code,
        'expires_in': '10 минут'
    })

    plain_message = f"""
    Здравствуйте, {user.name} {user.surname}!

    Ваш код подтверждения email: {code}

    Код действителен в течение 10 минут.

    Если вы не регистрировались в кинотеатре "Премьера", просто проигнорируйте это письмо.

    С уважением,
    Администрация кинотеатра "Премьера"
    """

    try:
        send_mail(
            subject,
            plain_message,
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            html_message=html_message,
            fail_silently=False,
        )
        return True
    except Exception as e:
        logger.error(f"Failed to send verification email to {user.email}: {e}")
        return False


def send_welcome_email(user):
    """Отправка приветственного письма после подтверждения"""
    try:
        subject = 'Добро пожаловать в Кинотеатр Премьера!'

        html_message = render_to_string('ticket/welcome_email.html', {
            'user': user,
        })

        plain_message = f"""
        Добро пожаловать в Кинотеатр Премьера!

        Здравствуйте, {user.name} {user.surname}!

        Ваш email успешно подтверждён. Теперь вы можете:

        • Покупать билеты на сеансы
        • Получать уведомления о покупках
        • Скачивать электронные билеты

        Начните прямо сейчас: http://localhost:8000

        С уважением,
        Команда Кинотеатра Премьера
        """

        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )

        logger.info(f"Welcome email sent to {user.email}")
        return True

    except Exception as e:
        logger.error(f"Failed to send welcome email to {user.email}: {str(e)}")
        return False


def send_password_reset_email(user, reset_code):
    """Отправка email с кодом восстановления пароля"""
    try:
        subject = 'Восстановление пароля - Кинотеатр Премьера'

        # HTML версия письма
        html_message = render_to_string('ticket/password_reset_email.html', {
            'user': user,
            'reset_code': reset_code,
        })

        # Текстовая версия письма
        plain_message = f"""
        Восстановление пароля - Кинотеатр Премьера

        Здравствуйте, {user.name}!

        Для восстановления пароля введите следующий код:

        {reset_code}

        Код действителен в течение 30 минут.

        Если вы не запрашивали восстановление пароля, просто проигнорируйте это письмо.

        С уважением,
        Команда Кинотеатра Премьера
        """

        # Отправляем email
        result = send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )

        logger.info(f"Password reset email sent to {user.email}")
        return True

    except Exception as e:
        logger.error(f"Failed to send password reset email to {user.email}: {str(e)}")
        return False


def send_email_change_verification(user, new_email, verification_code):
    """Отправка кода подтверждения для смены email"""
    try:
        from django.core.mail import EmailMultiAlternatives
        from django.template.loader import render_to_string
        from django.utils.html import strip_tags
        from django.contrib.sites.shortcuts import get_current_site
        from django.conf import settings

        subject = 'Подтверждение смены email в кинотеатре Премьера'

        context = {
            'user': user,
            'new_email': new_email,
            'verification_code': verification_code,
        }

        html_message = render_to_string('ticket/email_change_verification.html', context)
        plain_message = strip_tags(html_message)

        from_email = settings.DEFAULT_FROM_EMAIL
        to_email = new_email

        email = EmailMultiAlternatives(
            subject,
            plain_message,
            from_email,
            [to_email]
        )
        email.attach_alternative(html_message, "text/html")

        result = email.send()
        logger.info(f"Email change verification sent to {new_email}. Result: {result}")
        return result > 0

    except Exception as e:
        logger.error(f"Failed to send email change verification to {new_email}: {str(e)}")
        return False


def send_screening_completed_notification(user, movie_title, screening_date):
    """Отправка уведомления о прошедшем сеансе (опционально)"""
    try:
        subject = f'Сеанс завершён - {movie_title}'

        html_message = render_to_string('ticket/screening_completed_email.html', {
            'user': user,
            'movie_title': movie_title,
            'screening_date': screening_date,
        })

        plain_message = f"""
        Кинотеатр Премьера

        Здравствуйте, {user.name}!

        Сеанс фильма "{movie_title}" ({screening_date}) завершён.
        Спасибо, что выбрали наш кинотеатр!

        Вы можете оставить отзыв о фильме в личном кабинете.

        С уважением,
        Команда Кинотеатра Премьера
        """

        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=True,  # Не прерываем выполнение при ошибке
        )

        logger.info(f"Screening completed notification sent to {user.email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send notification to {user.email}: {str(e)}")
        return False


def send_ticket_receipt(user, ticket_group, payment):
    """Отправка чека на почту после успешной оплаты"""
    try:
        from django.core.mail import EmailMultiAlternatives
        from django.template.loader import render_to_string
        from django.utils.html import strip_tags

        tickets = ticket_group.tickets.all().select_related(
            'seat', 'screening__movie', 'screening__hall'
        )

        subject = f'Чек об оплате билетов - Кинотеатр Премьера'

        # Генерируем PDF для вложения
        from .utils import generate_enhanced_ticket_pdf
        pdf_buffer = generate_enhanced_ticket_pdf(tickets)
        pdf_buffer.seek(0)

        # Список мест
        seats_list = ", ".join(
            f"Ряд {t.seat.row}, Место {t.seat.number}" for t in tickets
        )

        plain_message = f"""
Кинотеатр Премьера — Чек об оплате

Здравствуйте, {user.name}!

Спасибо за покупку билетов!

Фильм: {ticket_group.screening.movie.title}
Дата и время: {ticket_group.screening.start_time.strftime('%d.%m.%Y %H:%M')}
Зал: {ticket_group.screening.hall.name}
Места: {seats_list}
Количество билетов: {ticket_group.tickets_count}
Сумма: {ticket_group.total_amount} ₽
Номер заказа: {ticket_group.group_uuid}

Билеты прикреплены к письму в формате PDF.

Приятного просмотра!
Команда Кинотеатра Премьера
        """

        html_message = render_to_string('ticket/payment_receipt_email.html', {
            'user': user,
            'ticket_group': ticket_group,
            'tickets': tickets,
            'payment': payment,
            'seats_list': seats_list,
        })

        email = EmailMultiAlternatives(
            subject,
            plain_message,
            settings.DEFAULT_FROM_EMAIL,
            [user.email]
        )
        email.attach_alternative(html_message, "text/html")

        # Прикрепляем PDF
        filename = f"bilety_{ticket_group.screening.movie.title.replace(' ', '_')}_{ticket_group.group_uuid.hex[:8]}.pdf"
        email.attach(filename, pdf_buffer.getvalue(), 'application/pdf')

        result = email.send()
        logger.info(f"Receipt email sent to {user.email}. Result: {result}")
        return result > 0

    except Exception as e:
        logger.error(f"Failed to send receipt email to {user.email}: {str(e)}")
        return False