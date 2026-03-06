import json
import logging
import uuid
from datetime import datetime, timedelta
import re

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import make_password
from django.db.models import Q, Count, Sum, Avg
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .email_utils import send_verification_email, send_welcome_email, send_password_reset_email, send_email_change_verification
from .forms import (
    MovieForm, HallForm, ScreeningForm, UserUpdateForm,
    PasswordResetForm, EmailChangeForm, RegistrationForm, LoginForm,
    DirectorForm, ActorForm, HallTypeForm, CountryForm
)
from .models import (
    PasswordResetRequest, AgeRating, PendingRegistration,
    Screening, Ticket, Seat, Movie, Hall, User,
    Director, Actor, Country, HallType, TicketGroup,
    EmailChangeRequest, TicketStatus, ActionType, ModuleType,
    MovieDirector, MovieActor, Genre  # Добавлен Genre
)
from .utils import generate_enhanced_ticket_pdf, generate_ticket_pdf
from .report_utils import ReportGenerator
from .logging_utils import OperationLogger
from decimal import Decimal

logger = logging.getLogger(__name__)


@staff_member_required
def admin_dashboard(request):
    """Панель управления для администратора"""
    return render(request, 'ticket/admin_dashboard.html')


def register(request):
    """Регистрация нового пользователя"""
    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            name = form.cleaned_data['name']
            surname = form.cleaned_data['surname']
            number = form.cleaned_data['number']
            password = form.cleaned_data['password1']

            # Удаляем старые просроченные регистрации
            PendingRegistration.objects.filter(email=email).delete()

            # Генерируем код подтверждения
            import random
            import string
            verification_code = ''.join(random.choices(string.digits, k=6))

            # Сохраняем данные во временную модель
            pending_reg = PendingRegistration.objects.create(
                email=email,
                name=name,
                surname=surname,
                number=number,
                password=make_password(password),
                verification_code=verification_code
            )

            # ЛОГИРОВАНИЕ РЕГИСТРАЦИИ
            OperationLogger.log_operation(
                request=request,
                action_type='CREATE',
                module_type='USERS',
                description=f'Начата регистрация пользователя {email}',
                object_id=pending_reg.id,
                object_repr=f"{name} {surname}"
            )

            request.session['pending_registration_id'] = pending_reg.id
            request.session['pending_registration_email'] = email
            request.session.save()

            logger.info(f"Session data saved: {request.session.session_key}")

            # Отправляем email
            try:
                if send_verification_email(pending_reg):
                    messages.success(request, f'Код подтверждения отправлен на email {email}')
                    logger.info(f"Email sent successfully to {email}")
                else:
                    messages.warning(request, f'Письмо отправлено, но возникли проблемы с доставкой.')
            except Exception as e:
                logger.error(f"Email sending error: {e}")
                messages.warning(request, f'Код подтверждения: {verification_code}')

            return redirect('verify_email')

        else:
            OperationLogger.log_operation(
                request=request,
                action_type='OTHER',
                module_type='AUTH',
                description=f'Ошибка в форме регистрации для {request.POST.get("email", "unknown")}',
                additional_data={
                    'form_errors': form.errors,
                    'email': request.POST.get('email', '')
                }
            )
            messages.error(request, 'Пожалуйста, исправьте ошибки в форме.')
    else:
        form = RegistrationForm()

    return render(request, 'ticket/register.html', {'form': form})


def verify_email(request):
    """Страница ввода кода подтверждения"""
    pending_reg_id = request.session.get('pending_registration_id')
    email = request.session.get('pending_registration_email')

    logger.info(f"Session data in verify_email: pending_reg_id={pending_reg_id}, email={email}")

    if not pending_reg_id or not email:
        logger.error("Missing session data in verify_email")
        messages.error(request, 'Сессия истекла. Пожалуйста, начните регистрацию заново.')
        return redirect('register')

    try:
        pending_reg = PendingRegistration.objects.get(id=pending_reg_id, email=email)
        logger.info(f"Found pending registration: {pending_reg.id}")
    except PendingRegistration.DoesNotExist:
        logger.error(f"Pending registration not found: id={pending_reg_id}, email={email}")
        messages.error(request, 'Регистрация не найдена. Пожалуйста, зарегистрируйтесь заново.')
        request.session.pop('pending_registration_id', None)
        request.session.pop('pending_registration_email', None)
        return redirect('register')

    if pending_reg.is_expired():
        logger.warning(f"Pending registration expired: {pending_reg.id}")
        pending_reg.delete()
        messages.error(request, 'Время для подтверждения истекло. Пожалуйста, зарегистрируйтесь заново.')
        request.session.pop('pending_registration_id', None)
        request.session.pop('pending_registration_email', None)
        return redirect('register')

    if request.method == 'POST':
        code = request.POST.get('verification_code', '').strip()

        if not code:
            messages.error(request, 'Введите код подтверждения')
            return render(request, 'ticket/verify_email.html', {
                'email': pending_reg.email
            })

        if pending_reg.verification_code == code:
            # Код верный - создаем пользователя
            user = pending_reg.create_user()

            # ЛОГИРОВАНИЕ УСПЕШНОЙ РЕГИСТРАЦИИ
            OperationLogger.log_operation(
                request=request,
                action_type='CREATE',
                module_type='USERS',
                description=f'Успешная регистрация и верификация пользователя {user.email}',
                object_id=user.id,
                object_repr=str(user)
            )

            # Отправляем приветственное письмо
            try:
                send_welcome_email(user)
            except Exception as e:
                logger.error(f"Welcome email error: {e}")

            # Логиним пользователя
            login(request, user)

            # Удаляем временную запись
            pending_reg.delete()

            # Очищаем сессию
            request.session.pop('pending_registration_id', None)
            request.session.pop('pending_registration_email', None)

            messages.success(request, 'Email успешно подтвержден! Добро пожаловать!')
            return redirect('home')
        else:
            # ЛОГИРОВАНИЕ НЕВЕРНОГО КОДА
            OperationLogger.log_operation(
                request=request,
                action_type='OTHER',
                module_type='AUTH',
                description=f'Неверный код подтверждения для {pending_reg.email}'
            )
            messages.error(request, 'Неверный код подтверждения')
            logger.warning(f"Invalid verification code entered for {pending_reg.email}")

    return render(request, 'ticket/verify_email.html', {
        'email': pending_reg.email
    })


def resend_verification_code(request):
    """Повторная отправка кода подтверждения"""
    pending_reg_id = request.session.get('pending_registration_id')

    if not pending_reg_id:
        messages.error(request, 'Сессия истекла.')
        return redirect('register')

    try:
        pending_reg = PendingRegistration.objects.get(id=pending_reg_id)

        # Генерируем новый код
        import random
        import string
        new_code = ''.join(random.choices(string.digits, k=6))

        # Обновляем код
        pending_reg.verification_code = new_code
        pending_reg.save()

        # Отправляем email
        if send_verification_email(pending_reg):
            messages.success(request, 'Новый код подтверждения отправлен на ваш email')
        else:
            messages.error(request, 'Ошибка при отправке кода. Попробуйте позже.')

    except PendingRegistration.DoesNotExist:
        messages.error(request, 'Регистрация не найдена.')
        return redirect('register')

    return redirect('verify_email')


def user_login(request):
    """Авторизация пользователя"""
    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']
            user = authenticate(request, email=email, password=password)

            if user is not None:
                # ПРОВЕРЯЕМ, ТРЕБУЕТСЯ ЛИ ПОДТВЕРЖДЕНИЕ EMAIL
                if user.requires_email_verification() and not user.is_email_verified:
                    # Если email не подтвержден, отправляем новый код
                    # Создаем временную регистрацию для повторной отправки
                    pending_reg = PendingRegistration.objects.create(
                        email=user.email,
                        name=user.name,
                        surname=user.surname,
                        number=user.number,
                        password=user.password,
                        verification_code=user.generate_email_verification_code()
                    )
                    request.session['pending_registration_id'] = pending_reg.id
                    request.session['pending_registration_email'] = user.email
                    messages.warning(request, 'Ваш email не подтвержден. Новый код отправлен на вашу почту.')
                    return redirect('verify_email')

                login(request, user)

                # ЛОГИРОВАНИЕ ВХОДА
                OperationLogger.log_operation(
                    request=request,
                    action_type='LOGIN',
                    module_type='AUTH',
                    description=f'Успешный вход пользователя {user.email}'
                )

                next_url = request.GET.get('next', 'home')
                return redirect(next_url)
            else:
                # ЛОГИРОВАНИЕ НЕУДАЧНОЙ ПОПЫТКИ ВХОДА
                OperationLogger.log_operation(
                    request=request,
                    action_type='OTHER',
                    module_type='AUTH',
                    description=f'Неудачная попытка входа для email {email}',
                    additional_data={
                        'email': email,
                        'ip_address': request.META.get('REMOTE_ADDR', 'unknown'),
                        'user_agent': request.META.get('HTTP_USER_AGENT', '')[:100]
                    }
                )
                messages.error(request, 'Неверный email или пароль')
    else:
        form = LoginForm()

    return render(request, 'ticket/login.html', {'form': form})


def home(request):
    """Главная страница с фильмами и сеансами"""
    local_now = timezone.localtime(timezone.now())
    today = local_now.date()

    search_query = request.GET.get('search', '')
    hall_filter = request.GET.get('hall', '')
    genre_filter = request.GET.get('genre', '')
    age_rating_filter = request.GET.get('age_rating', '')
    selected_date = request.GET.get('date', today.isoformat())

    # Преобразуем выбранную дату
    try:
        selected_date = datetime.strptime(selected_date, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        selected_date = today

    # Генерируем список дат для фильтра (5 дней)
    date_filters = []
    for i in range(5):
        filter_date = today + timedelta(days=i)
        date_filters.append({
            'date': filter_date,
            'is_today': i == 0,
            'is_tomorrow': i == 1,
            'label': get_date_label(filter_date, i)
        })

    # Получаем все фильмы
    movies = Movie.objects.prefetch_related(
        'screenings__hall'
    ).select_related('genre', 'age_rating').all()

    # Применяем текстовые фильтры
    if search_query:
        movies = movies.filter(
            Q(title__icontains=search_query) |
            Q(description__icontains=search_query)
        )

    if genre_filter:
        movies = movies.filter(genre__name=genre_filter)

    if age_rating_filter:
        movies = movies.filter(age_rating__name=age_rating_filter)

    # Собираем данные для каждого фильма
    movies_data = []

    for movie in movies:
        # Базовый фильтр для сеансов
        screenings_filter = Q(
            start_time__date=selected_date,
            start_time__gt=local_now  # Только будущие сеансы
        )

        # Применяем фильтр по залу если выбран
        if hall_filter:
            screenings_filter &= Q(hall_id=hall_filter)

        # Получаем сеансы на выбранную дату с учетом всех фильтров
        screenings_on_date = movie.screenings.filter(screenings_filter).order_by('start_time')

        # Получаем ближайшие сеансы (максимум 3)
        upcoming_screenings = screenings_on_date[:3]

        # Определяем самый ранний сеанс для сортировки
        earliest_screening = screenings_on_date.first()

        movies_data.append({
            'movie': movie,
            'upcoming_screenings': upcoming_screenings,
            'screening_count': screenings_on_date.count(),
            'earliest_screening': earliest_screening,
            'has_screenings_today': screenings_on_date.exists()
        })

    # Сортируем фильмы
    movies_with_screenings = [m for m in movies_data if m['has_screenings_today']]
    movies_without_screenings = [m for m in movies_data if not m['has_screenings_today']]

    movies_with_screenings.sort(
        key=lambda x: x['earliest_screening'].start_time if x['earliest_screening'] else local_now)

    sorted_movies_data = movies_with_screenings + movies_without_screenings

    # Получаем жанры для фильтра
    genres = Genre.objects.values_list('name', flat=True).distinct().order_by('name')

    # Получаем возрастные рейтинги
    age_ratings = AgeRating.objects.all().order_by('name')

    return render(request, 'ticket/home.html', {
        'movies': sorted_movies_data,
        'halls': Hall.objects.all(),
        'genres': genres,
        'age_ratings': age_ratings,
        'date_filters': date_filters,
        'selected_date': selected_date,
        'today': today,
        'current_filters': {
            'search': search_query,
            'hall': hall_filter,
            'genre': genre_filter,
            'age_rating': age_rating_filter,
            'date': selected_date.isoformat()
        }
    })


def get_date_label(date, index):
    """Генерирует подпись для даты в фильтре"""
    today = timezone.localtime(timezone.now()).date()

    # Русские названия месяцев
    months = {
        1: 'января', 2: 'февраля', 3: 'марта', 4: 'апреля',
        5: 'мая', 6: 'июня', 7: 'июля', 8: 'августа',
        9: 'сентября', 10: 'октября', 11: 'ноября', 12: 'декабря'
    }

    day = date.day
    month = months[date.month]

    if index == 0:
        return {"label": "Сегодня", "date": f"{day} {month}"}
    elif index == 1:
        return {"label": "Завтра", "date": f"{day} {month}"}
    else:
        days_of_week = {
            0: 'Пн', 1: 'Вт', 2: 'Ср', 3: 'Чт',
            4: 'Пт', 5: 'Сб', 6: 'Вс'
        }
        day_of_week = days_of_week[date.weekday()]
        return {"label": day_of_week, "date": f"{day} {month}"}


def user_logout(request):
    """Выход из системы"""
    if request.user.is_authenticated:
        OperationLogger.log_operation(
            request=request,
            action_type='LOGOUT',
            module_type='AUTH',
            description=f'Выход пользователя {request.user.email}'
        )

    logout(request)
    messages.info(request, 'Вы успешно вышли из системы.')
    return redirect('login')


def movie_detail(request, movie_id):
    """Детальная страница фильма"""
    movie = get_object_or_404(
        Movie.objects.select_related('genre', 'age_rating').prefetch_related('directors', 'actors'),
        pk=movie_id
    )
    local_now = timezone.localtime(timezone.now())

    # Предстоящие сеансы
    upcoming_screenings = movie.screenings.filter(
        start_time__gt=local_now
    ).select_related('hall', 'hall__hall_type').order_by('start_time')

    # Прошедшие сеансы (последние 2)
    past_screenings = movie.screenings.filter(
        start_time__lte=local_now
    ).select_related('hall').order_by('-start_time')[:2]

    return render(request, 'ticket/movie_detail.html', {
        'movie': movie,
        'upcoming_screenings': upcoming_screenings,
        'past_screenings': past_screenings,
    })


def screening_detail(request, screening_id):
    """Детальная страница сеанса с выбором мест"""
    screening = get_object_or_404(
        Screening.objects.select_related('movie', 'hall', 'hall__hall_type'),
        pk=screening_id
    )

    # Загружаем информацию о фильме с режиссёрами и актёрами
    movie = Movie.objects.prefetch_related(
        'directors',
        'actors',
        'genre',
        'age_rating'
    ).get(pk=screening.movie.id)

    seats = Seat.objects.filter(hall=screening.hall).order_by('row', 'number')

    # Получаем все билеты на этот сеанс
    booked_tickets = Ticket.objects.filter(screening=screening).select_related('status')
    booked_seat_ids = [ticket.seat.id for ticket in booked_tickets]

    # Группируем места по рядам
    rows = {}
    for seat in seats:
        if seat.row not in rows:
            rows[seat.row] = []
        rows[seat.row].append(seat)

    return render(request, 'ticket/screening_detail.html', {
        'screening': screening,
        'movie': movie,  # Передаём movie с предзагруженными режиссёрами и актёрами
        'rows': rows,
        'booked_seat_ids': booked_seat_ids,
        'is_guest': not request.user.is_authenticated
    })


@login_required
@require_POST
def book_tickets(request):
    """Покупка билетов"""
    screening_id = request.POST.get('screening_id')
    selected_seats = request.POST.get('selected_seats')

    if not selected_seats:
        messages.error(request, "Выберите хотя бы одно место.")
        return redirect('screening_detail', screening_id=screening_id)

    try:
        seat_ids = json.loads(selected_seats)
    except json.JSONDecodeError as e:
        messages.error(request, "Ошибка при обработке выбранных мест. Попробуйте снова.")
        return redirect('screening_detail', screening_id=screening_id)

    if not seat_ids:
        messages.error(request, "Выберите хотя бы одно место.")
        return redirect('screening_detail', screening_id=screening_id)

    screening = get_object_or_404(Screening, pk=screening_id)

    # Проверяем доступность мест
    for seat_id in seat_ids:
        seat = get_object_or_404(Seat, pk=seat_id)
        if Ticket.objects.filter(screening=screening, seat=seat).exists():
            messages.error(request, f"Место {seat.row}-{seat.number} уже занято.")
            return redirect('screening_detail', screening_id=screening_id)

    # Получаем активный статус для билетов
    active_status = TicketStatus.objects.get(code='active')

    # Создаем группу билетов
    ticket_group = TicketGroup.objects.create(
        user=request.user,
        screening=screening,
        purchase_date=timezone.now(),
        total_amount=screening.ticket_price * len(seat_ids),
        tickets_count=len(seat_ids)
    )

    # Создаем билеты
    tickets = []
    for seat_id in seat_ids:
        seat = get_object_or_404(Seat, pk=seat_id)
        ticket = Ticket.objects.create(
            user=request.user,
            screening=screening,
            seat=seat,
            price=screening.ticket_price,
            status=active_status,
            ticket_group=ticket_group
        )
        tickets.append(ticket)

    # ЛОГИРОВАНИЕ ПОКУПКИ БИЛЕТОВ
    OperationLogger.log_operation(
        request=request,
        action_type='CREATE',
        module_type='TICKETS',
        description=f'Покупка {len(tickets)} билетов на фильм {screening.movie.title}',
        object_id=tickets[0].id if tickets else None,
        object_repr=f"Группа билетов #{ticket_group.id}",
        additional_data={
            'screening_id': screening_id,
            'movie_title': screening.movie.title,
            'seat_count': len(tickets),
            'total_price': float(ticket_group.total_amount),
            'group_id': str(ticket_group.group_uuid)
        }
    )

    # Отправляем уведомление в Telegram
    if tickets and request.user.is_telegram_verified:
        try:
            from ticket.telegram_bot.bot import get_bot
            import asyncio

            async def send_notification():
                bot = get_bot()
                if bot:
                    await bot.send_ticket_notification(request.user, tickets)

            asyncio.run(send_notification())
        except Exception as e:
            logger.error(f"Failed to send Telegram notification: {e}")

    return redirect(f'{reverse("screening_detail", args=[screening_id])}?purchase_success=true&group_id={ticket_group.group_uuid}')


@login_required
def download_ticket(request):
    """Скачивание билетов по group_id из GET параметров"""
    group_uuid = request.GET.get('group_id')

    if not group_uuid:
        return redirect('home')

    try:
        ticket_group = TicketGroup.objects.get(group_uuid=group_uuid, user=request.user)
        tickets = ticket_group.tickets.all().select_related(
            'screening__movie', 'screening__hall', 'seat', 'status'
        )
    except TicketGroup.DoesNotExist:
        return redirect('home')

    if not tickets.exists():
        return redirect('home')

    pdf_buffer = generate_ticket_pdf(tickets)

    response = HttpResponse(pdf_buffer.getvalue(), content_type='application/pdf')
    filename = f"билет_{tickets[0].screening.movie.title}_{group_uuid[:8]}.pdf"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@login_required
def download_ticket_single(request, ticket_id):
    """Скачивание одного билета"""
    ticket = get_object_or_404(Ticket, id=ticket_id, user=request.user)

    # Проверяем статус билета
    if ticket.status and ticket.status.code == 'refunded' and not request.user.is_staff:
        messages.error(request, 'Нельзя скачать возвращённый билет')
        return redirect('profile')

    # Если билет входит в группу, скачиваем всю группу
    if ticket.ticket_group:
        tickets = Ticket.objects.filter(ticket_group=ticket.ticket_group, user=request.user)
    else:
        tickets = [ticket]

    # ЛОГИРОВАНИЕ СКАЧИВАНИЯ PDF
    OperationLogger.log_operation(
        request=request,
        action_type='EXPORT',
        module_type='TICKETS',
        description=f'Скачивание PDF билета для фильма {ticket.screening.movie.title}',
        object_id=ticket.id,
        object_repr=str(ticket),
        additional_data={
            'format': 'PDF',
            'movie': ticket.screening.movie.title,
            'ticket_count': len(tickets),
            'group_id': str(ticket.ticket_group.group_uuid) if ticket.ticket_group else None,
            'status': ticket.status.code if ticket.status else 'unknown',
            'is_refunded': ticket.status and ticket.status.code == 'refunded'
        }
    )

    try:
        pdf_buffer = generate_enhanced_ticket_pdf(tickets)
        response = HttpResponse(pdf_buffer.getvalue(), content_type='application/pdf')

        if len(tickets) > 1 and ticket.ticket_group:
            filename = f"билет_{ticket.screening.movie.title}_{ticket.ticket_group.group_uuid[:8]}.pdf"
        else:
            filename = f"билет_{ticket.screening.movie.title}_{ticket.id}.pdf"

        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
    except Exception as e:
        logger.error(f"Ошибка генерации PDF: {str(e)}")
        messages.error(request, "Ошибка при генерации билета. Пожалуйста, попробуйте позже.")
        return redirect('profile')


@login_required
def download_ticket_group(request, group_uuid):
    """Скачивание группы билетов по UUID"""
    try:
        ticket_group = TicketGroup.objects.get(group_uuid=group_uuid, user=request.user)
        tickets = ticket_group.tickets.all().select_related(
            'screening__movie', 'screening__hall', 'seat', 'status'
        )
    except TicketGroup.DoesNotExist:
        messages.error(request, "Билеты не найдены.")
        return redirect('profile')

    if not tickets.exists():
        messages.error(request, "Билеты не найдены.")
        return redirect('profile')

    # Проверяем статус группы билетов
    has_refunded_tickets = any(ticket.status and ticket.status.code == 'refunded' for ticket in tickets)

    if has_refunded_tickets and not request.user.is_staff:
        messages.error(request, 'В этой группе есть возвращённые билеты. Скачивание невозможно.')
        return redirect('profile')

    # ЛОГИРОВАНИЕ СКАЧИВАНИЯ PDF ГРУППЫ
    OperationLogger.log_operation(
        request=request,
        action_type='EXPORT',
        module_type='TICKETS',
        description=f'Скачивание PDF группы билетов для фильма {tickets[0].screening.movie.title}',
        object_id=tickets[0].id,
        object_repr=f"Группа билетов {group_uuid}",
        additional_data={
            'format': 'PDF',
            'movie': tickets[0].screening.movie.title,
            'ticket_count': len(tickets),
            'group_id': group_uuid,
            'has_refunded_tickets': has_refunded_tickets
        }
    )

    try:
        pdf_buffer = generate_enhanced_ticket_pdf(tickets)
        response = HttpResponse(pdf_buffer.getvalue(), content_type='application/pdf')
        filename = f"билет_{tickets[0].screening.movie.title}_{group_uuid[:8]}.pdf"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
    except Exception as e:
        logger.error(f"Ошибка генерации PDF: {str(e)}")
        messages.error(request, "Ошибка при генерации билета. Пожалуйста, попробуйте позже.")
        return redirect('profile')


@login_required
def profile(request):
    """Профиль пользователя"""
    # Получаем все билеты пользователя
    all_tickets = Ticket.objects.filter(
        user=request.user
    ).select_related(
        'screening__movie', 'screening__hall', 'seat', 'status', 'ticket_group'
    ).order_by('-created_at')

    # Группируем билеты по группам
    groups_dict = {}

    for ticket in all_tickets:
        if ticket.ticket_group:
            group_id = ticket.ticket_group.id
            if group_id not in groups_dict:
                group = ticket.ticket_group
                group_status = 'mixed'

                # Определяем статус группы
                group_tickets = group.tickets.all()
                statuses = set(t.status.code for t in group_tickets if t.status)

                if len(statuses) == 1:
                    group_status = list(statuses)[0]
                elif 'refunded' in statuses and len(statuses) == 2 and 'active' in statuses:
                    group_status = 'partially_refunded'

                groups_dict[group_id] = {
                    'group': group,
                    'movie_title': ticket.screening.movie.title,
                    'movie_poster': ticket.screening.movie.poster,
                    'hall_name': ticket.screening.hall.name,
                    'start_time': ticket.screening.start_time,
                    'purchase_date': group.purchase_date,
                    'screening': ticket.screening,
                    'screening_id': ticket.screening.id,
                    'seats': [],
                    'ticket_count': group.tickets_count,
                    'total_price': group.total_amount,
                    'group_status': group_status,
                    'can_be_downloaded': group_status != 'refunded' or request.user.is_staff,
                    'is_future_screening': ticket.screening.start_time > timezone.now(),
                }

            # Добавляем информацию о месте
            groups_dict[group_id]['seats'].append({
                'row': ticket.seat.row,
                'number': ticket.seat.number,
                'ticket_id': ticket.id,
                'status': ticket.status.code if ticket.status else 'unknown',
                'status_display': ticket.get_status_display()
            })
        else:
            # Билет без группы (старые или одиночные)
            group_id = f"single_{ticket.id}"
            groups_dict[group_id] = {
                'group': None,
                'movie_title': ticket.screening.movie.title,
                'movie_poster': ticket.screening.movie.poster,
                'hall_name': ticket.screening.hall.name,
                'start_time': ticket.screening.start_time,
                'purchase_date': ticket.created_at,
                'screening': ticket.screening,
                'screening_id': ticket.screening.id,
                'seats': [{
                    'row': ticket.seat.row,
                    'number': ticket.seat.number,
                    'ticket_id': ticket.id,
                    'status': ticket.status.code if ticket.status else 'unknown',
                    'status_display': ticket.get_status_display()
                }],
                'ticket_count': 1,
                'total_price': ticket.price,
                'group_status': ticket.status.code if ticket.status else 'unknown',
                'can_be_downloaded': (ticket.status and ticket.status.code != 'refunded') or request.user.is_staff,
                'is_future_screening': ticket.screening.start_time > timezone.now(),
            }

    # Преобразуем словарь в список и сортируем
    ticket_groups = sorted(
        groups_dict.values(),
        key=lambda x: x['purchase_date'],
        reverse=True
    )

    profile_form = UserUpdateForm(instance=request.user)
    email_form = EmailChangeForm(user=request.user)

    if request.method == 'POST':
        form_type = request.POST.get('form_type')

        if form_type == 'profile':
            profile_form = UserUpdateForm(request.POST, instance=request.user)
            if profile_form.is_valid():
                user = profile_form.save()

                OperationLogger.log_operation(
                    request=request,
                    action_type='UPDATE',
                    module_type='USERS',
                    description=f'Обновление профиля пользователя {request.user.email}',
                    object_id=request.user.id,
                    object_repr=str(request.user)
                )

                messages.success(request, 'Ваши данные успешно обновлены!')
                return redirect('profile')
            else:
                for field, errors in profile_form.errors.items():
                    for error in errors:
                        messages.error(request, f'{field}: {error}')

        elif form_type == 'telegram_unlink':
            request.user.unlink_telegram()

            OperationLogger.log_operation(
                request=request,
                action_type='UPDATE',
                module_type='USERS',
                description=f'Отвязка Telegram для пользователя {request.user.email} через сайт',
                object_id=request.user.id,
                object_repr=str(request.user),
                additional_data={'source': 'website'}
            )

            messages.success(request, 'Telegram аккаунт успешно отвязан!')
            return redirect('profile')

        elif form_type == 'email_change':
            email_form = EmailChangeForm(request.POST, user=request.user)
            if email_form.is_valid():
                new_email = email_form.cleaned_data['new_email']
                verification_code = email_form.cleaned_data.get('verification_code')

                if verification_code:
                    # Код подтвержден - меняем email
                    change_request = EmailChangeRequest.objects.filter(
                        user=request.user,
                        new_email=new_email,
                        is_used=False
                    ).order_by('-created_at').first()

                    if change_request and change_request.verification_code == verification_code:
                        old_email = request.user.email
                        request.user.email = new_email
                        request.user.is_email_verified = True
                        request.user.save()

                        change_request.mark_as_used()
                        EmailChangeRequest.objects.filter(user=request.user).delete()

                        OperationLogger.log_operation(
                            request=request,
                            action_type='UPDATE',
                            module_type='USERS',
                            description=f'Успешная смена email с {old_email} на {new_email}',
                            object_id=request.user.id,
                            object_repr=str(request.user)
                        )

                        messages.success(request, 'Email успешно изменен!')
                        return redirect('profile')
                    else:
                        messages.error(request, 'Неверный код подтверждения')
                else:
                    # Отправляем код подтверждения
                    import random
                    import string

                    EmailChangeRequest.objects.filter(user=request.user, new_email=new_email).delete()

                    verification_code = ''.join(random.choices(string.digits, k=6))
                    change_request = EmailChangeRequest.objects.create(
                        user=request.user,
                        new_email=new_email,
                        verification_code=verification_code
                    )

                    try:
                        if send_email_change_verification(request.user, new_email, verification_code):
                            messages.success(
                                request,
                                f'Код подтверждения отправлен на новый email {new_email}. '
                                f'Введите код для завершения смены email.'
                            )
                        else:
                            messages.warning(
                                request,
                                f'Код подтверждения: {verification_code}. '
                                f'Письмо отправлено, но возникли проблемы с доставкой.'
                            )
                    except Exception as e:
                        logger.error(f"Email change verification error: {e}")
                        messages.warning(
                            request,
                            f'Код подтверждения: {verification_code}. '
                            f'Ошибка при отправке email.'
                        )

                    OperationLogger.log_operation(
                        request=request,
                        action_type='UPDATE',
                        module_type='USERS',
                        description=f'Запрос смены email с {request.user.email} на {new_email}',
                        object_id=request.user.id,
                        object_repr=str(request.user)
                    )
            else:
                for field in email_form.errors:
                    if field in email_form.fields:
                        email_form[field].field.widget.attrs['class'] = 'form-control error-field'
                messages.error(request, 'Пожалуйста, исправьте ошибки в форме смены email.')

        elif form_type == 'telegram_connect':
            verification_code = request.user.generate_verification_code()

            OperationLogger.log_operation(
                request=request,
                action_type='OTHER',
                module_type='USERS',
                description=f'Генерация кода привязки Telegram для пользователя {request.user.email}',
                object_id=request.user.id,
                object_repr=str(request.user),
                additional_data={
                    'verification_code': verification_code,
                    'source': 'website'
                }
            )

            messages.success(
                request,
                f'Код для привязки Telegram: {verification_code}. Отправьте его боту @CinemaaPremierBot'
            )
            return redirect('profile')

    telegram_connected = request.user.is_telegram_verified
    telegram_username = request.user.telegram_username

    active_email_change = EmailChangeRequest.objects.filter(
        user=request.user,
        is_used=False
    ).order_by('-created_at').first()

    return render(request, 'ticket/profile.html', {
        'form': profile_form,
        'email_form': email_form,
        'ticket_groups': ticket_groups,
        'telegram_connected': telegram_connected,
        'telegram_username': telegram_username,
        'active_email_change': active_email_change,
    })


# Административные views
@staff_member_required
def movie_manage(request):
    """Управление фильмами"""
    movies = Movie.objects.all().select_related('genre', 'age_rating')
    return render(request, 'ticket/admin/movie_manage.html', {'movies': movies})


@staff_member_required
def movie_add(request):
    """Добавление фильма"""
    if request.method == 'POST':
        form = MovieForm(request.POST, request.FILES)
        if form.is_valid():
            movie = form.save()

            OperationLogger.log_operation(
                request=request,
                action_type='CREATE',
                module_type='MOVIES',
                description=f'Создан новый фильм: {movie.title}',
                object_id=movie.pk,
                object_repr=str(movie),
                additional_data={
                    'genre': movie.genre.name,
                    'age_rating': str(movie.age_rating)
                }
            )

            messages.success(request, f'Фильм "{movie.title}" успешно добавлен.')
            return redirect('movie_manage')
    else:
        form = MovieForm()
    return render(request, 'ticket/admin/movie_form.html', {'form': form})


@staff_member_required
def movie_edit(request, movie_id):
    """Редактирование фильма"""
    movie = get_object_or_404(Movie, pk=movie_id)
    if request.method == 'POST':
        form = MovieForm(request.POST, request.FILES, instance=movie)
        if form.is_valid():
            movie = form.save()

            OperationLogger.log_operation(
                request=request,
                action_type='UPDATE',
                module_type='MOVIES',
                description=f'Обновлен фильм: {movie.title}',
                object_id=movie.pk,
                object_repr=str(movie)
            )

            messages.success(request, f'Фильм "{movie.title}" успешно обновлен.')
            return redirect('movie_manage')
    else:
        form = MovieForm(instance=movie)
    return render(request, 'ticket/admin/movie_form.html', {'form': form})


@staff_member_required
def movie_delete(request, movie_id):
    """Удаление фильма"""
    movie = get_object_or_404(Movie, pk=movie_id)
    if request.method == 'POST':
        OperationLogger.log_operation(
            request=request,
            action_type='DELETE',
            module_type='MOVIES',
            description=f'Удален фильм: {movie.title}',
            object_id=movie.pk,
            object_repr=str(movie)
        )

        movie.delete()
        messages.success(request, f'Фильм "{movie.title}" успешно удален.')
        return redirect('movie_manage')
    return render(request, 'ticket/admin/movie_confirm_delete.html', {'movie': movie})


@staff_member_required
def hall_manage(request):
    """Управление залами"""
    halls = Hall.objects.all().select_related('hall_type')
    return render(request, 'ticket/admin/hall_manage.html', {'halls': halls})


@staff_member_required
def hall_add(request):
    """Добавление зала"""
    if request.method == 'POST':
        form = HallForm(request.POST)
        if form.is_valid():
            hall = form.save()

            OperationLogger.log_operation(
                request=request,
                action_type='CREATE',
                module_type='HALLS',
                description=f'Создан новый зал: {hall.name}',
                object_id=hall.pk,
                object_repr=str(hall),
                additional_data={
                    'hall_type': hall.hall_type.name,
                    'rows': hall.rows,
                    'seats_per_row': hall.seats_per_row,
                    'total_seats': hall.rows * hall.seats_per_row
                }
            )

            messages.success(request, f'Зал "{hall.name}" успешно добавлен.')
            return redirect('hall_manage')
    else:
        form = HallForm()
    return render(request, 'ticket/admin/hall_form.html', {'form': form})


@staff_member_required
def hall_edit(request, hall_id):
    """Редактирование зала"""
    hall = get_object_or_404(Hall, pk=hall_id)
    if request.method == 'POST':
        form = HallForm(request.POST, instance=hall)
        if form.is_valid():
            hall = form.save()

            OperationLogger.log_operation(
                request=request,
                action_type='UPDATE',
                module_type='HALLS',
                description=f'Обновлен зал: {hall.name}',
                object_id=hall.pk,
                object_repr=str(hall)
            )

            messages.success(request, f'Зал "{hall.name}" успешно обновлен.')
            return redirect('hall_manage')
    else:
        form = HallForm(instance=hall)
    return render(request, 'ticket/admin/hall_form.html', {'form': form})


@staff_member_required
def hall_delete(request, hall_id):
    """Удаление зала"""
    hall = get_object_or_404(Hall, pk=hall_id)
    if request.method == 'POST':
        OperationLogger.log_operation(
            request=request,
            action_type='DELETE',
            module_type='HALLS',
            description=f'Удален зал: {hall.name}',
            object_id=hall.pk,
            object_repr=str(hall)
        )

        hall.delete()
        messages.success(request, f'Зал "{hall.name}" успешно удален.')
        return redirect('hall_manage')
    return render(request, 'ticket/admin/hall_confirm_delete.html', {'hall': hall})


@staff_member_required
def screening_manage(request):
    """Управление сеансами"""
    screenings = Screening.objects.all().select_related('movie', 'hall', 'hall__hall_type')
    return render(request, 'ticket/admin/screening_manage.html', {'screenings': screenings})


@staff_member_required
def screening_add(request):
    """Добавление сеанса"""
    if request.method == 'POST':
        form = ScreeningForm(request.POST)
        if form.is_valid():
            screening = form.save(commit=False)
            if screening.movie and screening.start_time:
                duration_timedelta = timedelta(minutes=screening.movie.duration)
                screening.end_time = screening.start_time + duration_timedelta + timedelta(minutes=10)
                screening.ticket_price = screening.calculate_ticket_price()
            screening.save()

            OperationLogger.log_operation(
                request=request,
                action_type='CREATE',
                module_type='SCREENINGS',
                description=f'Создан новый сеанс: {screening.movie.title} в {screening.hall.name}',
                object_id=screening.pk,
                object_repr=str(screening),
                additional_data={
                    'movie': screening.movie.title,
                    'hall': screening.hall.name,
                    'start_time': screening.start_time.strftime('%d.%m.%Y %H:%M'),
                    'price': str(screening.ticket_price)
                }
            )

            messages.success(request, f'Сеанс успешно добавлен.')
            return redirect('screening_manage')
    else:
        form = ScreeningForm()
    return render(request, 'ticket/admin/screening_form.html', {'form': form})


@staff_member_required
def screening_edit(request, screening_id):
    """Редактирование сеанса"""
    screening = get_object_or_404(Screening, pk=screening_id)
    if request.method == 'POST':
        form = ScreeningForm(request.POST, instance=screening)
        if form.is_valid():
            updated_screening = form.save(commit=False)
            if updated_screening.movie and updated_screening.start_time:
                duration_timedelta = timedelta(minutes=updated_screening.movie.duration)
                updated_screening.end_time = updated_screening.start_time + duration_timedelta + timedelta(minutes=10)

            old_hall = screening.hall
            old_start_time = screening.start_time

            if (updated_screening.hall != old_hall) or (updated_screening.start_time != old_start_time):
                updated_screening.ticket_price = updated_screening.calculate_ticket_price()

            updated_screening.save()

            OperationLogger.log_operation(
                request=request,
                action_type='UPDATE',
                module_type='SCREENINGS',
                description=f'Обновлен сеанс: {screening.movie.title} в {screening.hall.name}',
                object_id=screening.pk,
                object_repr=str(screening),
                additional_data={
                    'old_price': str(screening.ticket_price),
                    'new_price': str(updated_screening.ticket_price),
                    'price_recalculated': updated_screening.ticket_price != screening.ticket_price
                }
            )

            messages.success(request, f'Сеанс успешно обновлен.')
            return redirect('screening_manage')
    else:
        form = ScreeningForm(instance=screening)
    return render(request, 'ticket/admin/screening_form.html', {'form': form})


@staff_member_required
def screening_delete(request, screening_id):
    """Удаление сеанса"""
    screening = get_object_or_404(Screening, pk=screening_id)
    if request.method == 'POST':
        OperationLogger.log_operation(
            request=request,
            action_type='DELETE',
            module_type='SCREENINGS',
            description=f'Удален сеанс: {screening.movie.title} в {screening.hall.name}',
            object_id=screening.pk,
            object_repr=str(screening)
        )

        screening.delete()
        messages.success(request, f'Сеанс успешно удален.')
        return redirect('screening_manage')
    return render(request, 'ticket/admin/screening_confirm_delete.html', {'screening': screening})


def screening_partial(request, screening_id):
    """Возвращает HTML для частичной информации о сеансе"""
    screening = get_object_or_404(
        Screening.objects.select_related('movie', 'hall'),
        pk=screening_id
    )

    booked_tickets = Ticket.objects.filter(screening=screening)
    booked_seat_ids = [ticket.seat.id for ticket in booked_tickets]

    seats = Seat.objects.filter(hall=screening.hall).order_by('row', 'number')

    rows = {}
    for seat in seats:
        if seat.row not in rows:
            rows[seat.row] = []
        rows[seat.row].append(seat)

    return render(request, 'ticket/screening_partial.html', {
        'screening': screening,
        'rows': rows,
        'booked_seat_ids': booked_seat_ids
    })


def password_reset_request(request):
    """Шаг 1: Запрос на восстановление пароля"""
    from .forms import PasswordResetRequestForm

    if request.method == 'POST':
        form = PasswordResetRequestForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            logger.info(f"Password reset requested for email: {email}")

            try:
                user = User.objects.get(email=email, is_email_verified=True)
                logger.info(f"User found: {user.name} {user.surname}")

                # Удаляем старые запросы для этого пользователя
                PasswordResetRequest.objects.filter(user=user).delete()

                # Генерируем код восстановления
                import random
                import string
                reset_code = ''.join(random.choices(string.digits, k=6))
                logger.info(f"Generated reset code: {reset_code}")

                reset_request = PasswordResetRequest.objects.create(
                    user=user,
                    reset_code=reset_code
                )

                OperationLogger.log_operation(
                    request=request,
                    action_type='OTHER',
                    module_type='AUTH',
                    description=f'Запрос восстановления пароля для {email}',
                    additional_data={'reset_code': reset_code}
                )

                logger.info(f"Attempting to send email to {email}")
                if send_password_reset_email(user, reset_code):
                    request.session['password_reset_email'] = email
                    messages.success(request, f'Код восстановления отправлен на email {email}')
                    logger.info(f"Email sent successfully to {email}")
                    return redirect('password_reset_code')
                else:
                    messages.error(request, 'Ошибка при отправке кода. Попробуйте позже.')
                    logger.error(f"Failed to send email to {email}")

            except User.DoesNotExist:
                logger.warning(f"User not found for email: {email}")
                messages.success(request, 'Если email зарегистрирован, код восстановления будет отправлен')
                return redirect('password_reset_code')

    else:
        form = PasswordResetRequestForm()

    return render(request, 'ticket/password_reset_request.html', {'form': form})


def password_reset_code(request):
    """Шаг 2: Ввод кода подтверждения"""
    from .forms import PasswordResetCodeForm

    email = request.session.get('password_reset_email')
    logger.info(f"Password reset code page - Email from session: {email}")

    if not email:
        messages.error(request, 'Сессия истекла. Начните восстановление пароля заново.')
        return redirect('password_reset_request')

    try:
        user = User.objects.get(email=email, is_email_verified=True)
        reset_request = PasswordResetRequest.objects.filter(
            user=user,
            is_used=False
        ).order_by('-created_at').first()

        if not reset_request:
            messages.error(request, 'Запрос на восстановление не найден. Начните заново.')
            return redirect('password_reset_request')

    except (User.DoesNotExist, PasswordResetRequest.DoesNotExist):
        messages.error(request, 'Запрос на восстановление не найден. Начните заново.')
        return redirect('password_reset_request')

    if reset_request.is_expired():
        reset_request.delete()
        messages.error(request, 'Время действия кода истекло. Начните заново.')
        return redirect('password_reset_request')

    if request.method == 'POST':
        form = PasswordResetCodeForm(request.POST)
        if form.is_valid():
            code = form.cleaned_data['reset_code']

            logger.info(f"Entered code: {code}, Expected code: {reset_request.reset_code}")

            if reset_request.reset_code == code:
                reset_request.mark_as_used()
                request.session['password_reset_verified'] = True
                messages.success(request, 'Код подтвержден. Установите новый пароль.')
                return redirect('password_reset_confirm')
            else:
                messages.error(request, 'Неверный код подтверждения')
                logger.error(f"Code mismatch. Expected: {reset_request.reset_code}, Got: {code}")
    else:
        form = PasswordResetCodeForm()

    return render(request, 'ticket/password_reset_code.html', {
        'form': form,
        'email': email
    })


def password_reset_confirm(request):
    """Шаг 3: Установка нового пароля"""
    email = request.session.get('password_reset_email')
    verified = request.session.get('password_reset_verified')

    if not email or not verified:
        messages.error(request, 'Сессия истекла. Начните восстановление пароля заново.')
        return redirect('password_reset_request')

    try:
        user = User.objects.get(email=email, is_email_verified=True)
    except User.DoesNotExist:
        messages.error(request, 'Пользователь не найден.')
        return redirect('password_reset_request')

    if request.method == 'POST':
        form = PasswordResetForm(request.POST)
        if form.is_valid():
            new_password = form.cleaned_data['new_password1']
            user.set_password(new_password)
            user.save()

            OperationLogger.log_operation(
                request=request,
                action_type='UPDATE',
                module_type='AUTH',
                description=f'Успешное восстановление пароля для {email}',
                object_id=user.id,
                object_repr=str(user)
            )

            request.session.pop('password_reset_email', None)
            request.session.pop('password_reset_verified', None)

            PasswordResetRequest.objects.filter(user=user).delete()

            messages.success(request, 'Пароль успешно изменен! Теперь вы можете войти в систему.')
            return redirect('login')
    else:
        form = PasswordResetForm()

    return render(request, 'ticket/password_reset_confirm.html', {
        'form': form,
        'email': email
    })


def about(request):
    """Страница 'О кинотеатре' с руководством пользователя"""
    from django.db.models import Count

    halls = Hall.objects.annotate(
        total_seats=Count('seats'),
        total_screenings=Count('screenings', distinct=True)
    ).select_related('hall_type')

    total_movies = Movie.objects.count()

    today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    total_screenings_today = Screening.objects.filter(
        start_time__gte=timezone.now(),
        start_time__date=timezone.now().date()
    ).count()

    total_screenings_all = Screening.objects.count()

    context = {
        'halls': halls,
        'total_movies': total_movies,
        'total_screenings_today': total_screenings_today,
        'total_screenings_all': total_screenings_all,
        'cinema_info': {
            'name': 'Кинотеатр Премьера',
            'description': 'Современный кинотеатр с комфортными залами и новейшим оборудованием',
            'features': [
                'Цифровое качество изображения 4K',
                'Объемный звук Dolby Atmos',
                'Комфортные кресла с откидными подлокотниками',
                'Система кондиционирования',
                'Доступная среда для людей с ограниченными возможностями'
            ],
            'working_hours': 'Ежедневно с 8:00 до 24:00'
        }
    }

    return render(request, 'ticket/about.html', context)


@login_required
@require_POST
def request_ticket_refund(request, ticket_id):
    """Автоматический возврат билета с проверкой условий"""
    ticket = get_object_or_404(Ticket, id=ticket_id, user=request.user)

    OperationLogger.log_operation(
        request=request,
        action_type='UPDATE',
        module_type='TICKETS',
        description=f'Попытка возврата билета #{ticket_id}',
        object_id=ticket.id,
        object_repr=str(ticket),
        additional_data={
            'movie': ticket.screening.movie.title,
            'screening_time': ticket.screening.start_time.isoformat(),
            'seat': f"Ряд {ticket.seat.row}, Место {ticket.seat.number}",
            'current_status': ticket.status.code if ticket.status else 'unknown'
        }
    )

    success, message = ticket.request_refund()

    if success:
        OperationLogger.log_operation(
            request=request,
            action_type='UPDATE',
            module_type='TICKETS',
            description=f'Успешный возврат билета #{ticket_id}',
            object_id=ticket.id,
            object_repr=str(ticket),
            additional_data={
                'movie': ticket.screening.movie.title,
                'refund_amount': float(ticket.price),
                'refund_time': ticket.refund_processed_at.isoformat() if ticket.refund_processed_at else None
            }
        )

        messages.success(request, message)
    else:
        messages.error(request, f'❌ {message}')

    return redirect('profile')


@login_required
@require_POST
def cancel_refund_request(request, ticket_id):
    """Отмена запроса на возврат"""
    ticket = get_object_or_404(Ticket, id=ticket_id, user=request.user)

    success, message = ticket.cancel_refund_request()

    if success:
        OperationLogger.log_operation(
            request=request,
            action_type='UPDATE',
            module_type='TICKETS',
            description=f'Отмена запроса возврата билета #{ticket_id}',
            object_id=ticket.id,
            object_repr=str(ticket)
        )

        messages.success(request, 'Запрос на возврат отменен.')
    else:
        messages.error(request, f'Не удалось отменить возврат: {message}')

    return redirect('profile')


def calculate_screening_price(request):
    """AJAX endpoint для расчета цены"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            hall_id = data.get('hall_id')
            time_str = data.get('time', '')

            hall = Hall.objects.select_related('hall_type').get(id=hall_id)
            hour = int(time_str.split(':')[0]) if ':' in time_str else 12

            base_price = hall.hall_type.base_price
            coefficient = hall.hall_type.price_coefficient

            if 8 <= hour < 12:
                multiplier = 0.7
            elif 12 <= hour < 16:
                multiplier = 0.9
            elif 16 <= hour < 20:
                multiplier = 1.2
            else:
                multiplier = 1.4

            final_price = int(base_price * float(coefficient) * multiplier)

            return JsonResponse({
                'success': True,
                'price': final_price,
                'calculation': f'{base_price} × {coefficient} × {multiplier} = {final_price} руб.'
            })
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Invalid request method'})


def generate_report(request):
    """Генерация отчета"""
    report_type = request.GET.get('report_type')
    period = request.GET.get('period', 'daily')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')

    report_data = None

    if report_type == 'movies':
        report_data = ReportGenerator.get_popular_movies(
            start_date=start_date,
            end_date=end_date
        )
    elif report_type == 'halls':
        report_data = ReportGenerator.get_hall_occupancy(
            start_date=start_date,
            end_date=end_date
        )
    elif report_type == 'sales':
        report_data = ReportGenerator.get_sales_statistics(
            start_date=start_date,
            end_date=end_date
        )
    elif report_type == 'revenue':
        report_data = ReportGenerator.get_revenue_stats(
            period=period,
            start_date=start_date,
            end_date=end_date
        )

    return render(request, 'ticket/admin/reports.html', {
        'report_data': report_data,
        'report_type': report_type,
        'filters': {
            'period': period,
            'start_date': start_date,
            'end_date': end_date
        }
    })