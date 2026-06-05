import os
from django.contrib.auth.admin import UserAdmin
from django.http import HttpResponse
from django.utils import timezone
from django.utils.html import format_html

from .export_utils import LogExporter
from .forms import ReportFilterForm, MovieForm, ScreeningAdminForm
from .logging_utils import OperationLogger
from .models import (
    PasswordResetRequest,
    Report, OperationLog, AgeRating, TicketStatus, Country,
    HallType, Director, Actor, MovieDirector, MovieActor,
    TicketGroup, ActionType, ModuleType, EmailChangeRequest,
    MovieGenre, ImportCache, ImportTask, APIRequestLog, APIToken, PriceHistory,
    MovieCountry
)
from .models import Hall, Movie, Screening, Seat, Ticket, User, Genre
from .report_utils import ReportGenerator
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.contrib import admin
from django.urls import path
from django import forms
from django.shortcuts import render
from django.contrib import messages
from django.core.management import call_command
import io
import sys
from .phone_utils import validate_and_format_phone
from django import forms
from django.core.exceptions import ValidationError
from django.contrib.auth.models import Group
from django.contrib.auth.admin import GroupAdmin
from django.forms import BaseInlineFormSet


class CustomGroupForm(forms.ModelForm):
    """Кастомная форма для группы с улучшенным отображением прав"""

    class Meta:
        model = Group
        fields = ('name', 'permissions')
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'style': 'width: 300px;'}),
        }


class CustomGroupAdmin(GroupAdmin):
    """Кастомный админ-класс для групп с улучшенным отображением прав"""

    form = CustomGroupForm
    filter_horizontal = ('permissions',)

    list_display = ('name', 'get_permissions_count')
    search_fields = ('name',)

    class Media:
        css = {
            'all': ['ticket/css/admin/user-permissions-fix.css']
        }

    def get_permissions_count(self, obj):
        return obj.permissions.count()

    get_permissions_count.short_description = 'Количество прав'

    def has_add_permission(self, request):
        return True

    def has_change_permission(self, request, obj=None):
        return True

    def has_delete_permission(self, request, obj=None):
        return True

# Переопределяем стандартную регистрацию Group
admin.site.unregister(Group)
admin.site.register(Group, CustomGroupAdmin)


class CustomUserChangeForm(forms.ModelForm):
    """Кастомная форма для редактирования пользователя с валидацией телефона"""

    class Meta:
        model = User
        fields = '__all__'

    def clean_number(self):
        number = self.cleaned_data.get('number')
        if number:
            try:
                return validate_and_format_phone(number)
            except ValidationError as e:
                raise ValidationError(str(e))
        return number


class CustomUserCreationForm(forms.ModelForm):
    """Кастомная форма для создания пользователя"""

    password1 = forms.CharField(
        label='Пароль',
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        help_text='Минимум 8 символов'
    )
    password2 = forms.CharField(
        label='Подтверждение пароля',
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )

    class Meta:
        model = User
        fields = ('email', 'name', 'surname', 'number')
        widgets = {
            'email': forms.EmailInput(attrs={'class': 'form-control', 'style': 'width: 300px;'}),
            'name': forms.TextInput(attrs={'class': 'form-control', 'style': 'width: 300px;'}),
            'surname': forms.TextInput(attrs={'class': 'form-control', 'style': 'width: 300px;'}),
            'number': forms.TextInput(attrs={'class': 'form-control', 'style': 'width: 300px;',
                                             'placeholder': 'Введите 10 цифр (9011234567)'}),
        }

    def clean_number(self):
        number = self.cleaned_data.get('number')
        if number:
            try:
                return validate_and_format_phone(number)
            except ValidationError as e:
                raise ValidationError(str(e))
        return number

    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            raise ValidationError("Пароли не совпадают")
        if len(password1) < 8:
            raise ValidationError("Пароль должен содержать минимум 8 символов")
        return password2

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user

class LoggingModelAdmin(admin.ModelAdmin):
    """Базовый класс для автоматического логирования операций в админке"""

    def save_model(self, request, obj, form, change):
        """Логирование создания/изменения объектов с детализацией изменений"""
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
            'OperationLog': 'SYSTEM',
        }

        module_type = module_map.get(obj.__class__.__name__, 'SYSTEM')

        # Подготавливаем дополнительные данные
        additional_data = None

        if change:
            # При UPDATE — собираем информацию об изменениях полей
            changes = OperationLogger._get_field_changes(form)
            if changes:
                additional_data = {
                    "action": "UPDATE",
                    "changes": changes,
                    "changed_fields": list(changes.keys()),
                    "changed_fields_count": len(changes)
                }

        # Сохраняем объект
        super().save_model(request, obj, form, change)

        # Логируем операцию с детальными данными об изменениях
        OperationLogger.log_model_operation(
            request=request,
            action_type=action,
            instance=obj,
            description=f"{action} {obj._meta.verbose_name} '{str(obj)}'",
            additional_data=additional_data
        )

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
            'OperationLog': 'SYSTEM',
        }

        module_type = module_map.get(obj.__class__.__name__, 'SYSTEM')

        OperationLogger.log_model_operation(
            request=request,
            action_type='DELETE',
            instance=obj,
            description=f"DELETE {obj._meta.verbose_name} '{str(obj)}'"
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
                'OperationLog': 'SYSTEM',
            }

            module_type = module_map.get(obj.__class__.__name__, 'SYSTEM')

            OperationLogger.log_model_operation(
                request=request,
                action_type='DELETE',
                instance=obj,
                description=f"DELETE {obj._meta.verbose_name} '{str(obj)}' (mass delete)"
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


class BaseMovieInlineFormSet(BaseInlineFormSet):
    """Базовый formset для inline-форм фильма"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Убеждаемся, что формы создаются правильно
        for form in self.forms:
            form.empty_permitted = False


class MovieGenreInlineForm(forms.ModelForm):
    """Форма для inline жанров"""

    class Meta:
        model = MovieGenre
        fields = ('genre',)
        widgets = {
            'genre': forms.Select(attrs={'class': 'form-control'})
        }


class MovieDirectorInlineForm(forms.ModelForm):
    """Форма для inline режиссёров"""

    class Meta:
        model = MovieDirector
        fields = ('director',)
        widgets = {
            'director': forms.Select(attrs={'class': 'form-control'})
        }


class MovieActorInlineForm(forms.ModelForm):
    """Форма для inline актёров"""

    class Meta:
        model = MovieActor
        fields = ('actor',)
        widgets = {
            'actor': forms.Select(attrs={'class': 'form-control'})
        }


class MovieGenreInline(admin.TabularInline):
    """Инлайн для жанров фильма"""
    model = MovieGenre
    form = MovieGenreInlineForm
    extra = 1
    verbose_name = 'Жанр'
    verbose_name_plural = 'Жанры'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('genre')

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'genre':
            kwargs['queryset'] = Genre.objects.all().order_by('name')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class MovieDirectorInline(admin.TabularInline):
    """Инлайн для режиссёров фильма"""
    model = MovieDirector
    form = MovieDirectorInlineForm
    extra = 1
    verbose_name = 'Режиссёр'
    verbose_name_plural = 'Режиссёры'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('director')

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'director':
            kwargs['queryset'] = Director.objects.all().order_by('surname', 'name')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class MovieActorInline(admin.TabularInline):
    """Инлайн для актёров фильма"""
    model = MovieActor
    form = MovieActorInlineForm
    extra = 1
    verbose_name = 'Актёр'
    verbose_name_plural = 'Актёры'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('actor')

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'actor':
            kwargs['queryset'] = Actor.objects.all().order_by('surname', 'name')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class MovieCountryInline(admin.TabularInline):
    """Инлайн для стран фильма"""
    model = MovieCountry
    extra = 1
    verbose_name = 'Страна'
    verbose_name_plural = 'Страны'

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'country':
            kwargs['queryset'] = Country.objects.all().order_by('name')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(Movie)
class MovieAdmin(LoggingModelAdmin):
    list_display = ('title', 'release_year', 'display_genres', 'display_countries', 'age_rating', 'duration_display', 'has_poster', 'screening_count')
    search_fields = ('title', 'description')
    list_filter = ('age_rating', 'release_year')
    list_per_page = 20
    form = MovieForm
    readonly_fields = ('created_at',)

    inlines = [MovieGenreInline, MovieDirectorInline, MovieActorInline, MovieCountryInline]

    fieldsets = (
        (None, {
            'fields': ('title', 'release_year', 'duration')
        }),
        ('Описание', {
            'fields': ('short_description', 'description')
        }),
        ('Классификация', {
            'fields': ('age_rating',)
        }),
        ('Медиа', {
            'fields': ('poster',)
        }),
        ('Системная информация', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )

    def display_countries(self, obj):
        countries = obj.countries.all()
        if countries:
            return ", ".join(c.name for c in countries)
        return "-"

    display_countries.short_description = 'Страны'

    def duration_display(self, obj):
        hours = obj.duration // 60
        minutes = obj.duration % 60
        if hours > 0:
            return f"{hours} ч {minutes} мин"
        return f"{minutes} мин"

    duration_display.short_description = 'Длительность'

    def display_genres(self, obj):
        genres = obj.genres.all()
        if genres:
            return ", ".join(g.name for g in genres)
        return "-"

    display_genres.short_description = 'Жанры'

    def has_poster(self, obj):
        return bool(obj.poster)

    has_poster.boolean = True
    has_poster.short_description = 'Есть постер'

    def screening_count(self, obj):
        return obj.screenings.count()

    screening_count.short_description = 'Сеансы'

    class Media:
        js = ['ticket/js/admin/movie-form-fix.js']
        css = {'all': ['ticket/css/admin/movie-form-fix.css']}

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

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('import-from-api/',
                 self.admin_site.admin_view(self.smart_import_view),
                 name='movie-import-from-api'),
        ]
        return custom_urls + urls

    def smart_import_view(self, request):
        """Новая страница умного импорта с информацией о токенах"""
        from django.core.management import call_command
        import io, sys

        # Получаем информацию о токенах
        try:
            token_info = KinopoiskDevClient.get_total_available_tokens()
        except Exception:
            token_info = {'tokens_count': 0, 'total_remaining': 0, 'total_limit': 0, 'tokens': []}

        if request.method == 'POST':
            form = SmartImportForm(request.POST)
            if form.is_valid():
                stdout = sys.stdout
                string_io = io.StringIO()
                sys.stdout = string_io

                try:
                    call_command(
                        'smart_import',
                        type=form.cleaned_data['import_type'],
                        pages=form.cleaned_data['pages'],
                        year_from=form.cleaned_data['year_from'],
                        year_to=form.cleaned_data['year_to'],
                        no_posters=not form.cleaned_data['import_posters'],
                        no_persons=not form.cleaned_data['import_persons'],
                    )
                    output = string_io.getvalue()
                    messages.success(request, "✅ Импорт успешно выполнен!")
                except Exception as e:
                    output = str(e)
                    messages.error(request, f"❌ Ошибка импорта: {e}")
                finally:
                    sys.stdout = stdout

                return render(request, 'admin/import_result.html', {
                    'title': 'Результат импорта',
                    'output': output,
                    'opts': self.model._meta,
                })
        else:
            form = SmartImportForm()

        context = {
            'title': 'Умный импорт фильмов из Poiskkino.dev',
            'form': form,
            'opts': self.model._meta,
            'token_info': token_info,
        }
        return render(request, 'admin/import_form.html', context)


@admin.register(MovieGenre)
class MovieGenreAdmin(LoggingModelAdmin):
    """Админ-класс для связей фильмов и жанров"""
    list_display = ('id', 'movie_title', 'genre_name', 'created_at')
    list_filter = ('genre', 'created_at')
    search_fields = ('movie__title', 'genre__name')
    readonly_fields = ('created_at',)
    autocomplete_fields = ['movie', 'genre']

    def movie_title(self, obj):
        return obj.movie.title

    movie_title.short_description = 'Фильм'

    def genre_name(self, obj):
        return obj.genre.name

    genre_name.short_description = 'Жанр'


@admin.register(User)
class CustomUserAdmin(LoggingModelAdmin, UserAdmin):
    list_display = ('email', 'name', 'surname', 'number', 'is_staff', 'is_email_verified')
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'is_email_verified', 'created_at')
    search_fields = ('email', 'name', 'surname', 'number')

    # Используем filter_horizontal для групп и прав
    filter_horizontal = ('groups', 'user_permissions')

    # Используем кастомные формы
    form = CustomUserChangeForm
    add_form = CustomUserCreationForm

    # Кастомные стили для filter_horizontal
    class Media:
        css = {
            'all': ['ticket/css/admin/user-permissions-fix.css']
        }

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Личная информация', {'fields': ('name', 'surname', 'number', 'created_at', 'updated_at')}),
        ('Верификация email', {'fields': ('is_email_verified', 'email_verification_code', 'email_verification_code_sent_at')}),
        ('Права доступа', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Важные даты', {'fields': ('last_login', 'date_joined')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'name', 'surname', 'number', 'password1', 'password2'),
        }),
    )

    readonly_fields = ('created_at', 'updated_at', 'last_login', 'date_joined')
    ordering = ('email',)

    def get_form(self, request, obj=None, **kwargs):
        if obj is None:
            kwargs['form'] = self.add_form
        else:
            kwargs['form'] = self.form
        return super().get_form(request, obj, **kwargs)

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
        return obj.movies.count()
    movie_count.short_description = 'Количество фильмов'


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


class DirectorInline(admin.TabularInline):
    """Inline для быстрого добавления режиссёров (не используется напрямую, но можно)"""
    model = Movie.directors.through
    extra = 1
    autocomplete_fields = ['director']
    verbose_name = 'Режиссёр'
    verbose_name_plural = 'Режиссёры'


class ActorInline(admin.TabularInline):
    """Inline для быстрого добавления актёров"""
    model = Movie.actors.through
    extra = 1
    autocomplete_fields = ['actor']
    verbose_name = 'Актёр'
    verbose_name_plural = 'Актёры'


@admin.register(Screening)
class ScreeningAdmin(LoggingModelAdmin):
    list_display = ('movie', 'hall', 'start_time', 'end_time', 'ticket_price', 'is_active_screening')
    list_filter = ('hall', 'start_time', 'movie')
    search_fields = ('movie__title', 'hall__name')
    readonly_fields = ('end_time', 'created_at', 'ticket_price')
    list_per_page = 20
    date_hierarchy = 'start_time'
    form = ScreeningAdminForm

    fieldsets = (
        ('Основная информация', {
            'fields': ('movie', 'hall', 'start_date', 'start_time_hour', 'start_time_minute', 'end_time')
        }),
        ('Стоимость билета', {
            'fields': ('price_calculation', 'ticket_price'),
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
                description=f'Удалено место {seat}'
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

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


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
                        description=f'Обработка возврата билета #{ticket.id}'
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
        """Подсвеченный JSON с форматированием"""
        if not obj.additional_data:
            return format_html('<span style="color: #888;">—</span>')

        try:
            import json
            formatted_json = json.dumps(obj.additional_data, ensure_ascii=False, indent=2)
        except (TypeError, ValueError):
            formatted_json = str(obj.additional_data)

        return format_html(
            '<pre><code class="language-json" style="max-height:400px; overflow:auto; '
            'background:#1e1e1e; color:#d4d4d4; padding:15px; border-radius:6px; '
            'font-size:13px; line-height:1.5; white-space:pre-wrap; word-break:break-word; '
            'border:1px solid #333;">{}</code></pre>',
            formatted_json
        )

    additional_data_display.short_description = 'Дополнительные данные'

    class Media:
        css = {
            'all': [
                'https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/atom-one-dark.min.css',
            ]
        }
        js = [
            'https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js',
            'https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/languages/json.min.js',
        ]

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


class ImportMoviesForm(forms.Form):
    pages = forms.IntegerField(
        label='Количество страниц',
        min_value=1,
        max_value=10,
        initial=2,
        help_text='По 50 фильмов на странице'
    )
    year_start = forms.IntegerField(
        label='Начальный год',
        min_value=2000,
        max_value=2025,
        initial=2020,
        help_text='Импортировать фильмы начиная с этого года'
    )
    download_posters = forms.BooleanField(
        label='Скачивать постеры',
        required=False,
        initial=True,
        help_text='Загружать изображения постеров'
    )
    import_persons = forms.BooleanField(
        label='Импортировать актёров и режиссёров',
        required=False,
        initial=True,
        help_text='Добавлять информацию об актёрах и режиссёрах'
    )
    skip_existing = forms.BooleanField(
        label='Пропускать существующие фильмы',
        required=False,
        initial=True,
        help_text='Не импортировать фильмы, которые уже есть в БД'
    )


# ═══════════════════════════════════════════════
# АДМИНКА ДЛЯ API ТОКЕНОВ И ИМПОРТА
# ═══════════════════════════════════════════════

@admin.register(APIToken)
class APITokenAdmin(admin.ModelAdmin):
    list_display = ('label', 'is_active', 'requests_today', 'daily_limit', 'remaining_display', 'total_requests', 'last_reset_date')
    list_filter = ('is_active',)
    search_fields = ('label', 'token')
    readonly_fields = ('requests_today', 'last_reset_date', 'total_requests')

    def remaining_display(self, obj):
        remaining = obj.remaining_today()
        color = 'green' if remaining > 50 else 'orange' if remaining > 10 else 'red'
        return format_html(
            '<span style="color:{}; font-weight:bold;">{}</span>',
            color, remaining
        )

    remaining_display.short_description = 'Осталось'

    actions = ['reset_daily_counters']

    def reset_daily_counters(self, request, queryset):
        queryset.update(requests_today=0, last_reset_date=timezone.now().date())
        self.message_user(request, 'Счётчики сброшены')

    reset_daily_counters.short_description = '🔄 Сбросить дневные счётчики'


class SmartImportForm(forms.Form):
    """Форма для умного импорта с выбором категорий"""

    import_type = forms.ChoiceField(
        choices=[
            ('movies', '🎬 Только фильмы'),
            ('genres', '🎭 Только жанры'),
            ('persons', '👥 Только персоны'),
            ('full', '📦 Полный импорт'),
        ],
        initial='movies',
        label='Тип импорта',
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    pages = forms.IntegerField(
        min_value=1, max_value=20, initial=3,
        label='Количество страниц (×50 фильмов)',
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )

    year_from = forms.IntegerField(
        min_value=2000, max_value=2026, initial=2024,
        label='Год от',
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )

    year_to = forms.IntegerField(
        min_value=2000, max_value=2026, initial=2025,
        label='Год до',
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )

    import_posters = forms.BooleanField(
        required=False, initial=True,
        label='🖼️ Скачивать постеры',
    )

    import_persons = forms.BooleanField(
        required=False, initial=True,
        label='👥 Импортировать актёров и режиссёров',
    )

    import_genres = forms.BooleanField(
        required=False, initial=True,
        label='🎭 Импортировать жанры',
    )

    skip_existing = forms.BooleanField(
        required=False, initial=True,
        label='⏭️ Пропускать существующие фильмы',
    )

    max_api_requests = forms.IntegerField(
        min_value=5, max_value=500, initial=50,
        label='🔌 Максимум API запросов',
        help_text='Импорт остановится при достижении лимита',
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )

# ═══════════════════════════════════════════════
# АДМИНКА ДЛЯ API ЛОГОВ С ЭКСПОРТОМ
# ═══════════════════════════════════════════════

@admin.register(APIRequestLog)
class APIRequestLogAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'token_label', 'endpoint', 'success_status', 'status_code', 'duration_ms')
    list_filter = ('success', 'token', 'endpoint', 'created_at')
    search_fields = ('endpoint', 'error_message')
    readonly_fields = ('token', 'endpoint', 'params', 'status_code', 'success', 'response_size', 'duration_ms', 'error_message', 'created_at')
    date_hierarchy = 'created_at'

    def token_label(self, obj):
        return obj.token.label if obj.token else '—'
    token_label.short_description = 'Токен'

    def success_status(self, obj):
        return '✅' if obj.success else '❌'
    success_status.short_description = ''

    def has_add_permission(self, request):
        return False

    actions = ['export_as_json', 'export_as_pdf']

    def export_as_json(self, request, queryset):
        """Экспорт выбранных API логов в JSON"""
        from .export_utils import LogExporter
        return LogExporter.export_api_logs_to_json(queryset)
    export_as_json.short_description = '📊 Экспорт выбранных API логов (JSON)'

    def export_as_pdf(self, request, queryset):
        """Экспорт выбранных API логов в PDF"""
        from .export_utils import LogExporter
        return LogExporter.export_api_logs_to_pdf(queryset)
    export_as_pdf.short_description = '📄 Экспорт выбранных API логов (PDF)'

    def get_urls(self):
        from django.urls import path
        urls = super().get_urls()
        custom_urls = [
            path('export-logs/', self.admin_site.admin_view(self.export_logs_view), name='ticket_apirequestlog_export'),
        ]
        return custom_urls + urls

    def export_logs_view(self, request):
        """Страница экспорта API логов"""
        from .forms import APIRequestLogExportForm

        form = APIRequestLogExportForm(request.GET or None)
        context = {
            'form': form,
            'title': 'Экспорт логов API запросов',
            'opts': self.model._meta,
            **self.admin_site.each_context(request),
        }

        if form.is_valid():
            queryset = self.get_export_queryset(form.cleaned_data)
            format_type = form.cleaned_data['format_type']

            from .logging_utils import OperationLogger
            OperationLogger.log_operation(
                request=request,
                action_type='EXPORT',
                module_type='SYSTEM',
                description=f'Экспорт API логов в формате {format_type.upper()}',
                additional_data={
                    'start_date': str(form.cleaned_data.get('start_date')) if form.cleaned_data.get('start_date') else None,
                    'end_date': str(form.cleaned_data.get('end_date')) if form.cleaned_data.get('end_date') else None,
                }
            )

            if format_type == 'json':
                return LogExporter.export_api_logs_to_json(queryset)
            elif format_type == 'pdf':
                return LogExporter.export_api_logs_to_pdf(queryset)

        return render(request, 'admin/ticket/apirequestlog/export_logs.html', context)

    def get_export_queryset(self, filters):
        """Получение queryset для экспорта API логов"""
        queryset = APIRequestLog.objects.all().select_related('token')

        if filters.get('start_date'):
            queryset = queryset.filter(created_at__date__gte=filters['start_date'])
        if filters.get('end_date'):
            queryset = queryset.filter(created_at__date__lte=filters['end_date'])

        if filters.get('success') is not None and filters.get('success') != '':
            queryset = queryset.filter(success=filters['success'])

        if filters.get('token'):
            queryset = queryset.filter(token=filters['token'])

        return queryset.order_by('-created_at')

    def changelist_view(self, request, extra_context=None):
        """Добавляем кнопку экспорта в changelist"""
        if extra_context is None:
            extra_context = {}
        extra_context['export_url'] = '/admin/ticket/apirequestlog/export-logs/'
        return super().changelist_view(request, extra_context=extra_context)

    def has_change_permission(self, request, obj=None):
        return False