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
from django.http import JsonResponse
from .forms import DirectorForm, ActorForm
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from .forms import DirectorForm, ActorForm
from django.views.decorators.csrf import csrf_exempt
from .payment_service import YooKassaService
from .models import Payment
from django.core.files.base import ContentFile

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
    MovieDirector, MovieActor, Genre, MovieGenre, PriceHistory
)
from .utils import generate_enhanced_ticket_pdf, generate_ticket_pdf
from .report_utils import ReportGenerator
from .logging_utils import OperationLogger
from decimal import Decimal
from django.contrib.auth.decorators import user_passes_test
from django.db.models import Count, Sum, Q, Avg, F
from django.db.models.functions import TruncDate, TruncWeek, TruncMonth
from datetime import datetime, timedelta
from django.utils import timezone

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
                    logger.info(f"Email sent successfully to {email}")
                else:
                    messages.warning(request, f'Не удалось отправить письмо. Ваш код подтверждения: {verification_code}')
            except Exception as e:
                logger.error(f"Email sending error: {e}")
                messages.warning(request, f'Ошибка отправки. Ваш код подтверждения: {verification_code}')

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

    storage = messages.get_messages(request)
    storage.used = True

    email_sent_message = request.session.pop('email_sent_message', None)
    if email_sent_message:
        messages.success(request, email_sent_message)

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

    date_param = request.GET.get('date', '')

    if date_param and date_param.strip():
        try:
            selected_date = datetime.strptime(date_param, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            selected_date = today
    else:
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
        'screenings__hall', 'genres'
    ).select_related('age_rating').all()

    movies = movies.filter(
        screenings__start_time__gt=local_now
    ).distinct()

    # Применяем текстовые фильтры
    if search_query:
        movies = movies.filter(
            Q(title__icontains=search_query) |
            Q(description__icontains=search_query)
        )

    if genre_filter:
        movies = movies.filter(genres__name=genre_filter)

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
        Movie.objects.select_related('age_rating').prefetch_related('directors', 'actors', 'genres'),
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

    # Для первого сеанса нужно подготовить данные о местах
    first_screening = upcoming_screenings.first()
    first_screening_rows = {}
    first_screening_booked_seat_ids = []

    if first_screening:
        # Получаем места для первого сеанса
        seats = Seat.objects.filter(hall=first_screening.hall).order_by('row', 'number')
        booked_tickets = Ticket.objects.filter(screening=first_screening, status__code='active')
        first_screening_booked_seat_ids = [ticket.seat.id for ticket in booked_tickets]

        # Группируем места по рядам
        for seat in seats:
            if seat.row not in first_screening_rows:
                first_screening_rows[seat.row] = []
            first_screening_rows[seat.row].append(seat)

    return render(request, 'ticket/movie_detail.html', {
        'movie': movie,
        'upcoming_screenings': upcoming_screenings,
        'past_screenings': past_screenings,
        'first_screening_rows': first_screening_rows,
        'first_screening_booked_seat_ids': first_screening_booked_seat_ids,
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
        'genres',
        'age_rating'
    ).get(pk=screening.movie.id)

    seats = Seat.objects.filter(hall=screening.hall).order_by('row', 'number')

    # Получаем все билеты на этот сеанс
    booked_tickets = Ticket.objects.filter(screening=screening, status__code='active')
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
    """Создание бронирования и переход к оплате"""
    screening_id = request.POST.get('screening_id')
    selected_seats = request.POST.get('selected_seats')

    if not selected_seats:
        messages.error(request, "Выберите хотя бы одно место.")
        return redirect('screening_detail', screening_id=screening_id)

    try:
        seat_ids = json.loads(selected_seats)
    except json.JSONDecodeError:
        messages.error(request, "Ошибка при обработке выбранных мест.")
        return redirect('screening_detail', screening_id=screening_id)

    if not seat_ids:
        messages.error(request, "Выберите хотя бы одно место.")
        return redirect('screening_detail', screening_id=screening_id)

    screening = get_object_or_404(Screening, pk=screening_id)

    # Проверяем доступность мест
    for seat_id in seat_ids:
        seat = get_object_or_404(Seat, pk=seat_id)
        if Ticket.objects.filter(screening=screening, seat=seat, status__code='active').exists():
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
        tickets_count=len(seat_ids),
        payment_status='pending_payment'
    )

    # Создаем билеты
    for seat_id in seat_ids:
        seat = get_object_or_404(Seat, pk=seat_id)
        Ticket.objects.create(
            user=request.user,
            screening=screening,
            seat=seat,
            price=screening.ticket_price,
            status=active_status,
            ticket_group=ticket_group
        )

    # Логируем создание бронирования
    OperationLogger.log_operation(
        request=request,
        action_type='CREATE',
        module_type='TICKETS',
        description=f'Создано бронирование на {len(seat_ids)} билетов',
        object_id=ticket_group.id,
        object_repr=str(ticket_group),
        additional_data={
            'screening_id': screening_id,
            'movie': screening.movie.title,
            'seats_count': len(seat_ids),
            'total_amount': float(ticket_group.total_amount),
            'group_uuid': str(ticket_group.group_uuid)
        }
    )

    # Формируем URL для возврата после оплаты
    return_url = request.build_absolute_uri(
        reverse('payment_result', args=[ticket_group.group_uuid])
    )

    # Создаём платёж в YooKassa
    try:
        payment_result = YooKassaService.create_payment(ticket_group, return_url)

        # Логируем успешное создание
        logger.info(f"Платёж создан: {payment_result['payment_id']}")

        # Редирект на страницу оплаты YooKassa
        return redirect(payment_result['confirmation_url'])

    except Exception as e:
        logger.error(f"Ошибка создания платежа: {e}")
        messages.error(request, "Произошла ошибка при создании платежа. Попробуйте позже.")
        return redirect('screening_detail', screening_id=screening_id)


def payment_result(request, group_uuid):
    """Страница результата оплаты (после возврата из YooKassa)"""
    ticket_group = get_object_or_404(
        TicketGroup.objects.select_related('screening__movie', 'screening__hall'),
        group_uuid=group_uuid,
        user=request.user
    )

    try:
        payment = Payment.objects.get(ticket_group=ticket_group)

        # Проверяем статус платежа в YooKassa
        result = YooKassaService.check_payment(payment.payment_id)

        if result['status'] == 'succeeded':
            # Успешная оплата
            context = {
                'ticket_group': ticket_group,
                'payment': payment,
                'success': True
            }

            # Логируем
            OperationLogger.log_operation(
                request=request,
                action_type='VIEW',
                module_type='TICKETS',
                description=f'Успешная оплата через YooKassa',
                object_id=payment.id,
                object_repr=str(payment),
                additional_data={
                    'payment_id': payment.payment_id,
                    'amount': float(payment.amount),
                    'group_uuid': str(group_uuid)
                }
            )

            # Отправляем чек на почту
            try:
                from .email_utils import send_ticket_receipt
                email_sent = send_ticket_receipt(request.user, ticket_group, payment)
                if email_sent:
                    logger.info(f"Чек отправлен на почту {request.user.email}")
                else:
                    logger.warning(f"Не удалось отправить чек на почту {request.user.email}")
            except Exception as e:
                logger.error(f"Ошибка отправки чека: {e}")

            return render(request, 'ticket/payment_success.html', context)
        else:
            # Платёж не завершён или отменён
            context = {
                'ticket_group': ticket_group,
                'payment': payment,
                'success': False,
                'status': result['status']
            }
            return render(request, 'ticket/payment_result.html', context)

    except Payment.DoesNotExist:
        messages.error(request, 'Платёж не найден')
        return redirect('home')


@csrf_exempt
def yookassa_webhook(request):
    """
    Webhook для получения уведомлений от YooKassa
    Не требует CSRF-токена
    """
    if request.method != 'POST':
        return HttpResponse(status=405)

    try:
        # Получаем данные уведомления
        notification = json.loads(request.body)
        logger.info(f"📨 Получен webhook от YooKassa: {notification.get('event')}")

        event = notification.get('event')
        payment_data = notification.get('object', {})
        payment_id = payment_data.get('id')

        if event == 'payment.succeeded':
            logger.info(f"✅ Webhook: платёж {payment_id} успешен")

            # Обновляем статус через сервис
            YooKassaService.check_payment(payment_id)

        elif event == 'payment.canceled':
            logger.info(f"❌ Webhook: платёж {payment_id} отменён")

            # Обновляем статус
            from .models import Payment
            try:
                payment = Payment.objects.get(payment_id=payment_id)
                payment.status = 'canceled'
                payment.payment_data = payment_data
                payment.save()

                # Отменяем группу билетов
                ticket_group = payment.ticket_group
                ticket_group.payment_status = 'canceled'
                ticket_group.save()
            except Payment.DoesNotExist:
                pass

        return HttpResponse(status=200)

    except Exception as e:
        logger.error(f"❌ Ошибка обработки webhook: {e}")
        return HttpResponse(status=500)


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

    # Если билет входит в группу — фильтруем только невозвращённые
    if ticket.ticket_group:
        tickets = Ticket.objects.filter(
            ticket_group=ticket.ticket_group,
            user=request.user
        ).exclude(status__code='refunded')
    else:
        tickets = [ticket]

    if not tickets:
        messages.error(request, 'Все билеты в этой группе возвращены')
        return redirect('profile')

    # Логирование
    try:
        from .models import ActionType, ModuleType
        action_type = ActionType.objects.get(code='EXPORT')
        module_type = ModuleType.objects.get(code='TICKETS')
        OperationLogger.log_operation(
            request=request,
            action_type=action_type,
            module_type=module_type,
            description=f'Скачивание PDF билета для фильма {ticket.screening.movie.title}',
            object_id=ticket.id,
            object_repr=str(ticket),
            additional_data={
                'format': 'PDF',
                'movie': ticket.screening.movie.title,
                'ticket_count': len(tickets),
                'group_id': str(ticket.ticket_group.group_uuid) if ticket.ticket_group else None,
                'status': ticket.status.code if ticket.status else 'unknown',
            }
        )
    except Exception as e:
        logger.error(f"Logging error: {e}")

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
        messages.error(request, f"Ошибка при генерации билета: {str(e)}")
        return redirect('profile')


@login_required
def download_ticket_group(request, group_id):
    """Скачивание группы билетов по UUID"""
    try:
        ticket_group = TicketGroup.objects.get(group_uuid=group_id, user=request.user)
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

    # ИСПРАВЛЕНИЕ 1: Получаем объекты ActionType и ModuleType для логирования
    try:
        from .models import ActionType, ModuleType
        action_type = ActionType.objects.get(code='EXPORT')
        module_type = ModuleType.objects.get(code='TICKETS')

        # ЛОГИРОВАНИЕ СКАЧИВАНИЯ PDF ГРУППЫ
        OperationLogger.log_operation(
            request=request,
            action_type=action_type,  # Передаём объект, а не строку
            module_type=module_type,  # Передаём объект, а не строку
            description=f'Скачивание PDF группы билетов для фильма {tickets[0].screening.movie.title}',
            object_id=tickets[0].id,
            object_repr=f"Группа билетов {group_id}",
            additional_data={
                'format': 'PDF',
                'movie': tickets[0].screening.movie.title,
                'ticket_count': len(tickets),
                'group_id': group_id,
                'has_refunded_tickets': has_refunded_tickets
            }
        )
    except Exception as e:
        logger.error(f"Logging error: {e}")
        # Продолжаем выполнение даже если логирование не удалось

    try:
        pdf_buffer = generate_enhanced_ticket_pdf(tickets)
        response = HttpResponse(pdf_buffer.getvalue(), content_type='application/pdf')
        filename = f"билет_{tickets[0].screening.movie.title}_{group_id[:8]}.pdf"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
    except Exception as e:
        logger.error(f"Ошибка генерации PDF: {str(e)}")
        messages.error(request, f"Ошибка при генерации билета: {str(e)}")
        return redirect('profile')


@login_required
def profile(request):
    """Профиль пользователя"""
    # Получаем все билеты пользователя (исключаем archived)
    all_tickets = Ticket.objects.filter(
        user=request.user
    ).exclude(
        status__code='archived'
    ).select_related(
        'screening__movie', 'screening__hall', 'seat', 'status', 'ticket_group'
    ).order_by('-created_at')

    # Группируем билеты по группам
    groups_dict = {}

    for ticket in all_tickets:
        if ticket.status and ticket.status.code == 'active':
            if ticket.update_status_if_passed():
                ticket.refresh_from_db()
        if ticket.ticket_group:
            group_id = ticket.ticket_group.id
            if group_id not in groups_dict:
                group = ticket.ticket_group

                # Определяем статус группы: только active, used, refunded
                group_tickets = group.tickets.exclude(status__code='archived')
                status_codes = set(t.status.code for t in group_tickets if t.status)

                # Приоритет: active > used > refunded
                if 'active' in status_codes:
                    group_status = 'active'
                elif 'used' in status_codes:
                    group_status = 'used'
                elif 'refunded' in status_codes:
                    group_status = 'refunded'
                else:
                    group_status = 'unknown'

                # Статус-маппинг для отображения
                status_map = dict(TicketStatus.objects.filter(
                    code__in=['active', 'used', 'refunded']
                ).values_list('code', 'name'))

                groups_dict[group_id] = {
                    'group': group,
                    'group_uuid': group.group_uuid,
                    'movie_title': ticket.screening.movie.title,
                    'movie_poster': ticket.screening.movie.poster,
                    'hall_name': ticket.screening.hall.name,
                    'start_time': ticket.screening.start_time,
                    'purchase_date': group.purchase_date,
                    'screening': ticket.screening,
                    'screening_id': ticket.screening.id,
                    'seats': [],
                    'ticket_count': group_tickets.count(),
                    'total_price': group.total_amount,
                    'group_status': group_status,
                    'status_display': status_map.get(group_status, group_status),
                    'can_be_downloaded': group_status in ('active', 'used') or request.user.is_staff,
                    'can_be_refunded': group_status == 'active',
                    'is_future_screening': ticket.screening.start_time > timezone.now(),
                    'first_ticket_id': None,
                    'refund_processed_at': None,
                    'refund_message': 'Возврат возможен за 30 минут до сеанса',
                }

            # Добавляем информацию о месте (только не archived)
            if ticket.status and ticket.status.code != 'archived':
                groups_dict[group_id]['seats'].append({
                    'row': ticket.seat.row,
                    'number': ticket.seat.number,
                    'ticket_id': ticket.id,
                    'status': ticket.status.code if ticket.status else 'unknown',
                    'status_display': ticket.get_status_display() if hasattr(ticket, 'get_status_display') else ticket.status.name if ticket.status else 'Неизвестно'
                })

            # Запоминаем первый ticket_id для возврата (только активные)
            if groups_dict[group_id]['first_ticket_id'] is None and ticket.status and ticket.status.code == 'active':
                groups_dict[group_id]['first_ticket_id'] = ticket.id

            # Запоминаем дату возврата если есть
            if ticket.refund_processed_at and not groups_dict[group_id]['refund_processed_at']:
                groups_dict[group_id]['refund_processed_at'] = ticket.refund_processed_at
        else:
            # Билет без группы (исключаем archived)
            if ticket.status and ticket.status.code == 'archived':
                continue

            group_id = f"single_{ticket.id}"
            ticket_code = ticket.status.code if ticket.status else 'unknown'
            status_map = dict(TicketStatus.objects.filter(
                code__in=['active', 'used', 'refunded']
            ).values_list('code', 'name'))

            groups_dict[group_id] = {
                'group': None,
                'group_uuid': None,
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
                    'status': ticket_code,
                    'status_display': status_map.get(ticket_code, ticket.status.name if ticket.status else 'Неизвестно')
                }],
                'ticket_count': 1,
                'total_price': ticket.price,
                'group_status': ticket_code,
                'status_display': status_map.get(ticket_code, ticket.status.name if ticket.status else 'Неизвестно'),
                'can_be_downloaded': ticket_code in ('active', 'used') or request.user.is_staff,
                'can_be_refunded': ticket_code == 'active',
                'is_future_screening': ticket.screening.start_time > timezone.now(),
                'first_ticket_id': ticket.id,
                'refund_processed_at': ticket.refund_processed_at,
                'refund_message': 'Возврат возможен за 30 минут до сеанса',
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

    active_email_change = EmailChangeRequest.objects.filter(
        user=request.user,
        is_used=False
    ).order_by('-created_at').first()

    return render(request, 'ticket/profile.html', {
        'form': profile_form,
        'email_form': email_form,
        'ticket_groups': ticket_groups,
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
                    'genres': ", ".join(g.name for g in movie.genres.all()),
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
            old_price = screening.ticket_price

            if (updated_screening.hall != old_hall) or (updated_screening.start_time != old_start_time):
                updated_screening.ticket_price = updated_screening.calculate_ticket_price()

            updated_screening.save()

            if updated_screening.ticket_price != old_price:
                PriceHistory.objects.create(
                    screening=updated_screening,
                    old_price=old_price,
                    new_price=updated_screening.ticket_price,
                    changed_by=request.user,
                    reason='Изменение через админ-панель'
                )
                OperationLogger.log_price_change(
                    updated_screening, old_price, updated_screening.ticket_price,
                    request.user
                )

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

    booked_tickets = Ticket.objects.filter(screening=screening, status__code='active')
    booked_seat_ids = [ticket.seat.id for ticket in booked_tickets]

    seats = Seat.objects.filter(hall=screening.hall).order_by('row', 'number')

    rows = {}
    for seat in seats:
        if seat.row not in rows:
            rows[seat.row] = []
        rows[seat.row].append(seat)

    # Добавляем отладочную информацию
    print(f"DEBUG: screening_id={screening_id}, rows count={len(rows)}, total seats={seats.count()}")
    for row_num, row_seats in rows.items():
        print(f"  Row {row_num}: {len(row_seats)} seats")

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


def is_manager(user):
    """Проверка, является ли пользователь менеджером или staff"""
    return user.is_authenticated and (user.is_staff or user.groups.filter(name='Manager').exists())


# ═══════════════════════════════════════════════
# API ДЛЯ ИМПОРТА ОДНОГО ФИЛЬМА ИЗ API
# ═══════════════════════════════════════════════

@user_passes_test(is_manager, login_url='login')
def search_movie_api(request):
    """Поиск фильма по названию через API (GET запрос)"""
    query = request.GET.get('query', '').strip()

    if not query or len(query) < 2:
        return JsonResponse({
            'success': False,
            'message': 'Введите минимум 2 символа для поиска'
        })

    try:
        from .tmdb_client import KinopoiskDevClient
        client = KinopoiskDevClient()

        result = client.search_movies(query, page=1, limit=10)

        if not result or 'docs' not in result:
            return JsonResponse({
                'success': False,
                'message': 'Ничего не найдено или ошибка API'
            })

        movies = []
        for movie in result.get('docs', []):
            # Проверяем, есть ли уже в БД
            title = movie.get('name', '')
            existing = Movie.objects.filter(title__iexact=title).first()

            movies.append({
                'id': movie.get('id'),
                'title': title,
                'year': movie.get('year'),
                'duration': movie.get('movieLength'),
                'description': (movie.get('shortDescription') or movie.get('description', ''))[:200],
                'poster': movie.get('poster', {}).get('url') or movie.get('poster', {}).get('previewUrl') if isinstance(movie.get('poster'), dict) else None,
                'rating_kp': movie.get('rating', {}).get('kp') if isinstance(movie.get('rating'), dict) else None,
                'genres': [g.get('name', '') for g in movie.get('genres', [])],
                'exists_in_db': existing is not None,
                'existing_id': existing.id if existing else None,
            })

        return JsonResponse({
            'success': True,
            'movies': movies,
            'total': len(movies),
            'remaining_requests': get_remaining_requests_info()
        })

    except Exception as e:
        logger.error(f"Ошибка поиска фильма: {e}")
        return JsonResponse({
            'success': False,
            'message': f'Ошибка поиска: {str(e)}'
        })


@user_passes_test(is_manager, login_url='login')
@require_POST
def import_single_movie_api(request):
    """Импорт одного фильма по ID из API"""
    import json
    data = json.loads(request.body)
    movie_id = data.get('movie_id')
    download_poster = data.get('download_poster', True)

    if not movie_id:
        return JsonResponse({
            'success': False,
            'message': 'Не указан ID фильма'
        })

    try:
        from .tmdb_client import KinopoiskDevClient
        client = KinopoiskDevClient()

        # Получаем детали фильма
        movie_data = client.get_movie_by_id(movie_id)

        if not movie_data:
            return JsonResponse({
                'success': False,
                'message': 'Не удалось получить данные фильма'
            })

        title = movie_data.get('name', '')

        # Проверяем, существует ли уже
        existing = Movie.objects.filter(title__iexact=title).first()
        if existing:
            return JsonResponse({
                'success': False,
                'message': f'Фильм "{title}" уже существует в базе (ID: {existing.id})',
                'exists': True,
                'existing_id': existing.id
            })

        # Создаём фильм
        # Возрастной рейтинг
        age_str = f"{movie_data.get('ageRating', 16)}+"
        age_rating, _ = AgeRating.objects.get_or_create(name=age_str)

        # Описание
        description = movie_data.get('description', '') or movie_data.get('shortDescription', '')
        if not description or len(description.strip()) < 10:
            description = 'Описание отсутствует'
        description = description[:997] + "..." if len(description) > 1000 else description

        short_desc = movie_data.get('shortDescription', '') or description[:197] + "..."
        short_desc = short_desc[:197] + "..." if len(short_desc) > 200 else short_desc

        # Длительность
        duration = movie_data.get('movieLength', 90)

        # Год
        year = movie_data.get('year', timezone.now().year)

        # Обрезаем название
        safe_title = title
        if len(title) > 50:
            safe_title = title[:47] + "..."

        movie = Movie.objects.create(
            title=safe_title,
            short_description=short_desc,
            description=description,
            duration=duration,
            release_year=year,
            age_rating=age_rating
        )

        created_items = {
            'movie': True,
            'genres': [],
            'directors': [],
            'actors': [],
            'poster': False
        }

        # Жанры
        for genre_data in movie_data.get('genres', []):
            genre_name = genre_data.get('name', '')
            if genre_name:
                genre, _ = Genre.objects.get_or_create(
                    name=genre_name.capitalize(),
                    defaults={'description': 'Импортировано из API'}
                )
                MovieGenre.objects.get_or_create(movie=movie, genre=genre)
                created_items['genres'].append(genre.name)

        # Персоны (режиссёры и актёры)
        for person in movie_data.get('persons', [])[:30]:  # Максимум 30 персон
            person_name = person.get('name', '')
            person_id = person.get('id')
            profession = person.get('profession', '').lower()

            if not person_name:
                continue

            name_parts = person_name.split(' ', 1)
            first_name = name_parts[0][:20] if name_parts else ""
            last_name = name_parts[1][:20] if len(name_parts) > 1 else ""

            if profession in ['режиссеры', 'director', 'режиссер', 'режиссёр']:
                director, created = Director.objects.get_or_create(
                    name=first_name,
                    surname=last_name,
                    defaults={'biography': f'ID API: {person_id}'}
                )
                MovieDirector.objects.get_or_create(movie=movie, director=director)
                created_items['directors'].append(f"{first_name} {last_name}")

            elif profession in ['актеры', 'actor', 'актер', 'актёр']:
                actor, created = Actor.objects.get_or_create(
                    name=first_name,
                    surname=last_name,
                    defaults={'biography': f'ID API: {person_id}'}
                )
                MovieActor.objects.get_or_create(movie=movie, actor=actor)
                created_items['actors'].append(f"{first_name} {last_name}")

        # Постер
        if download_poster:
            poster_url = None
            poster_data = movie_data.get('poster', {})
            if isinstance(poster_data, dict):
                poster_url = poster_data.get('url') or poster_data.get('previewUrl')

            if poster_url:
                try:
                    image_content = client.download_image(poster_url)
                    if image_content:
                        import re
                        safe_name = re.sub(r'[^\w\s-]', '', safe_title)[:50].strip()
                        movie.poster.save(
                            f"{safe_name}.jpg",
                            ContentFile(image_content),
                            save=True
                        )
                        created_items['poster'] = True
                except Exception as e:
                    logger.error(f"Ошибка скачивания постера: {e}")

        # Логируем
        OperationLogger.log_operation(
            request=request,
            action_type='CREATE',
            module_type='MOVIES',
            description=f'Импорт фильма из API: {safe_title}',
            object_id=movie.id,
            object_repr=str(movie),
            additional_data=created_items
        )

        return JsonResponse({
            'success': True,
            'message': f'✅ Фильм "{safe_title}" успешно импортирован!',
            'movie': {
                'id': movie.id,
                'title': safe_title,
                'year': year,
                'duration': duration,
            },
            'created': created_items,
            'remaining_requests': get_remaining_requests_info()
        })

    except Exception as e:
        logger.error(f"Ошибка импорта фильма: {e}")
        return JsonResponse({
            'success': False,
            'message': f'Ошибка импорта: {str(e)}'
        })


def get_remaining_requests_info():
    """Получить информацию об оставшихся запросах API"""
    try:
        from ticket.models import APIToken
        tokens = APIToken.objects.all()
        total_remaining = sum(t.remaining_today() for t in tokens)
        total_limit = sum(t.daily_limit for t in tokens)
        return {
            'remaining': total_remaining,
            'limit': total_limit,
            'percent': int((total_remaining / total_limit * 100)) if total_limit > 0 else 0
        }
    except Exception:
        return {'remaining': '?', 'limit': '?', 'percent': 0}


@user_passes_test(is_manager, login_url='login')
def api_remaining_requests(request):
    """API для получения оставшихся запросов"""
    info = get_remaining_requests_info()
    return JsonResponse(info)


# ═══════════════════════════════════════════════
# УПРАВЛЕНИЕ API ТОКЕНАМИ ДЛЯ МЕНЕДЖЕРА
# ═══════════════════════════════════════════════

@user_passes_test(is_manager, login_url='login')
def api_token_info(request):
    """Получить детальную информацию о всех токенах"""
    try:
        from ticket.models import APIToken, APIRequestLog
        from django.conf import settings  # ← ДОБАВИТЬ

        # ВСЕ токены, не только активные
        tokens = APIToken.objects.all()

        current_token = None
        try:
            from ticket.tmdb_client import KinopoiskDevClient
            client = KinopoiskDevClient()
            current_token = client._token_model
            current_api_key = client._api_key
        except Exception:
            current_api_key = getattr(settings, 'KINOPOISK_API_KEY', 'Не задан')

        token_list = []
        for t in tokens:
            is_current = bool(current_token and current_token.id == t.id)
            token_list.append({
                'id': t.id,
                'label': t.label,
                'token_preview': t.token[:8] + '...' + t.token[-4:] if len(t.token) > 12 else t.token[:8] + '...',
                'is_active': t.is_active,
                'is_current': is_current,
                'requests_today': t.requests_today,
                'limit': t.daily_limit,
                'remaining': t.remaining_today(),
                'total_requests': t.total_requests,
                'last_reset': t.last_reset_date.strftime('%d.%m.%Y') if t.last_reset_date else '—'
            })

        last_requests = list(APIRequestLog.objects.select_related('token').order_by('-created_at')[:5].values(
            'endpoint', 'success', 'status_code', 'created_at', 'token__label'
        ))

        return JsonResponse({
            'success': True,
            'tokens': token_list,
            'tokens_count': len(token_list),
            'current_token_info': {
                'key_preview': current_api_key[:8] + '...' + current_api_key[-4:] if current_api_key and len(current_api_key) > 12 else (current_api_key or 'Не задан'),
                'is_from_db': current_token is not None,
                'label': current_token.label if current_token else 'Из settings/.env'
            },
            'last_requests': last_requests
        })
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


@user_passes_test(is_manager, login_url='login')
@require_POST
def api_add_token(request):
    """Добавить новый токен"""
    import json
    data = json.loads(request.body)
    token_value = data.get('token', '').strip()
    label = data.get('label', '').strip()

    if not token_value:
        return JsonResponse({'success': False, 'message': 'Введите токен'})
    if not label:
        label = f'Токен {APIToken.objects.count() + 1}'

    try:
        from ticket.models import APIToken

        # Проверяем, нет ли уже такого токена
        if APIToken.objects.filter(token=token_value).exists():
            return JsonResponse({'success': False, 'message': 'Такой токен уже существует'})

        token = APIToken.objects.create(
            token=token_value,
            label=label,
            daily_limit=200
        )

        # Логируем
        OperationLogger.log_operation(
            request=request,
            action_type='CREATE',
            module_type='SYSTEM',
            description=f'Добавлен новый API токен: {label}',
            object_id=token.id,
            object_repr=str(token)
        )

        return JsonResponse({
            'success': True,
            'message': f'✅ Токен "{label}" успешно добавлен!',
            'token': {
                'id': token.id,
                'label': token.label,
                'token_preview': token.token[:8] + '...' + token.token[-4:]
            }
        })
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


@user_passes_test(is_manager, login_url='login')
@require_POST
def api_toggle_token(request):
    """Включить/выключить токен"""
    import json
    data = json.loads(request.body)
    token_id = data.get('token_id')
    action = data.get('action')  # 'activate' или 'deactivate'

    try:
        from ticket.models import APIToken
        token = APIToken.objects.get(id=token_id)

        if action == 'activate':
            token.is_active = True
            token.save()
            message = f'✅ Токен "{token.label}" активирован'
        else:
            token.is_active = False
            token.save()
            message = f'🔴 Токен "{token.label}" деактивирован'

        return JsonResponse({'success': True, 'message': message})
    except APIToken.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Токен не найден'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


@user_passes_test(is_manager, login_url='login')
@require_POST
def api_delete_token(request):
    """Удалить токен"""
    import json
    data = json.loads(request.body)
    token_id = data.get('token_id')

    try:
        from ticket.models import APIToken
        token = APIToken.objects.get(id=token_id)
        label = token.label
        token.delete()

        return JsonResponse({
            'success': True,
            'message': f'🗑️ Токен "{label}" удалён'
        })
    except APIToken.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Токен не найден'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


@user_passes_test(is_manager, login_url='login')
@require_POST
def api_set_current_token(request):
    """Переключить текущий токен — деактивировать все активные и активировать выбранный"""
    import json
    data = json.loads(request.body)
    token_id = data.get('token_id')

    try:
        from ticket.models import APIToken
        token = APIToken.objects.get(id=token_id)

        # Деактивируем только активные токены (чтобы только один был активен)
        APIToken.objects.filter(is_active=True).update(is_active=False)

        # Активируем выбранный
        token.is_active = True
        token.save()

        return JsonResponse({
            'success': True,
            'message': f'✅ Токен "{token.label}" теперь текущий'
        })
    except APIToken.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Токен не найден'})


def about(request):
    """Страница 'О кинотеатре' с руководством пользователя"""
    from django.db.models import Count

    halls = Hall.objects.annotate(
        seat_count=Count('seats'),
        screening_total=Count('screenings', distinct=True)
    ).select_related('hall_type')

    local_now = timezone.now()
    today = local_now.date()
    total_movies = Movie.objects.filter(
        screenings__start_time__date__gte=today
    ).distinct().count()

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


@user_passes_test(is_manager, login_url='login')
def manager_dashboard(request):
    """Главная страница панели менеджера"""
    # Статистика для дашборда
    today = timezone.now().date()

    # Количество фильмов
    total_movies = Movie.objects.count()

    # Количество сеансов сегодня
    today_screenings = Screening.objects.filter(
        start_time__date=today
    ).count()

    # Количество проданных билетов сегодня
    today_tickets = Ticket.objects.filter(
        created_at__date=today,
        status__code='active'
    ).count()

    # Выручка сегодня
    today_revenue = Ticket.objects.filter(
        created_at__date=today,
        status__code='active'
    ).aggregate(total=Sum('price'))['total'] or 0

    # Ближайшие сеансы
    upcoming_screenings = Screening.objects.filter(
        start_time__gt=timezone.now()
    ).select_related('movie', 'hall').order_by('start_time')[:5]

    context = {
        'total_movies': total_movies,
        'today_screenings': today_screenings,
        'today_tickets': today_tickets,
        'today_revenue': today_revenue,
        'upcoming_screenings': upcoming_screenings,
    }

    return render(request, 'ticket/manager/dashboard.html', context)


@user_passes_test(is_manager, login_url='login')
def manager_movies(request):
    """Управление фильмами для менеджера"""
    movies = Movie.objects.all().select_related('age_rating').prefetch_related('genres').order_by('-created_at')
    return render(request, 'ticket/manager/movies.html', {'movies': movies})


@user_passes_test(is_manager, login_url='login')
def manager_movie_add(request):
    """Добавление фильма менеджером"""
    if request.method == 'POST':
        form = MovieForm(request.POST, request.FILES)
        if form.is_valid():
            movie = form.save()  # Теперь save() правильно обработает ManyToMany

            OperationLogger.log_operation(
                request=request,
                action_type='CREATE',
                module_type='MOVIES',
                description=f'Менеджер создал фильм: {movie.title}',
                object_id=movie.pk,
                object_repr=str(movie),
                additional_data={
                    'genres': ", ".join(g.name for g in movie.genres.all()),
                    'directors': ", ".join(str(d) for d in movie.directors.all()),
                    'actors': ", ".join(str(a) for a in movie.actors.all()[:5])
                }
            )

            messages.success(request, f'Фильм "{movie.title}" успешно добавлен.')
            return redirect('manager_movies')
        else:
            # Логируем ошибки формы для отладки
            logger.error(f"Form errors: {form.errors}")
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    else:
        form = MovieForm()

    return render(request, 'ticket/manager/movie_form.html', {'form': form, 'action': 'add'})


@user_passes_test(is_manager, login_url='login')
def manager_movie_edit(request, movie_id):
    """Редактирование фильма менеджером"""
    movie = get_object_or_404(Movie, pk=movie_id)

    if request.method == 'POST':
        form = MovieForm(request.POST, request.FILES, instance=movie)
        if form.is_valid():
            movie = form.save()  # Теперь save() правильно обработает ManyToMany

            OperationLogger.log_operation(
                request=request,
                action_type='UPDATE',
                module_type='MOVIES',
                description=f'Менеджер обновил фильм: {movie.title}',
                object_id=movie.pk,
                object_repr=str(movie),
                additional_data={
                    'genres': ", ".join(g.name for g in movie.genres.all()),
                    'directors': ", ".join(str(d) for d in movie.directors.all()),
                    'actors': ", ".join(str(a) for a in movie.actors.all()[:5])
                }
            )

            messages.success(request, f'Фильм "{movie.title}" успешно обновлен.')
            return redirect('manager_movies')
        else:
            # Логируем ошибки формы для отладки
            logger.error(f"Form errors: {form.errors}")
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    else:
        form = MovieForm(instance=movie)

    return render(request, 'ticket/manager/movie_form.html', {'form': form, 'movie': movie, 'action': 'edit'})


@user_passes_test(is_manager, login_url='login')
def manager_movie_delete(request, movie_id):
    """Удаление фильма менеджером"""
    movie = get_object_or_404(Movie, pk=movie_id)

    if request.method == 'POST':
        title = movie.title

        OperationLogger.log_operation(
            request=request,
            action_type='DELETE',
            module_type='MOVIES',
            description=f'Менеджер удалил фильм: {title}',
            object_id=movie.pk,
            object_repr=str(movie)
        )

        movie.delete()
        messages.success(request, f'Фильм "{title}" успешно удален.')
        return redirect('manager_movies')

    return render(request, 'ticket/manager/movie_confirm_delete.html', {'movie': movie})


@user_passes_test(is_manager, login_url='login')
def manager_screenings(request):
    """Управление сеансами для менеджера"""
    view_mode = request.GET.get('view', 'upcoming')
    date_filter = request.GET.get('date', '')
    movie_filter = request.GET.get('movie', '')
    hall_filter = request.GET.get('hall', '')

    screenings = Screening.objects.all().select_related(
        'movie', 'hall', 'hall__hall_type'
    ).prefetch_related('tickets').order_by('start_time')

    # Режим отображения
    if view_mode == 'upcoming':
        screenings = screenings.filter(start_time__gte=timezone.now())

    if date_filter:
        try:
            filter_date = datetime.strptime(date_filter, '%Y-%m-%d').date()
            screenings = screenings.filter(start_time__date=filter_date)
        except ValueError:
            pass

    if movie_filter:
        screenings = screenings.filter(movie_id=movie_filter)

    if hall_filter:
        screenings = screenings.filter(hall_id=hall_filter)

    movies = Movie.objects.all().order_by('title')
    halls = Hall.objects.all()

    context = {
        'screenings': screenings,
        'movies': movies,
        'halls': halls,
        'view_mode': view_mode,
        'filters': {
            'date': date_filter,
            'movie': movie_filter,
            'hall': hall_filter,
        }
    }

    return render(request, 'ticket/manager/screenings.html', context)


@user_passes_test(is_manager, login_url='login')
def manager_screening_add(request):
    """Добавление сеанса менеджером"""
    if request.method == 'POST':
        form = ScreeningForm(request.POST)
        if form.is_valid():
            screening = form.save(commit=False)

            # Расчет времени окончания
            if screening.movie and screening.start_time:
                duration_timedelta = timedelta(minutes=screening.movie.duration)
                screening.end_time = screening.start_time + duration_timedelta + timedelta(minutes=10)
                screening.ticket_price = screening.calculate_ticket_price()

            try:
                screening.clean()  # Валидация
                screening.save()

                OperationLogger.log_operation(
                    request=request,
                    action_type='CREATE',
                    module_type='SCREENINGS',
                    description=f'Менеджер создал сеанс: {screening.movie.title} в {screening.hall.name}',
                    object_id=screening.pk,
                    object_repr=str(screening)
                )

                messages.success(request, 'Сеанс успешно добавлен.')
                return redirect('manager_screenings')
            except ValidationError as e:
                for error in e.messages:
                    messages.error(request, error)
    else:
        form = ScreeningForm()

    return render(request, 'ticket/manager/screening_form.html', {'form': form, 'action': 'add'})


@user_passes_test(is_manager, login_url='login')
def manager_screening_edit(request, screening_id):
    """Редактирование сеанса менеджером"""
    screening = get_object_or_404(Screening, pk=screening_id)

    if request.method == 'POST':
        form = ScreeningForm(request.POST, instance=screening)
        if form.is_valid():
            updated_screening = form.save(commit=False)

            # Пересчет времени окончания и цены
            if updated_screening.movie and updated_screening.start_time:
                duration_timedelta = timedelta(minutes=updated_screening.movie.duration)
                updated_screening.end_time = updated_screening.start_time + duration_timedelta + timedelta(minutes=10)

                old_price = screening.ticket_price

                if (updated_screening.hall != screening.hall) or (updated_screening.start_time != screening.start_time):
                    updated_screening.ticket_price = updated_screening.calculate_ticket_price()

            try:
                updated_screening.clean()
                updated_screening.save()

                # Сохраняем историю изменения цены
                if updated_screening.ticket_price != old_price:
                    PriceHistory.objects.create(
                        screening=updated_screening,
                        old_price=old_price,
                        new_price=updated_screening.ticket_price,
                        changed_by=request.user,
                        reason='Изменение через панель менеджера'
                    )
                    OperationLogger.log_price_change(
                        updated_screening, old_price, updated_screening.ticket_price,
                        request.user
                    )

                OperationLogger.log_operation(
                    request=request,
                    action_type='UPDATE',
                    module_type='SCREENINGS',
                    description=f'Менеджер обновил сеанс: {screening.movie.title}',
                    object_id=screening.pk,
                    object_repr=str(screening)
                )

                messages.success(request, 'Сеанс успешно обновлен.')
                return redirect('manager_screenings')
            except ValidationError as e:
                for error in e.messages:
                    messages.error(request, error)
    else:
        form = ScreeningForm(instance=screening)

    return render(request, 'ticket/manager/screening_form.html', {'form': form, 'screening': screening, 'action': 'edit'})


@user_passes_test(is_manager, login_url='login')
def manager_screening_delete(request, screening_id):
    """Удаление сеанса менеджером"""
    screening = get_object_or_404(Screening, pk=screening_id)

    if request.method == 'POST':
        movie_title = screening.movie.title
        hall_name = screening.hall.name
        start_time = screening.start_time

        # Проверяем, есть ли купленные билеты
        if screening.tickets.exists():
            messages.error(request, 'Нельзя удалить сеанс, на который уже куплены билеты.')
            return redirect('manager_screenings')

        OperationLogger.log_operation(
            request=request,
            action_type='DELETE',
            module_type='SCREENINGS',
            description=f'Менеджер удалил сеанс: {movie_title} в {hall_name}',
            object_id=screening.pk,
            object_repr=str(screening)
        )

        screening.delete()
        messages.success(request, 'Сеанс успешно удален.')
        return redirect('manager_screenings')

    return render(request, 'ticket/manager/screening_confirm_delete.html', {'screening': screening})


@user_passes_test(is_manager, login_url='login')
def manager_statistics(request):
    """Статистика и отчеты для менеджера"""
    period = request.GET.get('period', 'week')
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')

    today = timezone.now().date()

    # Определяем диапазон дат
    if start_date_str and end_date_str:
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        except ValueError:
            start_date = today - timedelta(days=7)
            end_date = today
    else:
        if period == 'day':
            start_date = today
            end_date = today
        elif period == 'yesterday':
            start_date = today - timedelta(days=1)
            end_date = today - timedelta(days=1)
        elif period == 'week':
            start_date = today - timedelta(days=7)
            end_date = today
        elif period == 'month':
            start_date = today - timedelta(days=30)
            end_date = today
        else:
            start_date = today - timedelta(days=7)
            end_date = today

    # Фильтр по датам для билетов
    date_filter = Q(created_at__date__gte=start_date, created_at__date__lte=end_date)

    # Основная статистика
    total_tickets = Ticket.objects.filter(date_filter, status__code='active').count()
    total_revenue = Ticket.objects.filter(date_filter, status__code='active').aggregate(
        total=Sum('price')
    )['total'] or 0

    refunded_tickets = Ticket.objects.filter(
        refund_processed_at__date__gte=start_date,
        refund_processed_at__date__lte=end_date,
        status__code='refunded'
    ).count()

    # Продажи по дням
    sales_by_day = list(Ticket.objects.filter(
        date_filter,
        status__code='active'
    ).annotate(
        day=TruncDate('created_at')
    ).values('day').annotate(
        tickets=Count('id'),
        revenue=Sum('price')
    ).order_by('day'))

    # Максимальная выручка для графика
    max_revenue = max((day['revenue'] for day in sales_by_day), default=1)

    # Популярные фильмы
    popular_movies = Movie.objects.filter(
        screenings__tickets__created_at__date__gte=start_date,
        screenings__tickets__created_at__date__lte=end_date,
        screenings__tickets__status__code='active'
    ).annotate(
        tickets_sold=Count('screenings__tickets'),
        revenue=Sum('screenings__tickets__price')
    ).order_by('-tickets_sold')[:5]

    max_popular_tickets = max((m.tickets_sold for m in popular_movies), default=1)

    # Загруженность залов
    hall_occupancy = []
    halls = Hall.objects.all()

    for hall in halls:
        total_seats = hall.rows * hall.seats_per_row
        screenings_in_period = Screening.objects.filter(
            hall=hall,
            start_time__date__gte=start_date,
            start_time__date__lte=end_date
        )

        total_tickets_sold = Ticket.objects.filter(
            screening__in=screenings_in_period,
            status__code='active'
        ).count()

        total_possible = screenings_in_period.count() * total_seats
        occupancy_percent = round((total_tickets_sold / total_possible * 100), 1) if total_possible > 0 else 0

        hall_occupancy.append({
            'hall': hall,
            'total_seats': total_seats,
            'screenings_count': screenings_in_period.count(),
            'tickets_sold': total_tickets_sold,
            'total_possible': total_possible,
            'occupancy_percent': occupancy_percent,
        })

    context = {
        'period': period,
        'start_date': start_date,
        'end_date': end_date,
        'total_tickets': total_tickets,
        'total_revenue': total_revenue,
        'refunded_tickets': refunded_tickets,
        'sales_by_day': sales_by_day,
        'max_revenue': max_revenue,
        'popular_movies': popular_movies,
        'max_popular_tickets': max_popular_tickets,
        'hall_occupancy': hall_occupancy,
    }

    return render(request, 'ticket/manager/statistics.html', context)


@user_passes_test(is_manager, login_url='login')
def manager_api_countries(request):
    """API для получения списка стран"""
    countries = Country.objects.all().values('id', 'name').order_by('name')
    return JsonResponse({'countries': list(countries)})


@user_passes_test(is_manager, login_url='login')
@require_POST
def manager_quick_add_director(request):
    """Быстрое добавление режиссёра через AJAX"""
    form = DirectorForm(request.POST)
    if form.is_valid():
        director = form.save()

        OperationLogger.log_operation(
            request=request,
            action_type='CREATE',
            module_type='MOVIES',
            description=f'Быстрое добавление режиссёра: {director.name} {director.surname}',
            object_id=director.pk,
            object_repr=str(director)
        )

        return JsonResponse({
            'success': True,
            'id': director.id,
            'name': str(director),
            'message': f'✅ Режиссёр {director.name} {director.surname} успешно добавлен!'
        })
    else:
        errors = []
        for field, field_errors in form.errors.items():
            label = form.fields[field].label if field in form.fields else field
            for error in field_errors:
                errors.append(f"{label}: {error}")
        return JsonResponse({
            'success': False,
            'message': '❌ ' + '; '.join(errors) if errors else '❌ Ошибка в форме'
        })


@user_passes_test(is_manager, login_url='login')
@require_POST
def manager_quick_add_actor(request):
    """Быстрое добавление актёра через AJAX"""
    form = ActorForm(request.POST)
    if form.is_valid():
        actor = form.save()

        OperationLogger.log_operation(
            request=request,
            action_type='CREATE',
            module_type='MOVIES',
            description=f'Быстрое добавление актёра: {actor.name} {actor.surname}',
            object_id=actor.pk,
            object_repr=str(actor)
        )

        return JsonResponse({
            'success': True,
            'id': actor.id,
            'name': str(actor),
            'message': f'✅ Актёр {actor.name} {actor.surname} успешно добавлен!'
        })
    else:
        errors = []
        for field, field_errors in form.errors.items():
            label = form.fields[field].label if field in form.fields else field
            for error in field_errors:
                errors.append(f"{label}: {error}")
        return JsonResponse({
            'success': False,
            'message': '❌ ' + '; '.join(errors) if errors else '❌ Ошибка в форме'
        })


@login_required
@require_POST
def request_group_refund(request, group_uuid):
    """Автоматический возврат всей группы билетов"""
    try:
        ticket_group = TicketGroup.objects.get(group_uuid=group_uuid, user=request.user)
    except TicketGroup.DoesNotExist:
        messages.error(request, 'Группа билетов не найдена.')
        return redirect('profile')

    # Логируем попытку возврата
    OperationLogger.log_operation(
        request=request,
        action_type='UPDATE',
        module_type='TICKETS',
        description=f'Попытка возврата группы билетов {group_uuid}',
        object_id=ticket_group.id,
        object_repr=str(ticket_group),
        additional_data={
            'group_uuid': group_uuid,
            'tickets_count': ticket_group.tickets_count,
            'movie': ticket_group.screening.movie.title,
            'screening_time': ticket_group.screening.start_time.isoformat(),
        }
    )

    # Вызываем метод возврата группы
    success, message = ticket_group.request_refund()

    if success:
        OperationLogger.log_operation(
            request=request,
            action_type='UPDATE',
            module_type='TICKETS',
            description=f'Успешный возврат группы билетов {group_uuid}',
            object_id=ticket_group.id,
            object_repr=str(ticket_group),
            additional_data={
                'group_uuid': group_uuid,
                'refund_amount': float(ticket_group.total_amount),
            }
        )
        messages.success(request, message)
    else:
        messages.error(request, f'❌ {message}')

    return redirect('profile')


@user_passes_test(lambda u: u.is_authenticated and u.is_superuser, login_url='manager_dashboard')
def manager_settings(request):
    """Страница настроек системы со ссылками на все справочники"""
    context = {
        'admin_base_url': '/admin/ticket/',
        'sections': [
            {
                'title': 'Фильмы и медиа',
                'icon': '🎬',
                'links': [
                    {'name': 'Жанры', 'url': '/admin/ticket/genre/', 'description': 'Управление жанрами фильмов'},
                    {'name': 'Возрастные рейтинги', 'url': '/admin/ticket/agerating/', 'description': '0+, 6+, 12+, 16+, 18+'},
                    {'name': 'Страны', 'url': '/admin/ticket/country/', 'description': 'Страны производства'},
                    {'name': 'Режиссёры', 'url': '/admin/ticket/director/', 'description': 'Управление режиссёрами'},
                    {'name': 'Актёры', 'url': '/admin/ticket/actor/', 'description': 'Управление актёрами'},
                ]
            },
            {
                'title': 'Залы и места',
                'icon': '🏢',
                'links': [
                    {'name': 'Типы залов', 'url': '/admin/ticket/halltype/', 'description': 'VIP, Стандарт, IMAX'},
                    {'name': 'Залы', 'url': '/admin/ticket/hall/', 'description': 'Управление залами'},
                    {'name': 'Места', 'url': '/admin/ticket/seat/', 'description': 'Просмотр мест (только чтение)'},
                ]
            },
            {
                'title': 'Билеты и платежи',
                'icon': '🎫',
                'links': [
                    {'name': 'Статусы билетов', 'url': '/admin/ticket/ticketstatus/', 'description': 'Настройка статусов билетов'},
                ]
            },
            {
                'title': 'Система',
                'icon': '⚙️',
                'links': [
                    {'name': 'API токены', 'url': '/admin/ticket/apitoken/', 'description': 'Управление токенами Poiskkino.dev'},
                    {'name': 'Бэкапы', 'url': '/admin/ticket/backupmanager/', 'description': 'Управление бэкапами БД'},
                    {'name': 'Пользователи', 'url': '/admin/ticket/user/', 'description': 'Управление пользователями'},
                ]
            },
        ]
    }
    return render(request, 'ticket/manager/settings.html', context)