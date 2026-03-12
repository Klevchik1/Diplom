import logging

logger = logging.getLogger(__name__)
from audioop import reverse
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from datetime import timedelta
from django.core.exceptions import ValidationError
import logging

logger = logging.getLogger(__name__)
import os
from django.conf import settings
from django.utils import timezone
import json
import subprocess
import uuid


class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    username = None
    email = models.EmailField(max_length=50, unique=True, verbose_name='Электронная почта')
    name = models.CharField(max_length=20, verbose_name='Имя')
    surname = models.CharField(max_length=20, verbose_name='Фамилия')
    number = models.CharField(max_length=20, verbose_name='Номер телефона')

    # Telegram fields
    telegram_chat_id = models.CharField(max_length=15, blank=True, null=True, verbose_name='ID чата в Telegram')
    telegram_username = models.CharField(max_length=32, blank=True, null=True, verbose_name='Имя пользователя в Telegram')
    is_telegram_verified = models.BooleanField(default=False, verbose_name='Статус привязки Telegram')
    telegram_verification_code = models.CharField(max_length=10, blank=True, null=True, verbose_name='Код для привязки Telegram')

    # Email verification fields
    is_email_verified = models.BooleanField(default=False, verbose_name='Статус верификации email')
    email_verification_code = models.CharField(max_length=6, blank=True, null=True, verbose_name='Код подтверждения email')
    email_verification_code_sent_at = models.DateTimeField(null=True, blank=True, verbose_name='Дата и время отправки кода')

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата и время создания')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Дата и время обновления')

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['name', 'surname', 'number']

    objects = CustomUserManager()

    def __str__(self):
        return f"{self.email} ({self.name} {self.surname})"

    def unlink_telegram(self):
        """Отвязать Telegram аккаунт"""
        self.telegram_chat_id = None
        self.telegram_username = None
        self.is_telegram_verified = False
        self.telegram_verification_code = None
        self.save(update_fields=['telegram_chat_id', 'telegram_username', 'is_telegram_verified', 'telegram_verification_code', 'updated_at'])

        logger.info(f"Telegram unlinked for user {self.email}")

        # Логируем операцию если есть request
        try:
            from .logging_utils import OperationLogger
            OperationLogger.log_system_operation(
                action_type='UPDATE',
                module_type='USERS',
                description=f'Отвязка Telegram для пользователя {self.email}',
                object_id=self.id,
                object_repr=str(self)
            )
        except Exception as e:
            logger.error(f"Error logging telegram unlink: {e}")

    def generate_verification_code(self):
        """Генерация кода подтверждения"""
        import random
        import string
        code = ''.join(random.choices(string.digits, k=6))
        self.telegram_verification_code = code
        self.is_telegram_verified = False
        self.save(update_fields=['telegram_verification_code', 'is_telegram_verified', 'updated_at'])
        logger.info(f"Generated verification code {code} for user {self.email}")
        return code

    # МЕТОДЫ ДЛЯ EMAIL
    def generate_email_verification_code(self):
        """Генерация кода подтверждения email"""
        import random
        import string
        from django.utils import timezone

        code = ''.join(random.choices(string.digits, k=6))
        self.email_verification_code = code
        self.email_verification_code_sent_at = timezone.now()
        self.is_email_verified = False
        self.save(update_fields=['email_verification_code', 'email_verification_code_sent_at', 'is_email_verified', 'updated_at'])
        logger.info(f"Generated email verification code for user {self.email}")
        return code

    def is_verification_code_expired(self):
        """Проверка истечения срока действия кода (10 минут)"""
        from django.utils import timezone
        if not self.email_verification_code_sent_at:
            return True
        expiration_time = self.email_verification_code_sent_at + timezone.timedelta(minutes=10)
        return timezone.now() > expiration_time

    def verify_email(self, code):
        """Подтверждение email"""
        if (self.email_verification_code == code and
                not self.is_verification_code_expired()):
            self.is_email_verified = True
            self.email_verification_code = None
            self.save(update_fields=['is_email_verified', 'email_verification_code', 'updated_at'])
            return True
        return False

    def requires_email_verification(self):
        """Проверяет, требуется ли подтверждение email для этого пользователя"""
        # Администраторам и суперпользователям не требуется подтверждение
        return not (self.is_staff or self.is_superuser)

    def save(self, *args, **kwargs):
        # Проверяем уникальность email при сохранении
        if self.email and User.objects.filter(email=self.email).exclude(pk=self.pk).exists():
            raise ValidationError('Пользователь с таким email уже существует')

        # Логируем создание/обновление пользователя
        is_new = self._state.adding

        # Устанавливаем created_at при создании
        if is_new and not self.created_at:
            self.created_at = timezone.now()

        # Всегда обновляем updated_at
        self.updated_at = timezone.now()

        super().save(*args, **kwargs)

        # Логируем после сохранения (когда есть pk)
        if is_new:
            try:
                from .logging_utils import OperationLogger
                OperationLogger.log_system_operation(
                    action_type='CREATE',
                    module_type='USERS',
                    description=f'Создан новый пользователь: {self.email}',
                    object_id=self.pk,
                    object_repr=str(self)
                )
            except Exception as e:
                logger.error(f"Error logging user creation: {e}")

    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['number']),
            models.Index(fields=['is_email_verified']),
            models.Index(fields=['-created_at']),
        ]


class Country(models.Model):
    """Модель для стран"""
    name = models.CharField(max_length=20, unique=True, verbose_name='Название страны')
    code = models.CharField(max_length=2, unique=True, verbose_name='Код страны')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата и время создания')

    def __str__(self):
        return f"{self.name} ({self.code})"

    class Meta:
        verbose_name = 'Страна'
        verbose_name_plural = 'Страны'
        ordering = ['name']


class HallType(models.Model):
    """Модель для типов залов с коэффициентами цен"""
    name = models.CharField(max_length=20, unique=True, verbose_name='Название типа зала')
    description = models.TextField(blank=True, null=True, verbose_name='Описание типа зала')
    price_coefficient = models.DecimalField(max_digits=3, decimal_places=2, default=1.0, verbose_name='Коэффициент стоимости')
    base_price = models.DecimalField(max_digits=6, decimal_places=2, verbose_name='Базовая цена для этого типа')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата и время создания')

    def __str__(self):
        return f"{self.name} (коэф. {self.price_coefficient})"

    class Meta:
        verbose_name = 'Тип зала'
        verbose_name_plural = 'Типы залов'


class Hall(models.Model):
    name = models.CharField(max_length=20, verbose_name='Название зала')
    rows = models.IntegerField(verbose_name='Количество рядов')
    seats_per_row = models.IntegerField(verbose_name='Количество мест в ряду')
    description = models.TextField(blank=True, null=True, verbose_name='Описание зала')
    hall_type = models.ForeignKey(HallType, on_delete=models.PROTECT, verbose_name='Тип зала', related_name='halls')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата и время создания')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Дата и время обновления')

    def __str__(self):
        return f"{self.name} ({self.hall_type.name})"

    def delete(self, *args, **kwargs):
        """Каскадное удаление всех связанных объектов"""
        try:
            # Сначала удаляем все сеансы в этом зале
            screenings = Screening.objects.filter(hall=self)
            for screening in screenings:
                screening.delete()

            # Места удалятся автоматически благодаря CASCADE
        except Exception as e:
            logger.error(f"Error in cascade delete for hall {self.name}: {e}")

        super().delete(*args, **kwargs)

    def save(self, *args, **kwargs):
        logger.info(f"Сохранение зала {self.name}, новый: {self._state.adding}")

        # Устанавливаем created_at при создании
        if self._state.adding and not self.created_at:
            self.created_at = timezone.now()

        # Всегда обновляем updated_at
        self.updated_at = timezone.now()

        super().save(*args, **kwargs)

        if self._state.adding:
            logger.info(f"Создаю места для нового зала {self.name}")
            self.create_seats()

    def create_seats(self):
        logger.info(f"Создание мест для зала {self.name}: {self.rows} рядов × {self.seats_per_row} мест")
        for row in range(1, self.rows + 1):
            for seat_num in range(1, self.seats_per_row + 1):
                Seat.objects.get_or_create(
                    hall=self,
                    row=row,
                    number=seat_num
                )

    class Meta:
        verbose_name = "Зал"
        verbose_name_plural = "Залы"
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['hall_type']),
        ]


class Genre(models.Model):
    name = models.CharField(max_length=20, unique=True, verbose_name='Название жанра')
    description = models.TextField(blank=True, null=True, verbose_name='Описание жанра')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        # Приводим имя к стандартному виду: первая буква заглавная, остальные строчные
        if self.name:
            # Убираем лишние пробелы
            self.name = ' '.join(self.name.strip().split())
            # Делаем первую букву заглавной, остальные строчные
            self.name = self.name.title()

        # Проверяем уникальность перед сохранением
        if Genre.objects.filter(name=self.name).exclude(pk=self.pk).exists():
            raise ValidationError(f'Жанр "{self.name}" уже существует')

        # Устанавливаем created_at при создании
        if self._state.adding and not self.created_at:
            self.created_at = timezone.now()

        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Жанр"
        verbose_name_plural = "Жанры"
        indexes = [
            models.Index(fields=['name']),
        ]


class AgeRating(models.Model):
    """Модель для возрастных рейтингов """
    name = models.CharField(
        max_length=10,
        unique=True,
        verbose_name='Возрастной рейтинг',
        help_text='Например: 0+, 6+, 12+, 16+, 18+'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата и время создания')

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Возрастной рейтинг'
        verbose_name_plural = 'Возрастные рейтинги'
        ordering = ['name']


class Director(models.Model):
    """Модель для режиссёров"""
    name = models.CharField(max_length=20, verbose_name='Имя режиссёра')
    surname = models.CharField(max_length=20, verbose_name='Фамилия режиссёра')
    birth_date = models.DateField(null=True, blank=True, verbose_name='Дата рождения')
    country = models.ForeignKey(Country, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Страна', related_name='directors')
    biography = models.TextField(blank=True, null=True, verbose_name='Биография')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата и время создания')

    def __str__(self):
        return f"{self.name} {self.surname}"

    class Meta:
        verbose_name = 'Режиссёр'
        verbose_name_plural = 'Режиссёры'
        indexes = [
            models.Index(fields=['surname', 'name']),
        ]


class Actor(models.Model):
    """Модель для актёров"""
    name = models.CharField(max_length=20, verbose_name='Имя актёра')
    surname = models.CharField(max_length=20, verbose_name='Фамилия актёра')
    birth_date = models.DateField(null=True, blank=True, verbose_name='Дата рождения')
    country = models.ForeignKey(Country, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Страна', related_name='actors')
    biography = models.TextField(blank=True, null=True, verbose_name='Биография')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата и время создания')

    def __str__(self):
        return f"{self.name} {self.surname}"

    class Meta:
        verbose_name = 'Актёр'
        verbose_name_plural = 'Актёры'
        indexes = [
            models.Index(fields=['surname', 'name']),
        ]


class Movie(models.Model):
    title = models.CharField(max_length=50, verbose_name='Название фильма')
    short_description = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        verbose_name='Короткое описание'
    )
    description = models.TextField(
        max_length=1000,
        verbose_name='Полное описание'
    )
    duration = models.IntegerField(verbose_name='Продолжительность в минутах')  # Изменено с DurationField на IntegerField
    poster = models.ImageField(
        upload_to='movie_posters/',
        blank=True,
        null=True,
        verbose_name='Постер фильма'
    )
    release_year = models.IntegerField(verbose_name='Год выпуска')
    genre = models.ForeignKey(
        Genre,
        on_delete=models.PROTECT,
        verbose_name='Жанр',
        related_name='movies'
    )
    age_rating = models.ForeignKey(
        AgeRating,
        on_delete=models.PROTECT,
        verbose_name='Возрастное ограничение',
        related_name='movies'
    )
    directors = models.ManyToManyField(
        Director,
        through='MovieDirector',
        verbose_name='Режиссёры',
        related_name='movies'
    )
    actors = models.ManyToManyField(
        Actor,
        through='MovieActor',
        verbose_name='Актёры',
        related_name='movies'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата и время создания')

    def __str__(self):
        return f"{self.title} ({self.release_year})"

    def save(self, *args, **kwargs):
        # Если короткое описание не задано, создаем его из полного
        if not self.short_description and self.description:
            self.short_description = self.description[:197] + '...' if len(self.description) > 200 else self.description

        # Устанавливаем created_at при создании
        if self._state.adding and not self.created_at:
            self.created_at = timezone.now()

        super().save(*args, **kwargs)

    def get_duration_display(self):
        """Возвращает длительность в формате ЧЧ:ММ"""
        hours = self.duration // 60
        minutes = self.duration % 60
        if hours > 0:
            return f"{hours} ч {minutes} мин"
        return f"{minutes} мин"

    class Meta:
        verbose_name = "Фильм"
        verbose_name_plural = "Фильмы"
        indexes = [
            models.Index(fields=['title']),
            models.Index(fields=['genre']),
            models.Index(fields=['age_rating']),
            models.Index(fields=['release_year']),
        ]


class MovieDirector(models.Model):
    """Связующая модель для фильмов и режиссёров"""
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE, verbose_name='Фильм')
    director = models.ForeignKey(Director, on_delete=models.CASCADE, verbose_name='Режиссёр')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата и время создания')

    class Meta:
        verbose_name = 'Режиссёр фильма'
        verbose_name_plural = 'Режиссёры фильмов'
        unique_together = ('movie', 'director')


class MovieActor(models.Model):
    """Связующая модель для фильмов и актёров"""
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE, verbose_name='Фильм')
    actor = models.ForeignKey(Actor, on_delete=models.CASCADE, verbose_name='Актёр')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата и время создания')

    class Meta:
        verbose_name = 'Актёр фильма'
        verbose_name_plural = 'Актёры фильмов'
        unique_together = ('movie', 'actor')


class Screening(models.Model):
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE, verbose_name='Фильм', related_name='screenings')
    hall = models.ForeignKey(Hall, on_delete=models.CASCADE, verbose_name='Зал', related_name='screenings')
    start_time = models.DateTimeField(verbose_name='Дата и время начала')
    end_time = models.DateTimeField(verbose_name='Дата и время окончания', blank=True, null=True)
    ticket_price = models.DecimalField(max_digits=6, decimal_places=2, verbose_name='Стоимость')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата и время создания')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Сохраняем старые значения, но только если они существуют
        self._old_hall = self.hall if self.pk else None
        self._old_start_time = self.start_time if self.pk else None

    def clean(self):
        # ВАЖНО: Сначала рассчитываем end_time если нужно
        if self.movie and self.start_time:
            # Конвертируем длительность из минут в timedelta
            duration_timedelta = timedelta(minutes=self.movie.duration)
            self.end_time = self.start_time + duration_timedelta + timedelta(minutes=10)

        if self.start_time and self.end_time and self.start_time >= self.end_time:
            raise ValidationError("Время окончания сеанса должно быть позже времени начала")

        # Проверяем время работы кинотеатра
        if self.start_time:
            local_start = timezone.localtime(self.start_time)
            if local_start.hour < 8 or local_start.hour >= 23:
                raise ValidationError("Сеансы могут начинаться только с 8:00 до 23:00")

        # Более гибкая проверка окончания сеанса
        if self.end_time:
            local_end = timezone.localtime(self.end_time)
            # Если сеанс заканчивается в 0:xx следующего дня
            if local_end.hour == 0 and local_end.minute <= 30:
                # Разрешаем сеансы, которые заканчиваются до 00:30
                pass
            elif local_end.hour >= 24 or (local_end.hour == 0 and local_end.minute > 30):
                raise ValidationError("Сеанс должен заканчиваться до 00:30 следующего дня")

        if self.hall and self.start_time and self.end_time:
            overlapping_screenings = Screening.objects.filter(
                hall=self.hall,
                start_time__lt=self.end_time,
                end_time__gt=self.start_time
            ).exclude(pk=self.pk)

            if overlapping_screenings.exists():
                raise ValidationError("Сеанс пересекается с другим сеансом в этом зале")

    def calculate_ticket_price(self):
        """Рассчитать стоимость билета на основе типа зала и времени"""
        from decimal import Decimal

        if not self.hall or not self.hall.hall_type:
            return Decimal('350.00')

        hall_type = self.hall.hall_type
        base_price = hall_type.base_price
        coefficient = hall_type.price_coefficient

        # Множитель по времени суток
        time_multiplier = self.get_time_multiplier()

        final_price = base_price * coefficient * Decimal(str(time_multiplier))
        # Округляем до целого числа
        return Decimal(str(int(final_price)))

    def get_time_multiplier(self):
        """Определить множитель по времени суток"""
        if not self.start_time:
            return 1.0

        local_time = timezone.localtime(self.start_time)
        hour = local_time.hour

        if 8 <= hour < 12:
            return 0.7  # утро
        elif 12 <= hour < 16:
            return 0.9  # день
        elif 16 <= hour < 20:
            return 1.2  # вечер
        else:
            return 1.4  # ночь

    def get_price_calculation_explanation(self):
        """Сгенерировать объяснение расчета цены"""
        if not self.hall or not self.start_time:
            return "Выберите зал и время сеанса для расчета цены"

        hall_type = self.hall.hall_type
        base_price = hall_type.base_price
        coefficient = hall_type.price_coefficient
        time_multiplier = self.get_time_multiplier()
        calculated_price = self.calculate_ticket_price()

        time_desc = self.get_time_description()

        explanation = (
            f"📊 РАСЧЕТ СТОИМОСТИ БИЛЕТА:\n"
            f"──────────────────────────\n"
            f"• Зал: '{self.hall.name}' → тип: {hall_type.name}\n"
            f"• Базовая цена типа зала: {base_price} руб.\n"
            f"• Коэффициент типа зала: {coefficient}\n"
            f"• Время сеанса: {time_desc}\n"
            f"• Множитель времени: {time_multiplier}\n"
            f"──────────────────────────\n"
            f"• ИТОГО: {base_price} × {coefficient} × {time_multiplier} = {calculated_price} руб.\n"
            f"──────────────────────────\n"
            f"*Цена фиксируется при сохранении"
        )

        return explanation

    def get_time_description(self):
        """Получить описание времени сеанса"""
        if not self.start_time:
            return "время не указано"

        local_time = timezone.localtime(self.start_time)
        hour = local_time.hour

        if 8 <= hour < 12:
            return f"утро ({hour}:00)"
        elif 12 <= hour < 16:
            return f"день ({hour}:00)"
        elif 16 <= hour < 20:
            return f"вечер ({hour}:00)"
        else:
            return f"ночь ({hour}:00)"

    @property
    def calculated_price_display(self):
        """Только для чтения: отображение рассчитанной цены"""
        if self.hall and self.start_time:
            return f"{self.calculate_ticket_price()} руб. (авторасчет)"
        return "—"

    def save(self, *args, **kwargs):
        # Пересчитываем end_time при сохранении
        if self.movie and self.start_time:
            duration_timedelta = timedelta(minutes=self.movie.duration)
            self.end_time = self.start_time + duration_timedelta + timedelta(minutes=10)

        # Автоматически рассчитываем цену
        if not self.pk:  # Новый объект
            if self.hall and self.start_time:
                self.ticket_price = self.calculate_ticket_price()
            else:
                # Устанавливаем цену по умолчанию, если нет зала или времени
                self.ticket_price = 350
        else:
            # Для существующего объекта проверяем, изменились ли зал или время
            if self._old_hall is not None or self._old_start_time is not None:
                if (self.hall != self._old_hall) or (self.start_time != self._old_start_time):
                    if self.hall and self.start_time:
                        self.ticket_price = self.calculate_ticket_price()

        # Устанавливаем created_at при создании
        if self._state.adding and not self.created_at:
            self.created_at = timezone.now()

        # Вызываем clean для дополнительных проверок
        self.clean()
        super().save(*args, **kwargs)

        # Обновляем старые значения
        if self.pk:
            self._old_hall = self.hall
            self._old_start_time = self.start_time

    def __str__(self):
        if self.movie and self.hall and self.start_time:
            return f"{self.movie.title} - {self.hall.name} ({self.start_time.strftime('%d.%m.%Y %H:%M')})"
        return "Новый сеанс"

    class Meta:
        verbose_name = "Сеанс"
        verbose_name_plural = "Сеансы"
        indexes = [
            models.Index(fields=['start_time']),
            models.Index(fields=['hall', 'start_time']),
            models.Index(fields=['movie', 'start_time']),
        ]


class Seat(models.Model):
    hall = models.ForeignKey(Hall, on_delete=models.CASCADE, related_name='seats')
    row = models.IntegerField(verbose_name='Ряд')
    number = models.IntegerField(verbose_name='Место')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата и время создания')

    def __str__(self):
        return f"{self.hall.name} - Ряд {self.row}, Место {self.number}"

    class Meta:
        verbose_name = "Место"
        verbose_name_plural = "Места"
        unique_together = ('hall', 'row', 'number')
        indexes = [
            models.Index(fields=['hall', 'row']),
        ]


class TicketGroup(models.Model):
    """Модель для группировки билетов одной покупки"""
    group_uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, verbose_name='Уникальный идентификатор группы')
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='Пользователь', related_name='ticket_groups')
    screening = models.ForeignKey(Screening, on_delete=models.CASCADE, verbose_name='Сеанс', related_name='ticket_groups')
    purchase_date = models.DateTimeField(verbose_name='Дата и время покупки')
    total_amount = models.DecimalField(max_digits=8, decimal_places=2, verbose_name='Общая сумма покупки')
    tickets_count = models.IntegerField(verbose_name='Количество билетов в группе')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата и время создания')

    def __str__(self):
        return f"Группа #{self.id} ({self.tickets_count} билетов) - {self.purchase_date.strftime('%d.%m.%Y %H:%M')}"

    def save(self, *args, **kwargs):
        if self._state.adding and not self.created_at:
            self.created_at = timezone.now()
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = 'Группа билетов'
        verbose_name_plural = 'Группы билетов'
        indexes = [
            models.Index(fields=['group_uuid']),
            models.Index(fields=['user', 'purchase_date']),
            models.Index(fields=['screening']),
        ]


class TicketStatus(models.Model):
    """Модель для статусов билетов"""
    code = models.CharField(
        max_length=20,
        unique=True,
        verbose_name='Код статуса'
    )
    name = models.CharField(
        max_length=20,
        verbose_name='Название статуса'
    )
    description = models.TextField(
        blank=True,
        null=True,
        verbose_name='Описание статуса'
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name='Активен ли статус'
    )
    can_be_refunded = models.BooleanField(
        default=False,
        verbose_name='Можно ли вернуть билет из этого статуса'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата и время создания')

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        is_new = self._state.adding

        if is_new and not self.created_at:
            self.created_at = timezone.now()

        super().save(*args, **kwargs)

        # Логируем создание статуса
        if is_new:
            try:
                from .logging_utils import OperationLogger
                # Получаем или создаем тип действия CREATE
                from .models import ActionType
                create_action, _ = ActionType.objects.get_or_create(
                    code='CREATE',
                    defaults={'name': 'Создание', 'description': 'Создание объекта'}
                )

                OperationLogger.log_system_operation(
                    action_type=create_action,  # Передаем объект ActionType, а не строку
                    module_type='SYSTEM',
                    description=f'Создан статус билета: {self.name} ({self.code})',
                    object_id=self.pk,
                    object_repr=str(self)
                )
            except Exception as e:
                logger.error(f"Error logging ticket status creation: {e}")

    class Meta:
        verbose_name = 'Статус билета'
        verbose_name_plural = 'Статусы билетов'
        ordering = ['id']


class Ticket(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tickets')
    screening = models.ForeignKey(Screening, on_delete=models.CASCADE, related_name='tickets')
    seat = models.ForeignKey(Seat, on_delete=models.CASCADE, related_name='tickets')
    qr_code = models.CharField(max_length=255, blank=True, null=True, verbose_name='Путь к файлу QR-кода')
    price = models.DecimalField(max_digits=6, decimal_places=2, verbose_name='Цена билета')
    refund_requested_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Дата и время запроса возврата'
    )
    refund_processed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Дата и время обработки возврата'
    )
    status = models.ForeignKey(
        TicketStatus,
        on_delete=models.PROTECT,
        verbose_name='Статус билета',
        related_name='tickets'
    )
    ticket_group = models.ForeignKey(
        TicketGroup,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name='Группа билетов',
        related_name='tickets'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата и время создания')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Дата и время обновления')

    class Meta:
        unique_together = ('screening', 'seat')
        verbose_name = "Билет"
        verbose_name_plural = "Билеты"
        indexes = [
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['screening']),
            models.Index(fields=['ticket_group']),
            models.Index(fields=['status']),
            models.Index(fields=['-created_at']),
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Устанавливаем статус по умолчанию при создании
        if not self.pk and not self.status_id:
            try:
                default_status = TicketStatus.objects.filter(is_active=True).first()
                if default_status:
                    self.status = default_status
            except TicketStatus.DoesNotExist:
                pass

    def save(self, *args, **kwargs):
        # Проверяем, что место свободно (только для новых билетов)
        if not self.pk:  # Новый билет
            existing_ticket = Ticket.objects.filter(
                screening=self.screening,
                seat=self.seat
            ).exists()

            if existing_ticket:
                raise ValidationError(f"Место {self.seat.row}-{self.seat.number} уже занято на этот сеанс")

        # Автоматически устанавливаем статус при первом сохранении
        if not self.pk and not self.status_id:
            try:
                active_status = TicketStatus.objects.filter(code='active', is_active=True).first()
                if active_status:
                    self.status = active_status
                else:
                    # Создаем статус по умолчанию, если его нет
                    active_status = TicketStatus.objects.create(
                        code='active',
                        name='Активный',
                        description='Билет активен и действителен',
                        is_active=True,
                        can_be_refunded=True
                    )
                    self.status = active_status
            except Exception as e:
                logger.error(f"Error setting default ticket status: {e}")

        # Устанавливаем цену из сеанса, если не указана
        if not self.price and self.screening:
            self.price = self.screening.ticket_price

        # Устанавливаем created_at при создании
        if self._state.adding and not self.created_at:
            self.created_at = timezone.now()

        # Всегда обновляем updated_at
        self.updated_at = timezone.now()

        super().save(*args, **kwargs)

    def can_be_refunded(self):
        """Проверяет, можно ли вернуть билет с учетом всех условий"""
        from django.utils import timezone

        if not self.status or self.status.code != 'active':
            return False, 'Билет не активен'

        # Проверяем временное ограничение: не менее 30 минут до начала
        time_until_screening = self.screening.start_time - timezone.now()
        minutes_until = time_until_screening.total_seconds() / 60

        if minutes_until < 30:
            return False, f'Возврат невозможен. До сеанса осталось {int(minutes_until)} минут'

        # Проверяем что сеанс еще не начался
        if self.screening.start_time <= timezone.now():
            return False, 'Сеанс уже начался'

        return True, 'Возврат возможен'

    def request_refund(self):
        """Запрос возврата билета с автоматической обработкой"""
        from django.utils import timezone

        # Проверяем можно ли вернуть
        can_refund, message = self.can_be_refunded()

        if not can_refund:
            return False, message

        try:
            # Если все условия соблюдены, сразу обрабатываем возврат
            refunded_status = TicketStatus.objects.get(code='refunded')

            # ВАЖНО: Сначала удаляем билет, чтобы освободить место
            # Но сохраняем информацию о возврате для логирования
            movie_title = self.screening.movie.title
            seat_info = f"Ряд {self.seat.row}, Место {self.seat.number}"
            user_email = self.user.email
            price = self.price

            # Удаляем билет (освобождаем место)
            self.delete()

            # Логируем возврат
            logger.info(f"Автоматический возврат билета на фильм {movie_title}, место {seat_info}")

            # Логируем операцию возврата
            try:
                from .logging_utils import OperationLogger
                OperationLogger.log_system_operation(
                    action_type='UPDATE',
                    module_type='TICKETS',
                    description=f'Билет на фильм {movie_title} (место {seat_info}) возвращен',
                    additional_data={
                        'movie': movie_title,
                        'user': user_email,
                        'seat': seat_info,
                        'refund_amount': str(price),
                        'reason': 'Автоматический возврат по запросу пользователя'
                    }
                )
            except Exception as e:
                logger.error(f"Error logging refund: {e}")

            return True, '✅ Билет успешно возвращен! Место освобождено.'

        except TicketStatus.DoesNotExist as e:
            logger.error(f"Статус 'refunded' не найден: {e}")
            return False, 'Ошибка: статус возврата не найден в системе'
        except Exception as e:
            logger.error(f"Ошибка при возврате билета #{self.id}: {e}")
            return False, f'Ошибка при обработке возврата: {str(e)}'

    def process_refund(self):
        """Обработка возврата (админ)"""
        try:
            if self.status.code != 'refund_requested':
                return False, 'Билет не запрашивал возврат'

            # Сохраняем информацию для логирования
            movie_title = self.screening.movie.title
            seat_info = f"Ряд {self.seat.row}, Место {self.seat.number}"
            user_email = self.user.email
            price = self.price

            # Удаляем билет (освобождаем место)
            self.delete()

            # Логируем операцию возврата
            try:
                from .logging_utils import OperationLogger
                OperationLogger.log_system_operation(
                    action_type='UPDATE',
                    module_type='TICKETS',
                    description=f'Билет на фильм {movie_title} (место {seat_info}) возвращен администратором',
                    additional_data={
                        'movie': movie_title,
                        'user': user_email,
                        'seat': seat_info,
                        'refund_amount': str(price),
                        'reason': 'Возврат обработан администратором'
                    }
                )
            except Exception as e:
                logger.error(f"Error logging refund: {e}")

            return True, 'Возврат обработан, место освобождено'

        except TicketStatus.DoesNotExist:
            return False, 'Статус не найден'

    def cancel_refund_request(self):
        """Отмена запроса на возврат"""
        try:
            active_status = TicketStatus.objects.get(code='active')
            if self.status.code != 'refund_requested':
                return False, 'Билет не запрашивал возврат'

            self.status = active_status
            self.refund_requested_at = None
            self.updated_at = timezone.now()
            self.save()
            return True, 'Запрос на возврат отменен'
        except TicketStatus.DoesNotExist:
            return False, 'Статус "Активный" не найден'

    def get_status_display(self):
        """Получить отображаемое название статуса"""
        return self.status.name if self.status else "Неизвестно"

    def get_pdf_url(self):
        return reverse('download_ticket_single', args=[self.id])

    def get_group_tickets(self):
        """Получить все билеты из той же группы"""
        if self.ticket_group:
            # Возвращаем все билеты группы, включая существующие
            return Ticket.objects.filter(ticket_group=self.ticket_group)
        return Ticket.objects.filter(id=self.id)


@receiver(post_save, sender=Hall)
def create_hall_seats(sender, instance, created, **kwargs):
    if created:
        for row in range(1, instance.rows + 1):
            for seat_num in range(1, instance.seats_per_row + 1):
                Seat.objects.get_or_create(
                    hall=instance,
                    row=row,
                    number=seat_num
                )


class ActionType(models.Model):
    """Модель для типов действий в логах"""
    code = models.CharField(max_length=20, unique=True, verbose_name='Код действия')
    name = models.CharField(max_length=30, verbose_name='Название действия')
    description = models.TextField(blank=True, null=True, verbose_name='Описание действия')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата и время создания')

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Тип действия'
        verbose_name_plural = 'Типы действий'


class ModuleType(models.Model):
    """Модель для типов модулей в логах"""
    code = models.CharField(max_length=20, unique=True, verbose_name='Код модуля')
    name = models.CharField(max_length=30, verbose_name='Название модуля')
    description = models.TextField(blank=True, null=True, verbose_name='Описание модуля')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата и время создания')

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Тип модуля'
        verbose_name_plural = 'Типы модулей'


class OperationLog(models.Model):
    """Модель для логирования операций в системе"""
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Пользователь',
        related_name='operation_logs'
    )
    action_type = models.ForeignKey(
        ActionType,
        on_delete=models.PROTECT,
        verbose_name='Тип действия',
        related_name='operation_logs'
    )
    module_type = models.ForeignKey(
        ModuleType,
        on_delete=models.PROTECT,
        verbose_name='Модуль системы',
        related_name='operation_logs'
    )
    description = models.TextField(verbose_name='Описание операции')
    ip_address = models.CharField(max_length=20, null=True, blank=True, verbose_name='IP-адрес')
    user_agent = models.TextField(null=True, blank=True, verbose_name='User Agent браузера')
    object_id = models.IntegerField(null=True, blank=True, verbose_name='ID объекта операции')
    object_repr = models.CharField(max_length=100, null=True, blank=True, verbose_name='Представление объекта')
    additional_data = models.JSONField(null=True, blank=True, verbose_name='Дополнительные данные')
    timestamp = models.DateTimeField(default=timezone.now, verbose_name='Время операции')

    class Meta:
        verbose_name = 'Лог операции'
        verbose_name_plural = 'Логи операций'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['-timestamp']),
            models.Index(fields=['user']),
            models.Index(fields=['action_type']),
            models.Index(fields=['module_type']),
        ]

    def __str__(self):
        return f"{self.action_type.name if self.action_type else '?'} - {self.module_type.name if self.module_type else '?'} - {self.timestamp.strftime('%d.%m.%Y %H:%M')}"

    def get_additional_data_display(self):
        """Форматированный вывод дополнительных данных"""
        if self.additional_data:
            try:
                return json.dumps(self.additional_data, ensure_ascii=False, indent=2)
            except:
                return str(self.additional_data)
        return "-"


class BackupManager(models.Model):
    """Модель для управления бэкапами"""
    name = models.CharField(max_length=50, verbose_name='Название бэкапа')
    backup_file = models.CharField(max_length=50, verbose_name='Имя файла бэкапа')
    backup_type = models.CharField(max_length=15, choices=[
        ('full', 'Full Backup'),
        ('daily', 'Daily Backup')
    ], verbose_name='Тип бэкапа')
    backup_date = models.DateField(null=True, blank=True, verbose_name='Дата выполнения бэкапа')
    restored_at = models.DateTimeField(null=True, blank=True, verbose_name='Дата и время восстановления')
    restoration_status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Ожидает'),
            ('in_progress', 'В процессе'),
            ('completed', 'Выполнено'),
            ('failed', 'Ошибка')
        ],
        default='pending',
        verbose_name='Статус восстановления'
    )
    restoration_log = models.TextField(blank=True, verbose_name='Лог процесса восстановления')
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Пользователь',
        related_name='backups'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата и время создания записи')

    class Meta:
        verbose_name = "Backup"
        verbose_name_plural = "Backups"
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['backup_type']),
            models.Index(fields=['restoration_status']),
        ]

    def __str__(self):
        return self.name

    def get_file_path(self):
        """Получить полный путь к файлу бэкапа"""
        return os.path.join(settings.BASE_DIR, 'backups', self.backup_file)

    def file_exists(self):
        """Проверить существует ли файл бэкапа"""
        return os.path.exists(self.get_file_path())

    def file_size(self):
        """Получить размер файла"""
        if self.file_exists():
            size = os.path.getsize(self.get_file_path())
            return f"{size / 1024 / 1024:.2f} MB"
        return "File not found"

    def can_be_restored(self):
        """Проверить, можно ли восстановить из этого backup"""
        return self.file_exists() and self.restoration_status != 'in_progress'

    def restore_database(self, user=None):
        """Восстановить БД из этого backup"""
        try:
            if not self.file_exists():
                self.restoration_status = 'failed'
                self.restoration_log = "Файл бэкапа не найден"
                self.save()
                return False, "Файл бэкапа не найден"

            if self.restoration_status == 'in_progress':
                return False, "Восстановление уже выполняется"

            # Устанавливаем статус "в процессе"
            self.restoration_status = 'in_progress'
            self.restoration_log = f"Начало восстановления в {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}"
            self.save()

            backup_path = self.get_file_path()

            # Используем новый класс для восстановления
            from .backup_utils import DatabaseRestorer

            # Проверяем подключение к БД
            connection_ok, stdout, stderr = DatabaseRestorer.test_psql_connection()
            if not connection_ok:
                self.restoration_status = 'failed'
                self.restoration_log = f"Нет подключения к БД: {stderr}"
                self.save()
                return False, f"Нет подключения к БД: {stderr}"

            # Выполняем восстановление
            success, stdout, stderr = DatabaseRestorer.restore_from_backup(backup_path)

            if success:
                self.restoration_status = 'completed'
                self.restored_at = timezone.now()
                self.restoration_log = (
                    f"✅ Восстановление успешно завершено\n"
                    f"Время: {self.restored_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
                    f"Файл: {self.backup_file}\n"
                    f"Вывод: {stdout[:1000]}"
                )
                self.save()

                # Логируем успешное восстановление
                from .logging_utils import OperationLogger
                OperationLogger.log_system_operation(
                    action_type='BACKUP',
                    module_type='BACKUPS',
                    description=f'Восстановление БД из backup: {self.name}',
                    object_id=self.id,
                    object_repr=str(self)
                )

                return True, "Восстановление успешно завершено"
            else:
                self.restoration_status = 'failed'
                error_msg = stderr if stderr else "Неизвестная ошибка"
                self.restoration_log = (
                    f"❌ Ошибка восстановления\n"
                    f"Файл: {self.backup_file}\n"
                    f"Ошибка:\n{error_msg[:2000]}"
                )
                self.save()

                # Показываем более подробную ошибку пользователю
                if "permission denied" in error_msg.lower():
                    return False, "Ошибка прав доступа к файлу"
                elif "does not exist" in error_msg.lower():
                    return False, "Файл не найден"
                else:
                    return False, f"Ошибка восстановления: {error_msg[:200]}"

        except Exception as e:
            self.restoration_status = 'failed'
            self.restoration_log = f"Исключение при восстановлении: {str(e)}"
            self.save()
            return False, f"Ошибка: {str(e)}"

    def get_restoration_status_display(self):
        """Получить отображаемый статус восстановления"""
        status_display = dict(self._meta.get_field('restoration_status').choices).get(
            self.restoration_status, self.restoration_status
        )

        if self.restoration_status == 'completed' and self.restored_at:
            return f"{status_display} ({self.restored_at.strftime('%d.%m.%Y %H:%M')})"
        return status_display

    def get_restoration_color(self):
        """Получить цвет статуса для отображения"""
        colors = {
            'pending': '#888',
            'in_progress': '#ff9800',
            'completed': '#4caf50',
            'failed': '#f44336'
        }
        return colors.get(self.restoration_status, '#888')

    def get_download_url(self):
        """Получить URL для скачивания файла backup"""
        return f'/backups/{self.backup_file}'

    def get_absolute_path(self):
        """Получить абсолютный путь к файлу"""
        return self.get_file_path()


class PendingRegistration(models.Model):
    """Временное хранение данных регистрации до подтверждения email"""
    email = models.EmailField(max_length=50, unique=True, verbose_name='Электронная почта')
    name = models.CharField(max_length=20, verbose_name='Имя')
    surname = models.CharField(max_length=20, verbose_name='Фамилия')
    number = models.CharField(max_length=20, verbose_name='Номер телефона')
    password = models.CharField(max_length=128, verbose_name='Хэшированный пароль')
    verification_code = models.CharField(max_length=6, verbose_name='Код подтверждения')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата и время создания')

    def is_expired(self):
        """Проверка истечения срока действия (30 минут)"""
        from django.utils import timezone
        expiration_time = self.created_at + timezone.timedelta(minutes=30)
        return timezone.now() > expiration_time

    def create_user(self):
        """Создание пользователя после подтверждения"""
        user = User.objects.create(
            email=self.email,
            name=self.name,
            surname=self.surname,
            number=self.number,
            password=self.password,  # Пароль уже хэширован
            is_email_verified=True
        )
        return user

    class Meta:
        verbose_name = "Ожидающая регистрация"
        verbose_name_plural = "Ожидающие регистрации"
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['-created_at']),
        ]


class PasswordResetRequest(models.Model):
    """Модель для хранения запросов на восстановление пароля"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='Пользователь', related_name='password_reset_requests')
    reset_code = models.CharField(max_length=6, verbose_name='Код для сброса пароля')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата и время создания')
    is_used = models.BooleanField(default=False, verbose_name='Использован ли код')
    expires_at = models.DateTimeField(verbose_name='Дата и время истечения срока')

    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timezone.timedelta(minutes=30)
        super().save(*args, **kwargs)

    def is_expired(self):
        """Проверка истечения срока действия кода"""
        from django.utils import timezone
        return timezone.now() > self.expires_at

    def mark_as_used(self):
        """Пометить код как использованный"""
        self.is_used = True
        self.save()

    class Meta:
        verbose_name = "Запрос восстановления пароля"
        verbose_name_plural = "Запросы восстановления пароля"
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['reset_code']),
        ]


class EmailChangeRequest(models.Model):
    """Модель для хранения запросов на смену email"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='Пользователь', related_name='email_change_requests')
    new_email = models.EmailField(max_length=50, verbose_name='Новый email')
    verification_code = models.CharField(max_length=6, verbose_name='Код подтверждения')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата и время создания')
    is_used = models.BooleanField(default=False, verbose_name='Использован ли запрос')
    expires_at = models.DateTimeField(verbose_name='Дата и время истечения срока')

    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timezone.timedelta(minutes=30)
        super().save(*args, **kwargs)

    def is_expired(self):
        """Проверка истечения срока действия кода (30 минут)"""
        from django.utils import timezone
        return timezone.now() > self.expires_at

    def mark_as_used(self):
        """Пометить запрос как использованный"""
        self.is_used = True
        self.save()

    class Meta:
        verbose_name = "Запрос смены email"
        verbose_name_plural = "Запросы смены email"
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['new_email']),
        ]


# Модель-заглушка для отчетов
class Report(models.Model):
    """Модель для отображения отчетов в админке"""

    class Meta:
        verbose_name = "Отчет"
        verbose_name_plural = "Отчеты"
        app_label = 'ticket'

    def __str__(self):
        return "Система отчетности"