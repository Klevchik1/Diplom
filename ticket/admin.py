import os
from django.contrib import admin
from django.contrib import messages
from django.contrib.auth.admin import UserAdmin
from django.core.management import call_command
from django.http import HttpResponse
from django.shortcuts import render
from django.urls import path
from django.utils import timezone
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from .export_utils import LogExporter
from .forms import ReportFilterForm, MovieForm, ScreeningAdminForm
from .logging_utils import OperationLogger
from .models import (
    BackupManager, PasswordResetRequest, PendingRegistration,
    Report, OperationLog, AgeRating, TicketStatus, Country,
    HallType, Director, Actor, MovieDirector, MovieActor,
    TicketGroup, ActionType, ModuleType, EmailChangeRequest
)
from .models import Hall, Movie, Screening, Seat, Ticket, User, Genre
from .report_utils import ReportGenerator
from django import forms
from django.core.exceptions import ValidationError
from django.http import JsonResponse, HttpResponseRedirect
from django.urls import reverse


class LoggingModelAdmin(admin.ModelAdmin):
    """Базовый класс для автоматического логирования операций в админке"""

    def save_model(self, request, obj, form, change):
        """Логирование создания/изменения объектов"""
        action = 'UPDATE' if change else 'CREATE'

        # Определяем module_type на основе модели
        module_map = {
            'User': 'USERS',
            'Hall': 'HALLS',
            'HallType': 'HALLS',
            'Movie': 'MOVIES',
            'Genre': 'MOVIES',
            'AgeRating': 'MOVIES',
            'Director': 'MOVIES',
            'Actor': 'MOVIES',
            'Screening': 'SCREENINGS',
            'Seat': 'HALLS',
            'Ticket': 'TICKETS',
            'TicketStatus': 'TICKETS',
            'TicketGroup': 'TICKETS',
            'Country': 'SYSTEM',
            'BackupManager': 'BACKUPS',
            'OperationLog': 'SYSTEM',
        }

        module_type = module_map.get(obj.__class__.__name__, 'SYSTEM')

        OperationLogger.log_model_operation(
            request=request,
            action_type=action,
            instance=obj,
            description=f"{action} {obj._meta.verbose_name} '{str(obj)}'",
            module_type=module_type
        )
        super().save_model(request, obj, form, change)

    def delete_model(self, request, obj):
        """Логирование удаления объектов"""
        module_map = {
            'User': 'USERS',
            'Hall': 'HALLS',
            'HallType': 'HALLS',
            'Movie': 'MOVIES',
            'Genre': 'MOVIES',
            'AgeRating': 'MOVIES',
            'Director': 'MOVIES',
            'Actor': 'MOVIES',
            'Screening': 'SCREENINGS',
            'Seat': 'HALLS',
            'Ticket': 'TICKETS',
            'TicketStatus': 'TICKETS',
            'TicketGroup': 'TICKETS',
            'Country': 'SYSTEM',
            'BackupManager': 'BACKUPS',
            'OperationLog': 'SYSTEM',
        }

        module_type = module_map.get(obj.__class__.__name__, 'SYSTEM')

        OperationLogger.log_model_operation(
            request=request,
            action_type='DELETE',
            instance=obj,
            description=f"DELETE {obj._meta.verbose_name} '{str(obj)}'",
            module_type=module_type
        )
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        """Логирование массового удаления"""
        for obj in queryset:
            module_map = {
                'User': 'USERS',
                'Hall': 'HALLS',
                'HallType': 'HALLS',
                'Movie': 'MOVIES',
                'Genre': 'MOVIES',
                'AgeRating': 'MOVIES',
                'Director': 'MOVIES',
                'Actor': 'MOVIES',
                'Screening': 'SCREENINGS',
                'Seat': 'HALLS',
                'Ticket': 'TICKETS',
                'TicketStatus': 'TICKETS',
                'TicketGroup': 'TICKETS',
                'Country': 'SYSTEM',
                'BackupManager': 'BACKUPS',
                'OperationLog': 'SYSTEM',
            }

            module_type = module_map.get(obj.__class__.__name__, 'SYSTEM')

            OperationLogger.log_model_operation(
                request=request,
                action_type='DELETE',
                instance=obj,
                description=f"DELETE {obj._meta.verbose_name} '{str(obj)}' (mass delete)",
                module_type=module_type
            )
        super().delete_queryset(request, queryset)


# Регистрация новых моделей
@admin.register(Country)
class CountryAdmin(LoggingModelAdmin):
    list_display = ('name', 'code', 'created_at')
    search_fields = ('name', 'code')
    list_filter = ('created_at',)
    readonly_fields = ('created_at',)


@admin.register(HallType)
class HallTypeAdmin(LoggingModelAdmin):
    list_display = ('name', 'price_coefficient', 'base_price', 'halls_count')
    search_fields = ('name', 'description')
    list_filter = ('created_at',)
    readonly_fields = ('created_at',)

    def halls_count(self, obj):
        return obj.halls.count()

    halls_count.short_description = 'Количество залов'


@admin.register(Director)
class DirectorAdmin(LoggingModelAdmin):
    list_display = ('surname', 'name', 'country', 'birth_date', 'movies_count')
    search_fields = ('name', 'surname')
    list_filter = ('country', 'created_at')
    readonly_fields = ('created_at',)

    def movies_count(self, obj):
        return obj.moviedirector_set.count()

    movies_count.short_description = 'Фильмов'


@admin.register(Actor)
class ActorAdmin(LoggingModelAdmin):
    list_display = ('surname', 'name', 'country', 'birth_date', 'movies_count')
    search_fields = ('name', 'surname')
    list_filter = ('country', 'created_at')
    readonly_fields = ('created_at',)

    def movies_count(self, obj):
        return obj.movieactor_set.count()

    movies_count.short_description = 'Фильмов'


class MovieDirectorInline(admin.TabularInline):
    model = MovieDirector
    extra = 1
    autocomplete_fields = ['director']


class MovieActorInline(admin.TabularInline):
    model = MovieActor
    extra = 1
    autocomplete_fields = ['actor']


@admin.register(User)
class CustomUserAdmin(LoggingModelAdmin, UserAdmin):
    list_display = ('email', 'name', 'surname', 'number', 'is_staff', 'is_email_verified', 'is_telegram_verified')
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'is_email_verified', 'is_telegram_verified', 'created_at')
    search_fields = ('email', 'name', 'surname', 'number')

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal Info', {'fields': ('name', 'surname', 'number', 'created_at', 'updated_at')}),
        ('Email Verification', {'fields': ('is_email_verified', 'email_verification_code', 'email_verification_code_sent_at')}),
        ('Telegram', {'fields': ('telegram_chat_id', 'telegram_username', 'is_telegram_verified', 'telegram_verification_code')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'name', 'surname', 'number', 'password1', 'password2'),
        }),
    )

    readonly_fields = ('created_at', 'updated_at', 'last_login', 'date_joined')
    ordering = ('email',)

    def has_add_permission(self, request):
        return True


@admin.register(Hall)
class HallAdmin(LoggingModelAdmin):
    list_display = ('name', 'hall_type', 'rows', 'seats_per_row', 'total_seats', 'created_at')
    list_filter = ('hall_type', 'created_at')
    search_fields = ('name', 'description')
    readonly_fields = ('created_at', 'updated_at')

    fieldsets = (
        (None, {
            'fields': ('name', 'hall_type', 'description')
        }),
        ('Схема зала', {
            'fields': ('rows', 'seats_per_row')
        }),
        ('Системная информация', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def total_seats(self, obj):
        return obj.rows * obj.seats_per_row

    total_seats.short_description = 'Всего мест'


class GenreAdminForm(forms.ModelForm):
    """Форма для админки с валидацией уникальности жанра"""

    class Meta:
        model = Genre
        fields = '__all__'

    def clean_name(self):
        name = self.cleaned_data.get('name')
        if name:
            # Приводим к стандартному виду
            name = ' '.join(name.strip().split()).title()

            # Проверяем уникальность
            queryset = Genre.objects.filter(name=name)
            if self.instance.pk:
                queryset = queryset.exclude(pk=self.instance.pk)

            if queryset.exists():
                raise ValidationError(f'Жанр "{name}" уже существует')

        return name


@admin.register(Genre)
class GenreAdmin(LoggingModelAdmin):
    """Админ-класс для управления жанрами"""
    list_display = ('name', 'description_short', 'movie_count', 'created_at')
    search_fields = ('name', 'description')
    list_per_page = 20
    readonly_fields = ('created_at',)
    form = GenreAdminForm
    list_filter = ('created_at',)

    def description_short(self, obj):
        if obj.description and len(obj.description) > 50:
            return obj.description[:50] + '...'
        return obj.description or '-'

    description_short.short_description = 'Описание'

    def movie_count(self, obj):
        """Количество фильмов в этом жанре"""
        return obj.movie_set.count()

    movie_count.short_description = 'Количество фильмов'

    actions = ['merge_duplicate_genres']

    def merge_duplicate_genres(self, request, queryset):
        """Объединить выбранные жанры в один (первый выбранный)"""
        if queryset.count() < 2:
            self.message_user(request, 'Выберите хотя бы 2 жанра для объединения', messages.WARNING)
            return

        main_genre = queryset.first()
        other_genres = queryset.exclude(pk=main_genre.pk)

        # Обновляем все фильмы с другими жанрами на основной жанр
        updated_count = 0
        for genre in other_genres:
            movies = genre.movie_set.all()
            for movie in movies:
                movie.genre = main_genre
                movie.save()
                updated_count += 1

        # Удаляем объединенные жанры
        deleted_count = other_genres.count()
        other_genres.delete()

        # Логируем операцию
        OperationLogger.log_model_operation(
            request=request,
            action_type='UPDATE',
            instance=main_genre,
            description=f'Объединение жанров: {deleted_count} жанров объединены в "{main_genre.name}", обновлено {updated_count} фильмов',
            module_type='MOVIES'
        )

        self.message_user(
            request,
            f'✅ Объединено {deleted_count} жанров в "{main_genre.name}". Обновлено {updated_count} фильмов.',
            messages.SUCCESS
        )

    merge_duplicate_genres.short_description = "🔀 Объединить выбранные жанры"


@admin.register(AgeRating)
class AgeRatingAdmin(LoggingModelAdmin):
    """Админ-класс для управления возрастными рейтингами"""
    list_display = ('name', 'movie_count', 'created_at')
    list_filter = ('name',)
    search_fields = ('name',)
    readonly_fields = ('created_at',)
    list_per_page = 20

    def movie_count(self, obj):
        """Количество фильмов с этим рейтингом"""
        return obj.movies.count()

    movie_count.short_description = 'Количество фильмов'


@admin.register(Movie)
class MovieAdmin(LoggingModelAdmin):
    list_display = ('title', 'release_year', 'genre', 'age_rating', 'duration_display', 'has_poster', 'screening_count')
    search_fields = ('title', 'genre__name', 'short_description', 'description')
    list_filter = ('genre', 'age_rating', 'release_year')
    list_per_page = 20
    form = MovieForm
    readonly_fields = ('created_at', 'display_directors', 'display_actors')

    fieldsets = (
        (None, {
            'fields': ('title', 'release_year', 'duration')
        }),
        ('Описание', {
            'fields': ('short_description', 'description')
        }),
        ('Классификация', {
            'fields': ('genre', 'age_rating')
        }),
        ('Медиа', {
            'fields': ('poster',)
        }),
        ('Создатели', {
            'fields': ('display_directors', 'display_actors'),
            'description': 'Режиссёры и актёры (редактирование через форму фильма)'
        }),
        ('Системная информация', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )

    # Убираем filter_horizontal, так как используем кастомные промежуточные модели
    # filter_horizontal = ('directors', 'actors')

    def duration_display(self, obj):
        hours = obj.duration // 60
        minutes = obj.duration % 60
        if hours > 0:
            return f"{hours} ч {minutes} мин"
        return f"{minutes} мин"

    duration_display.short_description = 'Длительность'

    def has_poster(self, obj):
        return bool(obj.poster)

    has_poster.boolean = True
    has_poster.short_description = 'Есть постер'

    def screening_count(self, obj):
        """Количество сеансов для этого фильма"""
        return obj.screenings.count()

    screening_count.short_description = 'Сеансы'

    def display_directors(self, obj):
        """Отображение режиссёров в админке"""
        if obj.pk:
            directors = obj.directors.all()
            if directors:
                return ", ".join([f"{d.name} {d.surname}" for d in directors])
        return "-"

    display_directors.short_description = 'Режиссёры'

    def display_actors(self, obj):
        """Отображение актёров в админке"""
        if obj.pk:
            actors = obj.actors.all()
            if actors:
                return ", ".join([f"{a.name} {a.surname}" for a in actors[:5]]) + (f" и ещё {len(actors) - 5}" if len(actors) > 5 else "")
        return "-"

    display_actors.short_description = 'Актёры'


@admin.register(Screening)
class ScreeningAdmin(LoggingModelAdmin):
    list_display = ('movie', 'hall', 'start_time', 'end_time', 'ticket_price', 'is_active_screening')
    list_filter = ('hall', 'start_time', 'movie')
    search_fields = ('movie__title', 'hall__name')
    readonly_fields = ('end_time', 'created_at')
    list_per_page = 20
    date_hierarchy = 'start_time'
    form = ScreeningAdminForm

    fieldsets = (
        ('Основная информация', {
            'fields': ('movie', 'hall', 'start_date', 'start_time', 'end_time')
        }),
        ('Стоимость билета', {
            'fields': ('ticket_price', 'price_calculation'),
            'description': 'Цена рассчитывается автоматически на основе типа зала и времени сеанса'
        }),
        ('Системная информация', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )

    def ticket_price(self, obj):
        return f"{obj.ticket_price} руб."

    ticket_price.short_description = 'Цена'

    def is_active_screening(self, obj):
        return obj.start_time > timezone.now()

    is_active_screening.boolean = True
    is_active_screening.short_description = 'Активный'

    def save_model(self, request, obj, form, change):
        """Переопределяем сохранение для логирования"""
        super().save_model(request, obj, form, change)

        OperationLogger.log_model_operation(
            request=request,
            action_type='UPDATE' if change else 'CREATE',
            instance=obj,
            description=f"{'Изменен' if change else 'Создан'} сеанс. Цена: {obj.ticket_price} руб. (авторасчет)",
            module_type='SCREENINGS'
        )

    change_form_template = 'admin/ticket/screening/change_form.html'


@admin.register(Seat)
class SeatAdmin(LoggingModelAdmin):
    list_display = ('hall', 'row', 'number', 'created_at')
    list_filter = ('hall', 'row')
    search_fields = ('hall__name',)
    readonly_fields = ('created_at',)

    # Запрещаем добавление новых мест
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    def delete_selected(self, request, queryset):
        """Кастомное удаление с логированием"""
        count = queryset.count()
        for seat in queryset:
            OperationLogger.log_model_operation(
                request=request,
                action_type='DELETE',
                instance=seat,
                description=f'Удалено место {seat}',
                module_type='HALLS'
            )

        queryset.delete()
        self.message_user(
            request,
            f'✅ Удалено мест: {count}',
            messages.SUCCESS
        )

    delete_selected.short_description = "🗑️ Удалить выбранные места"


@admin.register(TicketStatus)
class TicketStatusAdmin(LoggingModelAdmin):
    """Админ-класс для управления статусами билетов"""
    list_display = ('code', 'name', 'can_be_refunded', 'is_active', 'created_at')
    list_filter = ('is_active', 'can_be_refunded')
    search_fields = ('code', 'name', 'description')
    readonly_fields = ('created_at',)
    list_editable = ('is_active', 'can_be_refunded')

    fieldsets = (
        (None, {
            'fields': ('code', 'name', 'description')
        }),
        ('Настройки', {
            'fields': ('is_active', 'can_be_refunded')
        }),
        ('Системная информация', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )


@admin.register(TicketGroup)
class TicketGroupAdmin(LoggingModelAdmin):
    list_display = ('id', 'user', 'screening', 'purchase_date', 'tickets_count', 'total_amount')
    list_filter = ('purchase_date', 'user', 'screening')
    search_fields = ('user__email', 'screening__movie__title', 'group_uuid')
    readonly_fields = ('group_uuid', 'created_at')

    fieldsets = (
        (None, {
            'fields': ('group_uuid', 'user', 'screening', 'purchase_date')
        }),
        ('Финансы', {
            'fields': ('total_amount', 'tickets_count')
        }),
        ('Системная информация', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )


@admin.register(Ticket)
class TicketAdmin(LoggingModelAdmin):
    list_display = ('id', 'user', 'screening', 'seat', 'get_status_display', 'price', 'created_at')
    list_filter = ('status', 'created_at', 'user')
    search_fields = ('user__email', 'screening__movie__title')
    readonly_fields = ('created_at', 'updated_at')
    list_per_page = 20
    raw_id_fields = ('user', 'screening', 'seat', 'ticket_group')

    fieldsets = (
        (None, {
            'fields': ('user', 'screening', 'seat', 'ticket_group')
        }),
        ('Финансы', {
            'fields': ('price',)
        }),
        ('QR-код', {
            'fields': ('qr_code',)
        }),
        ('Возврат', {
            'fields': ('status', 'refund_requested_at', 'refund_processed_at'),
            'classes': ('collapse',)
        }),
        ('Системная информация', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def get_status_display(self, obj):
        return obj.get_status_display()

    get_status_display.short_description = 'Статус'

    def has_add_permission(self, request):
        return False

    actions = ['process_refunds', 'cancel_refunds']

    def process_refunds(self, request, queryset):
        """Action для обработки возвратов"""
        processed = 0
        errors = []

        for ticket in queryset:
            if ticket.status and ticket.status.code == 'refund_requested':
                success, message = ticket.process_refund()
                if success:
                    processed += 1

                    OperationLogger.log_model_operation(
                        request=request,
                        action_type='UPDATE',
                        instance=ticket,
                        description=f'Обработка возврата билета #{ticket.id}',
                        module_type='TICKETS'
                    )
                else:
                    errors.append(f"Билет #{ticket.id}: {message}")

        if processed:
            self.message_user(request, f'✅ Обработано возвратов: {processed}')

        if errors:
            self.message_user(request, f'❌ Ошибки: {"; ".join(errors)}', messages.ERROR)

    process_refunds.short_description = "✅ Обработать возвраты"

    def cancel_refunds(self, request, queryset):
        """Action для отмены запросов на возврат"""
        cancelled = 0

        for ticket in queryset:
            if ticket.status and ticket.status.code == 'refund_requested':
                success, message = ticket.cancel_refund_request()
                if success:
                    cancelled += 1

                    OperationLogger.log_model_operation(
                        request=request,
                        action_type='UPDATE',
                        instance=ticket,
                        description=f'Отмена возврата билета #{ticket.id}',
                        module_type='TICKETS'
                    )

        self.message_user(request, f'✅ Отменено запросов на возврат: {cancelled}')

    cancel_refunds.short_description = "❌ Отменить запросы возврата"


@admin.register(PendingRegistration)
class PendingRegistrationAdmin(LoggingModelAdmin):
    list_display = ('email', 'name', 'surname', 'created_at', 'is_expired')
    list_filter = ('created_at',)
    search_fields = ('email', 'name', 'surname')
    readonly_fields = ('created_at',)

    # Запрещаем добавление новых ожидающих регистраций
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def is_expired(self, obj):
        return obj.is_expired()

    is_expired.boolean = True
    is_expired.short_description = 'Просрочен'


@admin.register(PasswordResetRequest)
class PasswordResetRequestAdmin(LoggingModelAdmin):
    list_display = ('user', 'created_at', 'expires_at', 'is_expired', 'is_used')
    list_filter = ('created_at', 'is_used')
    search_fields = ('user__email',)
    readonly_fields = ('created_at',)

    # Запрещаем добавление новых запросов восстановления пароля
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def is_expired(self, obj):
        return obj.is_expired()

    is_expired.boolean = True
    is_expired.short_description = 'Просрочен'


@admin.register(EmailChangeRequest)
class EmailChangeRequestAdmin(LoggingModelAdmin):
    list_display = ('user', 'new_email', 'created_at', 'expires_at', 'is_expired', 'is_used')
    list_filter = ('created_at', 'is_used')
    search_fields = ('user__email', 'new_email')
    readonly_fields = ('created_at',)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def is_expired(self, obj):
        return obj.is_expired()

    is_expired.boolean = True
    is_expired.short_description = 'Просрочен'


@admin.register(ActionType)
class ActionTypeAdmin(LoggingModelAdmin):
    list_display = ('code', 'name', 'created_at')
    search_fields = ('code', 'name', 'description')
    readonly_fields = ('created_at',)


@admin.register(ModuleType)
class ModuleTypeAdmin(LoggingModelAdmin):
    list_display = ('code', 'name', 'created_at')
    search_fields = ('code', 'name', 'description')
    readonly_fields = ('created_at',)


# Функции для actions
def create_full_backup(modeladmin, request, queryset):
    """Action для создания полного бэкапа"""
    try:
        call_command('backup_db')
        OperationLogger.log_backup_operation(
            request=request,
            backup_type='FULL',
            description='Создан полный бэкап базы данных'
        )
        messages.success(request, '✅ Full backup created successfully!')
    except Exception as e:
        OperationLogger.log_operation(
            request=request,
            action_type='BACKUP',
            module_type='BACKUPS',
            description=f'Ошибка создания бэкапа: {str(e)}',
            additional_data={'error': str(e)}
        )
        messages.error(request, f'❌ Error creating backup: {str(e)}')


create_full_backup.short_description = "📦 Create full database backup"


def create_daily_backup_today(modeladmin, request, queryset):
    """Action для создания дневного бэкапа за сегодня"""
    from datetime import date
    try:
        call_command('backup_db', f'--date={date.today()}')
        OperationLogger.log_backup_operation(
            request=request,
            backup_type='DAILY',
            description=f'Создан дневной бэкап за {date.today()}'
        )
        messages.success(request, f'✅ Daily backup for {date.today()} created successfully!')
    except Exception as e:
        OperationLogger.log_operation(
            request=request,
            action_type='BACKUP',
            module_type='BACKUPS',
            description=f'Ошибка создания дневного бэкапа: {str(e)}',
            additional_data={'error': str(e)}
        )
        messages.error(request, f'❌ Error creating daily backup: {str(e)}')


create_daily_backup_today.short_description = "📅 Create daily backup for today"


@admin.register(BackupManager)
class BackupManagerAdmin(LoggingModelAdmin):
    list_display = [
        'name', 'backup_type', 'backup_date', 'created_at',
        'file_status', 'file_size', 'restoration_status_display'
    ]
    list_filter = ['backup_type', 'created_at', 'backup_date', 'restoration_status']
    readonly_fields = [
        'name', 'backup_file', 'created_at', 'backup_type',
        'backup_date', 'restoration_status', 'restored_at', 'restoration_log', 'user'
    ]
    actions = [create_full_backup, create_daily_backup_today, 'restore_selected_backups']

    def file_status(self, obj):
        if obj.file_exists():
            return "✅ Available"
        return "❌ Missing"

    file_status.short_description = "Status"

    def file_size(self, obj):
        return obj.file_size()

    file_size.short_description = "Size"

    def restoration_status_display(self, obj):
        """Отображение статуса восстановления в списке"""
        status_html = f'<span style="color:{obj.get_restoration_color()}; font-weight:bold;">{obj.get_restoration_status_display()}</span>'

        if obj.restoration_log and obj.restoration_status == 'failed':
            status_html += f'<br><small style="color:#f44336;">Ошибка: {obj.restoration_log[:100]}...</small>'

        return format_html(status_html)

    restoration_status_display.short_description = 'Статус восстановления'

    def restore_selected_backups(self, request, queryset):
        """Action для восстановления выбранных бэкапов"""
        if queryset.count() > 1:
            self.message_user(
                request,
                '⚠️ Пожалуйста, выберите только один бэкап для восстановления',
                messages.WARNING
            )
            return

        backup = queryset.first()

        if not backup.file_exists():
            self.message_user(
                request,
                f'❌ Файл бэкапа "{backup.name}" не найден',
                messages.ERROR
            )
            return

        if backup.restoration_status == 'in_progress':
            self.message_user(
                request,
                f'⚠️ Восстановление из бэкапа "{backup.name}" уже выполняется',
                messages.WARNING
            )
            return

        self.message_user(
            request,
            f'🔄 Начато восстановление из бэкапа: {backup.name}. Проверьте статус на странице управления бэкапами.',
            messages.INFO
        )

        import threading
        thread = threading.Thread(
            target=backup.restore_database,
            args=(request.user,)
        )
        thread.daemon = True
        thread.start()

    restore_selected_backups.short_description = "🔄 Восстановить из выбранных бэкапов"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('backup-management/', self.admin_site.admin_view(self.backup_management_view),
                 name='ticket_backupmanager_backup_management'),
            path('restore-backup/<int:backup_id>/', self.admin_site.admin_view(self.restore_backup_view),
                 name='ticket_backupmanager_restore_backup'),
        ]
        return custom_urls + urls

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def delete_model(self, request, obj):
        """Логирование удаления бэкапа"""
        OperationLogger.log_operation(
            request=request,
            action_type='DELETE',
            module_type='BACKUPS',
            description=f'Удален файл бэкапа {obj.name}',
            object_id=obj.id,
            object_repr=obj.name
        )
        file_path = obj.get_file_path()
        if os.path.exists(file_path):
            os.remove(file_path)
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        """Логирование массового удаления бэкапов"""
        for obj in queryset:
            OperationLogger.log_operation(
                request=request,
                action_type='DELETE',
                module_type='BACKUPS',
                description=f'Удален файл бэкапа {obj.name} (mass delete)',
                object_id=obj.id,
                object_repr=obj.name
            )
            file_path = obj.get_file_path()
            if os.path.exists(file_path):
                os.remove(file_path)
        super().delete_queryset(request, queryset)

    def backup_management_view(self, request):
        """Страница управления бэкапами"""
        from django.core.management import call_command
        import io
        from contextlib import redirect_stdout

        backups = BackupManager.objects.all().order_by('-created_at')

        if request.method == 'POST':
            action = request.POST.get('action')

            if action == 'full_backup':
                try:
                    f = io.StringIO()
                    with redirect_stdout(f):
                        call_command('backup_db')
                    OperationLogger.log_backup_operation(
                        request=request,
                        backup_type='FULL',
                        description='Создан полный бэкап базы данных через страницу управления'
                    )
                    messages.success(request, '✅ Полный бэкап создан успешно!')

                except Exception as e:
                    OperationLogger.log_operation(
                        request=request,
                        action_type='BACKUP',
                        module_type='BACKUPS',
                        description=f'Ошибка создания полного бэкапа: {str(e)}',
                        additional_data={'error': str(e)}
                    )
                    messages.error(request, f'❌ Ошибка создания бэкапа: {str(e)}')

            elif action == 'daily_backup':
                backup_date = request.POST.get('backup_date')
                if backup_date:
                    try:
                        f = io.StringIO()
                        with redirect_stdout(f):
                            call_command('backup_db', f'--date={backup_date}')

                        OperationLogger.log_backup_operation(
                            request=request,
                            backup_type='DAILY',
                            description=f'Создан дневной бэкап за {backup_date} через страницу управления'
                        )

                        messages.success(request, f'✅ Дневной бэкап за {backup_date} создан успешно!')

                    except Exception as e:
                        OperationLogger.log_operation(
                            request=request,
                            action_type='BACKUP',
                            module_type='BACKUPS',
                            description=f'Ошибка создания дневного бэкапа: {str(e)}',
                            additional_data={'error': str(e)}
                        )
                        messages.error(request, f'❌ Ошибка создания бэкапа: {str(e)}')
                else:
                    messages.error(request, '❌ Выберите дату для дневного бэкапа')

            backups = BackupManager.objects.all().order_by('-created_at')

        context = {
            'title': 'Управление бэкапами',
            'backups': backups,
            **self.admin_site.each_context(request),
        }

        return render(request, 'admin/backup_management.html', context)

    def restore_backup_view(self, request, backup_id):
        """API endpoint для восстановления бэкапа"""
        try:
            backup = BackupManager.objects.get(id=backup_id)

            if not backup.can_be_restored():
                return JsonResponse({
                    'success': False,
                    'message': 'Бэкап недоступен для восстановления'
                })

            success, message = backup.restore_database(request.user)

            if success:
                OperationLogger.log_operation(
                    request=request,
                    action_type='BACKUP',
                    module_type='BACKUPS',
                    description=f'Восстановление БД из бэкапа: {backup.name}',
                    object_id=backup.id,
                    object_repr=backup.name
                )

            return JsonResponse({
                'success': success,
                'message': message,
                'backup_name': backup.name
            })

        except BackupManager.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Бэкап не найден'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Ошибка: {str(e)}'
            })


@admin.register(Report)
class ReportAdmin(LoggingModelAdmin):
    """Админ-класс для управления отчетами"""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('', self.admin_site.admin_view(self.reports_view), name='ticket_reports'),
        ]
        return custom_urls + urls

    def reports_view(self, request):
        """Страница отчетов в админке"""
        form = ReportFilterForm(request.GET or None)
        context = {
            'form': form,
            'report_data': None,
            'report_type': None,
            'title': 'Отчеты кинотеатра',
            **self.admin_site.each_context(request),
        }

        if form.is_valid():
            report_type = form.cleaned_data['report_type']
            period = form.cleaned_data['period']
            start_date = form.cleaned_data['start_date']
            end_date = form.cleaned_data['end_date']

            context['report_type'] = report_type
            context['filters'] = {
                'period': period,
                'start_date': start_date,
                'end_date': end_date
            }

            OperationLogger.log_operation(
                request=request,
                action_type='VIEW',
                module_type='REPORTS',
                description=f'Просмотр отчета: {report_type}',
                additional_data={
                    'period': period,
                    'start_date': str(start_date) if start_date else None,
                    'end_date': str(end_date) if end_date else None
                }
            )

            if report_type == 'revenue':
                context['report_data'] = ReportGenerator.get_revenue_stats(period, start_date, end_date)
            elif report_type == 'movies':
                context['report_data'] = ReportGenerator.get_popular_movies(start_date=start_date, end_date=end_date)
            elif report_type == 'halls':
                context['report_data'] = ReportGenerator.get_hall_occupancy(start_date=start_date, end_date=end_date)
            elif report_type == 'sales':
                context['report_data'] = ReportGenerator.get_sales_statistics(start_date=start_date, end_date=end_date)

        if request.method == 'POST' and 'export_pdf' in request.POST:
            if form.is_valid():
                report_type = form.cleaned_data['report_type']
                period = form.cleaned_data['period']
                start_date = form.cleaned_data['start_date']
                end_date = form.cleaned_data['end_date']

                OperationLogger.log_report_export(
                    request=request,
                    report_type=report_type,
                    format_type='PDF',
                    filters={
                        'period': period,
                        'start_date': str(start_date) if start_date else None,
                        'end_date': str(end_date) if end_date else None
                    }
                )

                if report_type == 'revenue':
                    report_data = ReportGenerator.get_revenue_stats(period, start_date, end_date)
                    report_title = f"Финансовая статистика ({period})"
                elif report_type == 'movies':
                    report_data = ReportGenerator.get_popular_movies(start_date=start_date, end_date=end_date)
                    report_title = "Популярные фильмы"
                elif report_type == 'halls':
                    report_data = ReportGenerator.get_hall_occupancy(start_date=start_date, end_date=end_date)
                    report_title = "Загруженность залов"
                elif report_type == 'sales':
                    report_data = ReportGenerator.get_sales_statistics(start_date=start_date, end_date=end_date)
                    report_title = "Статистика продаж"
                else:
                    report_data = []
                    report_title = "Отчет"

                try:
                    from .pdf_utils import generate_pdf_report
                    pdf_buffer = generate_pdf_report(report_data, report_type, report_title, {
                        'period': period,
                        'start_date': start_date,
                        'end_date': end_date
                    })

                    response = HttpResponse(pdf_buffer.getvalue(), content_type='application/pdf')
                    filename = f"отчет_{report_type}_{timezone.now().strftime('%Y%m%d_%H%M')}.pdf"
                    response['Content-Disposition'] = f'attachment; filename="{filename}"'
                    return response

                except Exception as e:
                    messages.error(request, f'Ошибка при генерации PDF: {str(e)}')

        return render(request, 'ticket/admin/reports.html', context)

    def changelist_view(self, request, extra_context=None):
        """Перенаправляем на страницу отчетов при входе в раздел"""
        return self.reports_view(request)


@admin.register(OperationLog)
class OperationLogAdmin(admin.ModelAdmin):
    """Админ-класс для логов операций"""

    list_display = [
        'timestamp', 'user', 'action_type', 'module_type',
        'description_short', 'object_repr_short', 'ip_address'
    ]
    list_filter = [
        'action_type', 'module_type', 'timestamp', 'user'
    ]
    search_fields = [
        'description', 'user__email', 'object_repr',
        'ip_address', 'additional_data'
    ]
    readonly_fields = [
        'timestamp', 'user', 'action_type', 'module_type',
        'description', 'ip_address', 'user_agent', 'object_id',
        'object_repr', 'additional_data_display'
    ]
    date_hierarchy = 'timestamp'
    list_per_page = 50
    raw_id_fields = ('user', 'action_type', 'module_type')

    def description_short(self, obj):
        return obj.description[:60] + '...' if len(obj.description) > 60 else obj.description

    description_short.short_description = 'Описание'

    def object_repr_short(self, obj):
        return obj.object_repr[:30] + '...' if obj.object_repr and len(obj.object_repr) > 30 else obj.object_repr

    object_repr_short.short_description = 'Объект'

    def additional_data_display(self, obj):
        return obj.get_additional_data_display()

    additional_data_display.short_description = 'Дополнительные данные'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    def get_urls(self):
        from django.urls import path
        urls = super().get_urls()
        custom_urls = [
            path('export-logs/', self.admin_site.admin_view(self.export_logs_view), name='ticket_operationlog_export'),
        ]
        return custom_urls + urls

    def export_logs_view(self, request):
        """Страница экспорта логов"""
        from .forms import LogExportForm

        form = LogExportForm(request.GET or None)
        context = {
            'form': form,
            'title': 'Экспорт логов операций',
            **self.admin_site.each_context(request),
        }

        if form.is_valid():
            queryset = self.get_export_queryset(form.cleaned_data)
            format_type = form.cleaned_data['format_type']

            OperationLogger.log_operation(
                request=request,
                action_type='EXPORT',
                module_type='SYSTEM',
                description=f'Экспорт логов в формате {format_type.upper()}',
                additional_data={
                    'start_date': str(form.cleaned_data.get('start_date')) if form.cleaned_data.get('start_date') else None,
                    'end_date': str(form.cleaned_data.get('end_date')) if form.cleaned_data.get('end_date') else None,
                    'action_type': str(form.cleaned_data.get('action_type')) if form.cleaned_data.get('action_type') else None,
                    'module_type': str(form.cleaned_data.get('module_type')) if form.cleaned_data.get('module_type') else None,
                }
            )

            if format_type == 'csv':
                return LogExporter.export_logs_to_csv(queryset)
            elif format_type == 'json':
                return LogExporter.export_logs_to_json(queryset)
            elif format_type == 'pdf':
                return LogExporter.export_logs_to_pdf(queryset)

        return render(request, 'ticket/admin/export_logs.html', context)

    def get_export_queryset(self, filters):
        """Получение queryset для экспорта на основе фильтров"""
        queryset = OperationLog.objects.all().select_related('user', 'action_type', 'module_type')

        if filters.get('start_date'):
            queryset = queryset.filter(timestamp__date__gte=filters['start_date'])
        if filters.get('end_date'):
            queryset = queryset.filter(timestamp__date__lte=filters['end_date'])

        if filters.get('action_type'):
            queryset = queryset.filter(action_type__code=filters['action_type'])
        if filters.get('module_type'):
            queryset = queryset.filter(module_type__code=filters['module_type'])

        if filters.get('user'):
            queryset = queryset.filter(user=filters['user'])

        return queryset.order_by('-timestamp')

    def changelist_view(self, request, extra_context=None):
        """Добавляем кнопку экспорта в changelist"""
        if extra_context is None:
            extra_context = {}
        extra_context['export_url'] = '/admin/ticket/operationlog/export-logs/'
        return super().changelist_view(request, extra_context=extra_context)