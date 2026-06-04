# ticket/views_admin.py
import json
import csv
from datetime import datetime, timedelta
from io import BytesIO, StringIO
from decimal import Decimal

from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.paginator import Paginator
from django.db.models import Count, Sum, Q, Avg, F
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import os
from django.conf import settings

from .models import (
    User, HallType, AgeRating, Genre, Country, Director, Actor,
    OperationLog, APIRequestLog, APIToken, TicketStatus, PriceHistory,
    ImportTask, Payment, TicketGroup, Ticket, Screening, Movie, Hall
)
from .logging_utils import OperationLogger

User = get_user_model()


def is_superuser(user):
    """Проверка, является ли пользователь суперпользователем"""
    return user.is_authenticated and user.is_superuser


@staff_member_required
def admin_dashboard(request):
    """Главная страница админ-панели"""
    if not request.user.is_superuser:
        messages.error(request, 'У вас нет доступа к админ-панели.')
        return redirect('manager_dashboard')

    # Статистика
    total_users = User.objects.count()
    active_users_today = User.objects.filter(last_login__date=timezone.now().date()).count()
    verified_users = User.objects.filter(is_email_verified=True).count()

    total_movies = Movie.objects.count()
    total_screenings = Screening.objects.count()
    total_tickets = Ticket.objects.count()
    total_revenue = Ticket.objects.filter(status__code='active').aggregate(
        total=Sum('price')
    )['total'] or 0

    # Логи за последние 7 дней
    week_ago = timezone.now() - timedelta(days=7)
    logs_last_week = OperationLog.objects.filter(timestamp__gte=week_ago).count()

    # API статистика
    total_api_requests = APIRequestLog.objects.count()
    successful_api_requests = APIRequestLog.objects.filter(success=True).count()

    # Активные задачи импорта
    active_imports = ImportTask.objects.filter(status__in=['pending', 'running']).count()

    # Платежи
    total_payments = Payment.objects.count()
    successful_payments = Payment.objects.filter(status='succeeded').count()

    context = {
        'total_users': total_users,
        'active_users_today': active_users_today,
        'verified_users': verified_users,
        'total_movies': total_movies,
        'total_screenings': total_screenings,
        'total_tickets': total_tickets,
        'total_revenue': total_revenue,
        'logs_last_week': logs_last_week,
        'total_api_requests': total_api_requests,
        'successful_api_requests': successful_api_requests,
        'success_rate': int((successful_api_requests / total_api_requests * 100)) if total_api_requests > 0 else 0,
        'active_imports': active_imports,
        'total_payments': total_payments,
        'successful_payments': successful_payments,
        'now': timezone.now(),
        'recent_logs': OperationLog.objects.select_related('user', 'action_type').all().order_by('-timestamp')[:20],
        'total_halls': Hall.objects.count(),
    }

    OperationLogger.log_operation(
        request=request,
        action_type='VIEW',
        module_type='SYSTEM',
        description=f'Просмотр дашборда админ-панели',
        additional_data={'section': 'dashboard'}
    )

    return render(request, 'ticket/admin_panel/dashboard.html', context)


@staff_member_required
def admin_users(request):
    """Управление пользователями"""
    if not request.user.is_superuser:
        messages.error(request, 'У вас нет доступа к админ-панели.')
        return redirect('manager_dashboard')

    # Фильтры
    search = request.GET.get('search', '')
    is_verified = request.GET.get('is_verified', '')
    is_active = request.GET.get('is_active', '')
    is_staff = request.GET.get('is_staff', '')

    users = User.objects.all().order_by('-date_joined')

    if search:
        users = users.filter(
            Q(email__icontains=search) |
            Q(name__icontains=search) |
            Q(surname__icontains=search) |
            Q(number__icontains=search)
        )

    if is_verified == 'yes':
        users = users.filter(is_email_verified=True)
    elif is_verified == 'no':
        users = users.filter(is_email_verified=False)

    if is_active == 'yes':
        users = users.filter(is_active=True)
    elif is_active == 'no':
        users = users.filter(is_active=False)

    if is_staff == 'yes':
        users = users.filter(is_staff=True)
    elif is_staff == 'no':
        users = users.filter(is_staff=False)

    # Пагинация
    paginator = Paginator(users, 50)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    return render(request, 'ticket/admin_panel/users.html', {
        'users': page_obj,
        'search': search,
        'filters': {
            'is_verified': is_verified,
            'is_active': is_active,
            'is_staff': is_staff,
        }
    })


@staff_member_required
def admin_user_edit(request, user_id):
    """Редактирование пользователя"""
    if not request.user.is_superuser:
        messages.error(request, 'У вас нет доступа к админ-панели.')
        return redirect('manager_dashboard')

    user = get_object_or_404(User, id=user_id)

    if request.method == 'POST':
        # Обновление данных
        user.name = request.POST.get('name', user.name)
        user.surname = request.POST.get('surname', user.surname)
        user.number = request.POST.get('number', user.number)
        user.is_active = request.POST.get('is_active') == 'on'
        user.is_staff = request.POST.get('is_staff') == 'on'
        user.is_email_verified = request.POST.get('is_email_verified') == 'on'

        # Группы
        group_ids = request.POST.getlist('groups')
        user.groups.set(group_ids)

        user.save()

        OperationLogger.log_operation(
            request=request,
            action_type='UPDATE',
            module_type='USERS',
            description=f'Администратор обновил пользователя: {user.email}',
            object_id=user.id,
            object_repr=str(user),
            additional_data={
                'changed_fields': ['name', 'surname', 'number', 'is_active', 'is_staff', 'is_email_verified']
            }
        )

        messages.success(request, f'Пользователь {user.email} успешно обновлён.')
        return redirect('admin_panel_users')

    groups = Group.objects.all()
    user_groups = user.groups.values_list('id', flat=True)

    return render(request, 'ticket/admin_panel/user_edit.html', {
        'edit_user': user,
        'groups': groups,
        'user_groups': user_groups,
    })


@staff_member_required
@require_POST
def admin_user_delete(request, user_id):
    """Удаление пользователя"""
    if not request.user.is_superuser:
        messages.error(request, 'У вас нет доступа к админ-панели.')
        return redirect('manager_dashboard')

    user = get_object_or_404(User, id=user_id)

    if user == request.user:
        messages.error(request, 'Нельзя удалить самого себя.')
        return redirect('admin_panel_users')

    email = user.email

    OperationLogger.log_operation(
        request=request,
        action_type='DELETE',
        module_type='USERS',
        description=f'Администратор удалил пользователя: {email}',
        object_id=user.id,
        object_repr=str(user)
    )

    user.delete()
    messages.success(request, f'Пользователь {email} удалён.')
    return redirect('admin_panel_users')


@staff_member_required
@require_POST
def admin_user_toggle_block(request, user_id):
    """Блокировка/разблокировка пользователя"""
    if not request.user.is_superuser:
        messages.error(request, 'У вас нет доступа к админ-панели.')
        return redirect('manager_dashboard')

    user = get_object_or_404(User, id=user_id)

    if user == request.user:
        messages.error(request, 'Нельзя заблокировать самого себя.')
        return redirect('admin_panel_users')

    user.is_active = not user.is_active
    user.save()

    status = 'заблокирован' if not user.is_active else 'разблокирован'

    OperationLogger.log_operation(
        request=request,
        action_type='UPDATE',
        module_type='USERS',
        description=f'Администратор {status} пользователя: {user.email}',
        object_id=user.id,
        object_repr=str(user)
    )

    messages.success(request, f'Пользователь {user.email} {status}.')
    return redirect('admin_panel_users')


@staff_member_required
def admin_roles(request):
    """Управление ролями (группами)"""
    if not request.user.is_superuser:
        messages.error(request, 'У вас нет доступа к админ-панели.')
        return redirect('manager_dashboard')

    groups = Group.objects.all().annotate(
        user_count=Count('user')
    ).order_by('name')

    return render(request, 'ticket/admin_panel/roles.html', {'groups': groups})


@staff_member_required
def admin_role_edit(request, group_id):
    """Редактирование роли"""
    if not request.user.is_superuser:
        messages.error(request, 'У вас нет доступа к админ-панели.')
        return redirect('manager_dashboard')

    group = get_object_or_404(Group, id=group_id)

    if request.method == 'POST':
        group.name = request.POST.get('name', group.name)

        # Обновление разрешений
        permission_ids = request.POST.getlist('permissions')
        group.permissions.set(permission_ids)
        group.save()

        OperationLogger.log_operation(
            request=request,
            action_type='UPDATE',
            module_type='SYSTEM',
            description=f'Администратор обновил роль: {group.name}',
            object_id=group.id,
            object_repr=group.name
        )

        messages.success(request, f'Роль "{group.name}" успешно обновлена.')
        return redirect('admin_panel_roles')

    all_permissions = Permission.objects.select_related('content_type').order_by('content_type__app_label', 'codename')
    group_permissions = group.permissions.values_list('id', flat=True)

    # Группировка разрешений по приложениям
    permissions_by_app = {}
    for perm in all_permissions:
        app_label = perm.content_type.app_label
        if app_label not in permissions_by_app:
            permissions_by_app[app_label] = []
        permissions_by_app[app_label].append({
            'id': perm.id,
            'name': perm.name,
            'codename': perm.codename,
            'checked': perm.id in group_permissions
        })

    return render(request, 'ticket/admin_panel/role_edit.html', {
        'group': group,
        'permissions_by_app': permissions_by_app,
    })


@staff_member_required
def admin_hall_types(request):
    """Управление типами залов"""
    if not request.user.is_superuser:
        messages.error(request, 'У вас нет доступа к админ-панели.')
        return redirect('manager_dashboard')

    search = request.GET.get('search', '')
    hall_types = HallType.objects.all().order_by('name')

    if search:
        hall_types = hall_types.filter(
            Q(name__icontains=search) | Q(description__icontains=search)
        )

    # Пагинация
    paginator = Paginator(hall_types, 20)
    page_number = request.GET.get('page', 1)
    hall_types_page = paginator.get_page(page_number)

    if request.method == 'POST':
        name = request.POST.get('name')
        base_price = request.POST.get('base_price')
        price_coefficient = request.POST.get('price_coefficient', 1.0)
        description = request.POST.get('description', '')

        if name and base_price:
            hall_type = HallType.objects.create(
                name=name,
                base_price=base_price,
                price_coefficient=price_coefficient,
                description=description
            )
            OperationLogger.log_operation(
                request=request,
                action_type='CREATE',
                module_type='SYSTEM',
                description=f'Создан тип зала: {name}',
                object_id=hall_type.id,
                object_repr=name
            )
            messages.success(request, f'Тип зала "{name}" успешно создан.')
            return redirect('admin_panel_hall_types')

    return render(request, 'ticket/admin_panel/hall_types.html', {
        'hall_types': hall_types_page,
        'search': search,
    })


@staff_member_required
def admin_hall_type_edit(request, ht_id):
    """Редактирование типа зала"""
    if not request.user.is_superuser:
        messages.error(request, 'У вас нет доступа к админ-панели.')
        return redirect('manager_dashboard')

    hall_type = get_object_or_404(HallType, id=ht_id)

    if request.method == 'POST':
        old_name = hall_type.name
        hall_type.name = request.POST.get('name', hall_type.name)
        hall_type.base_price = request.POST.get('base_price', hall_type.base_price)
        hall_type.price_coefficient = request.POST.get('price_coefficient', hall_type.price_coefficient)
        hall_type.description = request.POST.get('description', hall_type.description)
        hall_type.save()

        OperationLogger.log_operation(
            request=request,
            action_type='UPDATE',
            module_type='SYSTEM',
            description=f'Обновлён тип зала: {old_name} → {hall_type.name}',
            object_id=hall_type.id,
            object_repr=hall_type.name
        )

        messages.success(request, f'Тип зала "{hall_type.name}" успешно обновлён.')
        return redirect('admin_panel_hall_types')

    return render(request, 'ticket/admin_panel/hall_type_edit.html', {'hall_type': hall_type})


@staff_member_required
def admin_hall_type_delete(request, ht_id):
    """Удаление типа зала"""
    if not request.user.is_superuser:
        messages.error(request, 'У вас нет доступа к админ-панели.')
        return redirect('manager_dashboard')

    hall_type = get_object_or_404(HallType, id=ht_id)

    if request.method == 'POST':
        name = hall_type.name
        hall_type.delete()

        OperationLogger.log_operation(
            request=request,
            action_type='DELETE',
            module_type='SYSTEM',
            description=f'Удалён тип зала: {name}',
            object_id=ht_id,
            object_repr=name
        )

        messages.success(request, f'Тип зала "{name}" удалён.')
        return redirect('admin_panel_hall_types')

    return render(request, 'ticket/admin_panel/hall_type_confirm_delete.html', {'hall_type': hall_type})


@staff_member_required
def admin_age_ratings(request):
    """Управление возрастными рейтингами"""
    if not request.user.is_superuser:
        messages.error(request, 'У вас нет доступа к админ-панели.')
        return redirect('manager_dashboard')

    search = request.GET.get('search', '')
    age_ratings = AgeRating.objects.all().order_by('name')

    if search:
        age_ratings = age_ratings.filter(name__icontains=search)

    paginator = Paginator(age_ratings, 20)
    page_number = request.GET.get('page', 1)
    age_ratings_page = paginator.get_page(page_number)

    if request.method == 'POST':
        name = request.POST.get('name')
        if name:
            age_rating = AgeRating.objects.create(name=name)
            OperationLogger.log_operation(
                request=request,
                action_type='CREATE',
                module_type='SYSTEM',
                description=f'Создан возрастной рейтинг: {name}',
                object_id=age_rating.id,
                object_repr=name
            )
            messages.success(request, f'Возрастной рейтинг "{name}" создан.')
            return redirect('admin_panel_age_ratings')

    return render(request, 'ticket/admin_panel/age_ratings.html', {
        'age_ratings': age_ratings_page,
        'search': search,
    })


@staff_member_required
@require_POST
def admin_age_rating_delete(request, ar_id):
    """Удаление возрастного рейтинга"""
    if not request.user.is_superuser:
        messages.error(request, 'У вас нет доступа к админ-панели.')
        return redirect('manager_dashboard')

    age_rating = get_object_or_404(AgeRating, id=ar_id)
    name = age_rating.name
    age_rating.delete()

    OperationLogger.log_operation(
        request=request,
        action_type='DELETE',
        module_type='SYSTEM',
        description=f'Удалён возрастной рейтинг: {name}',
        object_id=ar_id,
        object_repr=name
    )

    messages.success(request, f'Возрастной рейтинг "{name}" удалён.')
    return redirect('admin_panel_age_ratings')


@staff_member_required
def admin_genres(request):
    """Управление жанрами"""
    if not request.user.is_superuser:
        messages.error(request, 'У вас нет доступа к админ-панели.')
        return redirect('manager_dashboard')

    search = request.GET.get('search', '')
    genres = Genre.objects.all().order_by('name')

    if search:
        genres = genres.filter(
            Q(name__icontains=search) | Q(description__icontains=search)
        )

    paginator = Paginator(genres, 20)
    page_number = request.GET.get('page', 1)
    genres_page = paginator.get_page(page_number)

    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description', '')
        if name:
            genre = Genre.objects.create(name=name, description=description)
            OperationLogger.log_operation(
                request=request,
                action_type='CREATE',
                module_type='SYSTEM',
                description=f'Создан жанр: {name}',
                object_id=genre.id,
                object_repr=name
            )
            messages.success(request, f'Жанр "{name}" создан.')
            return redirect('admin_panel_genres')

    return render(request, 'ticket/admin_panel/genres.html', {
        'genres': genres_page,
        'search': search,
    })


@staff_member_required
@require_POST
def admin_genre_delete(request, genre_id):
    """Удаление жанра"""
    if not request.user.is_superuser:
        messages.error(request, 'У вас нет доступа к админ-панели.')
        return redirect('manager_dashboard')

    genre = get_object_or_404(Genre, id=genre_id)
    name = genre.name
    genre.delete()

    OperationLogger.log_operation(
        request=request,
        action_type='DELETE',
        module_type='SYSTEM',
        description=f'Удалён жанр: {name}',
        object_id=genre_id,
        object_repr=name
    )

    messages.success(request, f'Жанр "{name}" удалён.')
    return redirect('admin_panel_genres')


@staff_member_required
def admin_countries(request):
    """Управление странами"""
    if not request.user.is_superuser:
        messages.error(request, 'У вас нет доступа к админ-панели.')
        return redirect('manager_dashboard')

    search = request.GET.get('search', '')
    countries = Country.objects.all().order_by('name')

    if search:
        countries = countries.filter(
            Q(name__icontains=search) | Q(code__icontains=search)
        )

    paginator = Paginator(countries, 20)
    page_number = request.GET.get('page', 1)
    countries_page = paginator.get_page(page_number)

    if request.method == 'POST':
        name = request.POST.get('name')
        code = request.POST.get('code', '').upper()
        if name and code:
            country = Country.objects.create(name=name, code=code)
            OperationLogger.log_operation(
                request=request,
                action_type='CREATE',
                module_type='SYSTEM',
                description=f'Создана страна: {name} ({code})',
                object_id=country.id,
                object_repr=name
            )
            messages.success(request, f'Страна "{name}" создана.')
            return redirect('admin_panel_countries')

    return render(request, 'ticket/admin_panel/countries.html', {
        'countries': countries_page,
        'search': search,
    })


@staff_member_required
@require_POST
def admin_country_delete(request, country_id):
    """Удаление страны"""
    if not request.user.is_superuser:
        messages.error(request, 'У вас нет доступа к админ-панели.')
        return redirect('manager_dashboard')

    country = get_object_or_404(Country, id=country_id)
    name = country.name
    country.delete()

    OperationLogger.log_operation(
        request=request,
        action_type='DELETE',
        module_type='SYSTEM',
        description=f'Удалена страна: {name}',
        object_id=country_id,
        object_repr=name
    )

    messages.success(request, f'Страна "{name}" удалена.')
    return redirect('admin_panel_countries')


@staff_member_required
def admin_directors(request):
    """Управление режиссёрами"""
    if not request.user.is_superuser:
        messages.error(request, 'У вас нет доступа к админ-панели.')
        return redirect('manager_dashboard')

    search = request.GET.get('search', '')
    country_id = request.GET.get('country', '')

    directors = Director.objects.all().order_by('surname', 'name')

    if search:
        directors = directors.filter(
            Q(name__icontains=search) | Q(surname__icontains=search)
        )
    if country_id:
        directors = directors.filter(country_id=country_id)

    paginator = Paginator(directors, 20)
    page_number = request.GET.get('page', 1)
    directors_page = paginator.get_page(page_number)

    if request.method == 'POST':
        name = request.POST.get('name')
        surname = request.POST.get('surname')
        birth_date = request.POST.get('birth_date') or None
        country_id_val = request.POST.get('country')
        biography = request.POST.get('biography', '')

        if name and surname:
            director = Director.objects.create(
                name=name,
                surname=surname,
                birth_date=birth_date,
                country_id=country_id_val if country_id_val else None,
                biography=biography
            )
            OperationLogger.log_operation(
                request=request,
                action_type='CREATE',
                module_type='SYSTEM',
                description=f'Создан режиссёр: {name} {surname}',
                object_id=director.id,
                object_repr=str(director)
            )
            messages.success(request, f'Режиссёр "{name} {surname}" создан.')
            return redirect('admin_panel_directors')

    countries = Country.objects.all().order_by('name')

    return render(request, 'ticket/admin_panel/directors.html', {
        'directors': directors_page,
        'countries': countries,
        'search': search,
    })


@require_POST
def admin_director_delete(request, director_id):
    """Удаление режиссёра"""
    if not request.user.is_superuser:
        messages.error(request, 'У вас нет доступа к админ-панели.')
        return redirect('manager_dashboard')

    director = get_object_or_404(Director, id=director_id)
    name = f"{director.name} {director.surname}"
    director.delete()

    OperationLogger.log_operation(
        request=request,
        action_type='DELETE',
        module_type='SYSTEM',
        description=f'Удалён режиссёр: {name}',
        object_id=director_id,
        object_repr=name
    )

    messages.success(request, f'Режиссёр "{name}" удалён.')
    return redirect('admin_panel_directors')

@staff_member_required
def admin_actors(request):
    """Управление актёрами"""
    if not request.user.is_superuser:
        messages.error(request, 'У вас нет доступа к админ-панели.')
        return redirect('manager_dashboard')

    search = request.GET.get('search', '')
    country_id = request.GET.get('country', '')

    actors = Actor.objects.all().order_by('surname', 'name')

    if search:
        actors = actors.filter(
            Q(name__icontains=search) | Q(surname__icontains=search)
        )
    if country_id:
        actors = actors.filter(country_id=country_id)

    paginator = Paginator(actors, 20)
    page_number = request.GET.get('page', 1)
    actors_page = paginator.get_page(page_number)

    if request.method == 'POST':
        name = request.POST.get('name')
        surname = request.POST.get('surname')
        birth_date = request.POST.get('birth_date') or None
        country_id_val = request.POST.get('country')
        biography = request.POST.get('biography', '')

        if name and surname:
            actor = Actor.objects.create(
                name=name,
                surname=surname,
                birth_date=birth_date,
                country_id=country_id_val if country_id_val else None,
                biography=biography
            )
            OperationLogger.log_operation(
                request=request,
                action_type='CREATE',
                module_type='SYSTEM',
                description=f'Создан актёр: {name} {surname}',
                object_id=actor.id,
                object_repr=str(actor)
            )
            messages.success(request, f'Актёр "{name} {surname}" создан.')
            return redirect('admin_panel_actors')

    countries = Country.objects.all().order_by('name')

    return render(request, 'ticket/admin_panel/actors.html', {
        'actors': actors_page,
        'countries': countries,
        'search': search,
    })


@require_POST
def admin_actor_delete(request, actor_id):
    """Удаление актёра"""
    if not request.user.is_superuser:
        messages.error(request, 'У вас нет доступа к админ-панели.')
        return redirect('manager_dashboard')

    actor = get_object_or_404(Actor, id=actor_id)
    name = f"{actor.name} {actor.surname}"
    actor.delete()

    OperationLogger.log_operation(
        request=request,
        action_type='DELETE',
        module_type='SYSTEM',
        description=f'Удалён актёр: {name}',
        object_id=actor_id,
        object_repr=name
    )

    messages.success(request, f'Актёр "{name}" удалён.')
    return redirect('admin_panel_actors')


@staff_member_required
def admin_logs(request):
    """Просмотр логов операций"""
    if not request.user.is_superuser:
        messages.error(request, 'У вас нет доступа к админ-панели.')
        return redirect('manager_dashboard')

    # Фильтры
    action_type = request.GET.get('action_type', '')
    module_type = request.GET.get('module_type', '')
    user_id = request.GET.get('user_id', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')

    logs = OperationLog.objects.select_related('user', 'action_type', 'module_type').all()

    if action_type:
        logs = logs.filter(action_type__code=action_type)
    if module_type:
        logs = logs.filter(module_type__code=module_type)
    if user_id:
        logs = logs.filter(user_id=user_id)
    if date_from:
        logs = logs.filter(timestamp__date__gte=date_from)
    if date_to:
        logs = logs.filter(timestamp__date__lte=date_to)

    logs = logs.order_by('-timestamp')

    paginator = Paginator(logs, 100)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    # Для фильтров
    action_types = ActionType.objects.all().order_by('name')
    module_types = ModuleType.objects.all().order_by('name')
    users = User.objects.all().order_by('email')

    return render(request, 'ticket/admin_panel/logs.html', {
        'logs': page_obj,
        'action_types': action_types,
        'module_types': module_types,
        'users': users,
        'filters': {
            'action_type': action_type,
            'module_type': module_type,
            'user_id': user_id,
            'date_from': date_from,
            'date_to': date_to,
        }
    })


@staff_member_required
def admin_logs_export(request):
    """Экспорт логов в CSV/JSON/PDF"""
    if not request.user.is_superuser:
        messages.error(request, 'У вас нет доступа к админ-панели.')
        return redirect('manager_dashboard')

    format_type = request.GET.get('format', 'csv')

    # Получаем отфильтрованные логи
    action_type = request.GET.get('action_type', '')
    module_type = request.GET.get('module_type', '')
    user_id = request.GET.get('user_id', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')

    logs = OperationLog.objects.select_related('user', 'action_type', 'module_type').all()

    if action_type:
        logs = logs.filter(action_type__code=action_type)
    if module_type:
        logs = logs.filter(module_type__code=module_type)
    if user_id:
        logs = logs.filter(user_id=user_id)
    if date_from:
        logs = logs.filter(timestamp__date__gte=date_from)
    if date_to:
        logs = logs.filter(timestamp__date__lte=date_to)

    logs = logs.order_by('-timestamp')

    if format_type == 'csv':
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = 'attachment; filename="logs_export.csv"'

        writer = csv.writer(response)
        writer.writerow(
            ['ID', 'Пользователь', 'Действие', 'Модуль', 'Описание', 'IP адрес', 'Время', 'Object ID', 'Object Repr'])

        for log in logs:
            writer.writerow([
                log.id,
                log.user.email if log.user else 'Аноним',
                log.action_type.name if log.action_type else '-',
                log.module_type.name if log.module_type else '-',
                log.description,
                log.ip_address or '-',
                log.timestamp.strftime('%d.%m.%Y %H:%M:%S'),
                log.object_id or '-',
                log.object_repr or '-',
            ])

        OperationLogger.log_operation(
            request=request,
            action_type='EXPORT',
            module_type='SYSTEM',
            description=f'Экспорт логов в CSV ({logs.count()} записей)'
        )

        return response

    elif format_type == 'json':
        data = []
        for log in logs:
            data.append({
                'id': log.id,
                'user': log.user.email if log.user else None,
                'action': log.action_type.name if log.action_type else None,
                'module': log.module_type.name if log.module_type else None,
                'description': log.description,
                'ip_address': log.ip_address,
                'timestamp': log.timestamp.isoformat(),
                'object_id': log.object_id,
                'object_repr': log.object_repr,
                'additional_data': log.additional_data,
            })

        response = HttpResponse(json.dumps(data, ensure_ascii=False, indent=2),
                                content_type='application/json; charset=utf-8')
        response['Content-Disposition'] = 'attachment; filename="logs_export.json"'

        OperationLogger.log_operation(
            request=request,
            action_type='EXPORT',
            module_type='SYSTEM',
            description=f'Экспорт логов в JSON ({logs.count()} записей)'
        )

        return response

    messages.error(request, 'Неподдерживаемый формат экспорта.')
    return redirect('admin_panel_logs')


@staff_member_required
def admin_api_logs(request):
    """Просмотр логов API запросов"""
    if not request.user.is_superuser:
        messages.error(request, 'У вас нет доступа к админ-панели.')
        return redirect('manager_dashboard')

    # Фильтры
    success = request.GET.get('success', '')
    token_id = request.GET.get('token_id', '')

    logs = APIRequestLog.objects.select_related('token').all().order_by('-created_at')

    if success == 'yes':
        logs = logs.filter(success=True)
    elif success == 'no':
        logs = logs.filter(success=False)
    if token_id:
        logs = logs.filter(token_id=token_id)

    paginator = Paginator(logs, 100)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    tokens = APIToken.objects.all()

    return render(request, 'ticket/admin_panel/api_logs.html', {
        'logs': page_obj,
        'tokens': tokens,
        'filters': {
            'success': success,
            'token_id': token_id,
        }
    })


@staff_member_required
def admin_ticket_statuses(request):
    """Управление статусами билетов"""
    if not request.user.is_superuser:
        messages.error(request, 'У вас нет доступа к админ-панели.')
        return redirect('manager_dashboard')

    statuses = TicketStatus.objects.all().order_by('id')

    if request.method == 'POST':
        status_id = request.POST.get('status_id')
        status = get_object_or_404(TicketStatus, id=status_id)

        old_name = status.name
        status.name = request.POST.get('name', status.name)
        status.description = request.POST.get('description', status.description)
        status.is_active = request.POST.get('is_active') == 'on'
        status.can_be_refunded = request.POST.get('can_be_refunded') == 'on'
        status.save()

        OperationLogger.log_operation(
            request=request,
            action_type='UPDATE',
            module_type='SYSTEM',
            description=f'Обновлён статус билета: {old_name} → {status.name}',
            object_id=status.id,
            object_repr=status.name
        )

        messages.warning(request,
                         f'⚠️ Статус билета "{status.name}" обновлён. Будьте осторожны: изменение статусов может повлиять на логику работы системы!')
        return redirect('admin_panel_ticket_statuses')

    return render(request, 'ticket/admin_panel/ticket_statuses.html', {'statuses': statuses})


@staff_member_required
def admin_price_history(request):
    """Просмотр истории изменения цен"""
    if not request.user.is_superuser:
        messages.error(request, 'У вас нет доступа к админ-панели.')
        return redirect('manager_dashboard')

    history = PriceHistory.objects.select_related('screening', 'screening__movie', 'changed_by').all().order_by(
        '-changed_at')

    paginator = Paginator(history, 50)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    return render(request, 'ticket/admin_panel/price_history.html', {'history': page_obj})


@staff_member_required
def admin_import_tasks(request):
    """Просмотр задач импорта"""
    if not request.user.is_superuser:
        messages.error(request, 'У вас нет доступа к админ-панели.')
        return redirect('manager_dashboard')

    tasks = ImportTask.objects.all().order_by('-created_at')

    return render(request, 'ticket/admin_panel/import_tasks.html', {'tasks': tasks})


@staff_member_required
def admin_payments(request):
    """Просмотр платежей (только чтение)"""
    if not request.user.is_superuser:
        messages.error(request, 'У вас нет доступа к админ-панели.')
        return redirect('manager_dashboard')

    payments = Payment.objects.select_related('ticket_group', 'ticket_group__user',
                                              'ticket_group__screening__movie').all().order_by('-created_at')

    # Фильтры
    status = request.GET.get('status', '')
    if status:
        payments = payments.filter(status=status)

    paginator = Paginator(payments, 50)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    return render(request, 'ticket/admin_panel/payments.html', {
        'payments': page_obj,
        'filters': {'status': status}
    })


@staff_member_required
def admin_system_info(request):
    """Информация о системе"""
    if not request.user.is_superuser:
        messages.error(request, 'У вас нет доступа к админ-панели.')
        return redirect('manager_dashboard')

    # Статистика БД
    db_stats = {
        'users': User.objects.count(),
        'movies': Movie.objects.count(),
        'screenings': Screening.objects.count(),
        'halls': Hall.objects.count(),
        'tickets': Ticket.objects.count(),
        'payments': Payment.objects.count(),
        'logs': OperationLog.objects.count(),
        'api_logs': APIRequestLog.objects.count(),
    }

    # Запросы по типам
    from .models import ActionType
    actions_stats = {}
    for action in ActionType.objects.all():
        actions_stats[action.name] = OperationLog.objects.filter(action_type=action).count()

    context = {
        'db_stats': db_stats,
        'actions_stats': actions_stats,
    }

    return render(request, 'ticket/admin_panel/system_info.html', context)


@staff_member_required
def admin_redirect_to_django(request):
    """Редирект на Django Admin"""
    if not request.user.is_superuser:
        messages.error(request, 'У вас нет доступа к админ-панели.')
        return redirect('manager_dashboard')

    OperationLogger.log_operation(
        request=request,
        action_type='VIEW',
        module_type='SYSTEM',
        description=f'Переход в Django Admin из админ-панели'
    )

    return redirect('/admin/')