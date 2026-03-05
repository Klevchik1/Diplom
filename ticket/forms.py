import re
from datetime import date, timedelta
from django import forms
from django.contrib.auth import password_validation
from django.contrib.auth.forms import PasswordChangeForm
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.utils import timezone
from .export_utils import LogExporter
from .models import (
    User, Movie, Hall, Screening, OperationLog,
    Genre, AgeRating, Director, Actor, Country, HallType,
    ActionType, ModuleType, TicketStatus, TicketGroup,
    EmailChangeRequest, PendingRegistration, PasswordResetRequest
)
from django import forms
from django.utils.html import format_html
from django.utils import timezone
from decimal import Decimal
import datetime
from .widgets import TimePickerWidget


class RegistrationForm(forms.Form):
    email = forms.EmailField(
        label='Email',
        widget=forms.EmailInput(attrs={
            'placeholder': 'example@mail.ru',
            'class': 'form-control',
            'data-validate': 'email',
            'required': True,
            'autocomplete': 'email',
            'maxlength': '50'
        })
    )
    name = forms.CharField(
        label='Имя',
        max_length=20,
        widget=forms.TextInput(attrs={
            'placeholder': 'Иван',
            'class': 'form-control',
            'data-validate': 'name',
            'required': True,
            'minlength': '2',
            'maxlength': '20',
            'autocomplete': 'given-name'
        })
    )
    surname = forms.CharField(
        label='Фамилия',
        max_length=20,
        widget=forms.TextInput(attrs={
            'placeholder': 'Иванов',
            'class': 'form-control',
            'data-validate': 'surname',
            'required': True,
            'minlength': '2',
            'maxlength': '20',
            'autocomplete': 'family-name'
        })
    )
    number = forms.CharField(
        label='Телефон',
        max_length=20,
        widget=forms.TextInput(attrs={
            'placeholder': '+7 (999) 999-99-99',
            'class': 'form-control',
            'data-validate': 'phone',
            'required': True,
            'autocomplete': 'tel'
        }),
        help_text='Формат: +7 (999) 123-45-67'
    )
    password1 = forms.CharField(
        label='Пароль',
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Придумайте пароль',
            'class': 'form-control',
            'data-validate': 'password',
            'required': True,
            'minlength': '8',
            'autocomplete': 'new-password'
        }),
        help_text='<ul><li>Пароль должен содержать не менее 8 символов</li><li>Не должен быть слишком простым</li><li>Не должен состоять только из цифр</li></ul>'
    )
    password2 = forms.CharField(
        label='Подтверждение пароля',
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Повторите пароль',
            'class': 'form-control',
            'data-validate': 'confirm',
            'required': True,
            'minlength': '8',
            'autocomplete': 'new-password'
        })
    )

    def clean_email(self):
        email = self.cleaned_data.get('email')
        # Проверяем, не занят ли email подтвержденным пользователем
        if User.objects.filter(email=email, is_email_verified=True).exists():
            raise ValidationError('Пользователь с таким email уже существует')
        return email

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get('password1')
        password2 = cleaned_data.get('password2')

        if password1 and password2 and password1 != password2:
            raise ValidationError('Пароли не совпадают')

        return cleaned_data

    def clean_name(self):
        name = self.cleaned_data.get('name')
        if not re.match(r'^[а-яА-Яa-zA-Z\- ]+$', name):
            raise ValidationError('Имя может содержать только буквы и дефисы')
        return name

    def clean_surname(self):
        surname = self.cleaned_data.get('surname')
        if not re.match(r'^[а-яА-Яa-zA-Z\- ]+$', surname):
            raise ValidationError('Фамилия может содержать только буквы и дефисы')
        return surname

    def clean_number(self):
        number = self.cleaned_data.get('number')
        cleaned_number = re.sub(r'[^\d+]', '', number)

        if cleaned_number.startswith('8'):
            cleaned_number = '+7' + cleaned_number[1:]
        elif cleaned_number.startswith('7'):
            cleaned_number = '+' + cleaned_number

        if len(cleaned_number) != 12:
            raise ValidationError('Номер телефона должен содержать 11 цифр')

        return cleaned_number


class LoginForm(forms.Form):
    email = forms.EmailField(
        label='Email',
        max_length=50,
        widget=forms.EmailInput(attrs={
            'placeholder': 'Ваш email',
            'class': 'form-control'
        })
    )
    password = forms.CharField(
        label='Пароль',
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Ваш пароль',
            'class': 'form-control'
        })
    )


class UserUpdateForm(forms.ModelForm):
    name = forms.CharField(
        max_length=20,
        validators=[
            RegexValidator(
                regex=r'^[а-яА-Яa-zA-Z\- ]+$',
                message='Имя может содержать только буквы и дефисы'
            )
        ],
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ваше имя'
        })
    )
    surname = forms.CharField(
        max_length=20,
        validators=[
            RegexValidator(
                regex=r'^[а-яА-Яa-zA-Z\- ]+$',
                message='Фамилия может содержать только буквы и дефисы'
            )
        ],
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ваша фамилия'
        })
    )
    number = forms.CharField(
        max_length=20,
        validators=[
            RegexValidator(
                regex=r'^(\+7|8)?[\s\-]?\(?[489][0-9]{2}\)?[\s\-]?[0-9]{3}[\s\-]?[0-9]{2}[\s\-]?[0-9]{2}$',
                message='Введите корректный номер телефона РФ'
            )
        ],
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '+7 (XXX) XXX-XX-XX'
        })
    )

    class Meta:
        model = User
        fields = ['name', 'surname', 'number']

    def clean_number(self):
        number = self.cleaned_data.get('number')
        cleaned_number = re.sub(r'[^\d+]', '', number)

        if cleaned_number.startswith('8'):
            cleaned_number = '+7' + cleaned_number[1:]
        elif cleaned_number.startswith('7'):
            cleaned_number = '+' + cleaned_number

        if len(cleaned_number) != 12:
            raise ValidationError('Номер телефона должен содержать 11 цифр')

        if User.objects.filter(number=cleaned_number).exclude(pk=self.instance.pk).exists():
            raise ValidationError('Пользователь с таким номером телефона уже существует')

        return cleaned_number


class DirectorForm(forms.ModelForm):
    class Meta:
        model = Director
        fields = ['name', 'surname', 'birth_date', 'country', 'biography']
        widgets = {
            'birth_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'biography': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'surname': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        name = cleaned_data.get('name')
        surname = cleaned_data.get('surname')

        if not re.match(r'^[а-яА-Яa-zA-Z\- ]+$', name or ''):
            raise ValidationError('Имя может содержать только буквы и дефисы')
        if not re.match(r'^[а-яА-Яa-zA-Z\- ]+$', surname or ''):
            raise ValidationError('Фамилия может содержать только буквы и дефисы')

        return cleaned_data


class ActorForm(forms.ModelForm):
    class Meta:
        model = Actor
        fields = ['name', 'surname', 'birth_date', 'country', 'biography']
        widgets = {
            'birth_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'biography': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'surname': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        name = cleaned_data.get('name')
        surname = cleaned_data.get('surname')

        if not re.match(r'^[а-яА-Яa-zA-Z\- ]+$', name or ''):
            raise ValidationError('Имя может содержать только буквы и дефисы')
        if not re.match(r'^[а-яА-Яa-zA-Z\- ]+$', surname or ''):
            raise ValidationError('Фамилия может содержать только буквы и дефисы')

        return cleaned_data


class MovieForm(forms.ModelForm):
    duration = forms.IntegerField(
        min_value=1,
        max_value=300,
        label='Длительность (минуты)',
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 300})
    )
    release_year = forms.IntegerField(
        min_value=1900,
        max_value=date.today().year + 1,
        label='Год выпуска',
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )

    # Используем обычные ModelMultipleChoiceField без кастомных промежуточных моделей
    directors = forms.ModelMultipleChoiceField(
        queryset=Director.objects.all().order_by('surname', 'name'),
        required=False,
        label='Режиссёры',
        widget=forms.SelectMultiple(attrs={'class': 'form-control', 'size': 5})
    )

    actors = forms.ModelMultipleChoiceField(
        queryset=Actor.objects.all().order_by('surname', 'name'),
        required=False,
        label='Актёры',
        widget=forms.SelectMultiple(attrs={'class': 'form-control', 'size': 5})
    )

    class Meta:
        model = Movie
        fields = ['title', 'release_year', 'short_description', 'description',
                  'duration', 'genre', 'age_rating', 'poster', 'directors', 'actors']
        widgets = {
            'short_description': forms.Textarea(attrs={
                'rows': 3,
                'class': 'form-control',
                'placeholder': 'Короткое описание для главной страницы (до 300 символов)'
            }),
            'description': forms.Textarea(attrs={
                'rows': 5,
                'class': 'form-control',
                'placeholder': 'Полное описание для страницы фильма'
            }),
            'poster': forms.FileInput(attrs={'accept': 'image/*', 'class': 'form-control'}),
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'genre': forms.Select(attrs={'class': 'form-control'}),
            'age_rating': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.instance and self.instance.pk:
            # Для существующего фильма загружаем текущих режиссёров и актёров
            self.fields['directors'].initial = self.instance.directors.all()
            self.fields['actors'].initial = self.instance.actors.all()

    def save(self, commit=True):
        movie = super().save(commit=False)
        if commit:
            movie.save()
            # Сохраняем связи через кастомные промежуточные модели
            if self.cleaned_data.get('directors') is not None:
                # Очищаем старые связи
                MovieDirector.objects.filter(movie=movie).delete()
                # Создаем новые
                for director in self.cleaned_data['directors']:
                    MovieDirector.objects.create(movie=movie, director=director)

            if self.cleaned_data.get('actors') is not None:
                # Очищаем старые связи
                MovieActor.objects.filter(movie=movie).delete()
                # Создаем новые
                for actor in self.cleaned_data['actors']:
                    MovieActor.objects.create(movie=movie, actor=actor)
        return movie


class HallForm(forms.ModelForm):
    class Meta:
        model = Hall
        fields = ['name', 'hall_type', 'rows', 'seats_per_row', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'hall_type': forms.Select(attrs={'class': 'form-control'}),
            'rows': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'seats_per_row': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'description': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        }


class ScreeningForm(forms.ModelForm):
    start_time = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={
            'type': 'datetime-local',
            'class': 'form-control'
        }),
        label='Время начала'
    )

    class Meta:
        model = Screening
        fields = ['movie', 'hall', 'start_time']
        widgets = {
            'movie': forms.Select(attrs={'class': 'form-control'}),
            'hall': forms.Select(attrs={'class': 'form-control'}),
        }
        labels = {
            'movie': 'Фильм',
            'hall': 'Зал',
        }

    def clean_start_time(self):
        start_time = self.cleaned_data.get('start_time')
        if start_time:
            local_time = timezone.localtime(start_time)
            hour = local_time.hour

            if hour < 8 or hour >= 23:
                raise ValidationError("Сеансы могут начинаться только с 8:00 до 23:00")

            if start_time < timezone.now():
                raise ValidationError("Нельзя создавать сеансы в прошлом")

        return start_time

    def clean(self):
        cleaned_data = super().clean()
        start_time = cleaned_data.get('start_time')
        movie = cleaned_data.get('movie')
        hall = cleaned_data.get('hall')

        if start_time and movie and hall:
            duration_timedelta = timedelta(minutes=movie.duration)
            end_time = start_time + duration_timedelta + timedelta(minutes=10)

            local_end_time = timezone.localtime(end_time)
            if local_end_time.hour >= 24 or (local_end_time.hour == 0 and local_end_time.minute > 0):
                raise ValidationError(
                    f"Сеанс заканчивается в {local_end_time.strftime('%H:%M')}. "
                    f"Кинотеатр работает до 24:00. Выберите более раннее время начала."
                )

            overlapping_screenings = Screening.objects.filter(
                hall=hall,
                start_time__lt=end_time,
                end_time__gt=start_time
            ).exclude(pk=self.instance.pk if self.instance else None)

            if overlapping_screenings.exists():
                overlapping = overlapping_screenings.first()
                raise ValidationError(
                    f"Сеанс пересекается с другим сеансом: "
                    f"{overlapping.movie.title} в {timezone.localtime(overlapping.start_time).strftime('%H:%M')}"
                )

        return cleaned_data


class ScreeningAdminForm(forms.ModelForm):
    """Кастомная форма для админки Screening с автоматическим расчетом цены"""

    start_date = forms.DateField(
        widget=forms.DateInput(attrs={
            'type': 'date',
            'min': datetime.date.today().strftime('%Y-%m-%d'),
            'class': 'date-input form-control'
        }),
        label='Дата сеанса',
        required=True
    )

    start_time = forms.CharField(
        widget=TimePickerWidget(),
        label='Время сеанса',
        required=True,
        help_text='Выберите часы и минуты (доступно с 8:00 до 23:50)'
    )

    price_calculation = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'rows': 10,
            'cols': 80,
            'readonly': 'readonly',
            'class': 'price-calculation-field form-control',
            'style': 'font-family: monospace; font-size: 12px; white-space: pre;'
        }),
        label='Расчет стоимости',
        help_text='Цена рассчитывается автоматически при выборе зала, даты и времени'
    )

    class Meta:
        model = Screening
        fields = ['movie', 'hall', 'ticket_price']
        widgets = {
            'movie': forms.Select(attrs={'class': 'form-control'}),
            'hall': forms.Select(attrs={'class': 'form-control'}),
            'ticket_price': forms.NumberInput(attrs={'class': 'form-control', 'readonly': 'readonly'}),
        }
        labels = {
            'movie': 'Фильм',
            'hall': 'Зал',
            'ticket_price': 'Цена (рассчитывается автоматически)',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.instance.pk and self.instance.start_time:
            local_time = timezone.localtime(self.instance.start_time)
            self.fields['start_date'].initial = local_time.date()
            self.fields['start_time'].initial = local_time.strftime('%H:%M')

        self.fields['ticket_price'].widget.attrs['readonly'] = True
        self.fields['price_calculation'].initial = "Выберите зал, дату и время сеанса для расчета цены"

        if self.instance.pk and self.instance.hall and self.instance.start_time:
            calculation_text = self.instance.get_price_calculation_explanation()
            self.fields['price_calculation'].initial = calculation_text

    def clean_start_time(self):
        """Валидация времени"""
        time_str = self.cleaned_data.get('start_time')
        if time_str:
            try:
                hour, minute = map(int, time_str.split(':'))

                if hour < 8 or hour > 23:
                    raise ValidationError("Время должно быть с 8:00 до 23:50")
                if hour == 23 and minute > 50:
                    raise ValidationError("Последний сеанс может начинаться в 23:50")

            except (ValueError, AttributeError):
                raise ValidationError("Неверный формат времени. Используйте ЧЧ:ММ")

        return time_str

    def clean(self):
        """Общая валидация формы"""
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        start_time = cleaned_data.get('start_time')
        movie = cleaned_data.get('movie')
        hall = cleaned_data.get('hall')

        if start_date and start_time and movie and hall:
            try:
                hour, minute = map(int, start_time.split(':'))
                start_datetime = datetime.datetime.combine(
                    start_date,
                    datetime.time(hour, minute)
                )
                start_datetime = timezone.make_aware(start_datetime)

                if start_datetime < timezone.now():
                    raise ValidationError("Нельзя создавать сеансы в прошлом")

                duration_timedelta = datetime.timedelta(minutes=movie.duration)
                end_datetime = start_datetime + duration_timedelta + datetime.timedelta(minutes=10)

                local_end = timezone.localtime(end_datetime)
                if local_end.hour == 0 and local_end.minute > 0:
                    raise ValidationError(
                        f"Сеанс заканчивается в {local_end.strftime('%H:%M')} следующего дня. "
                        f"Кинотеатр работает до 24:00. Выберите более раннее время начала."
                    )
                elif local_end.hour >= 24:
                    raise ValidationError(
                        f"Сеанс заканчивается после 24:00. "
                        f"Кинотеатр работает до 24:00. Выберите более раннее время начала."
                    )

                overlapping_screenings = Screening.objects.filter(
                    hall=hall,
                    start_time__lt=end_datetime,
                    end_time__gt=start_datetime
                ).exclude(pk=self.instance.pk if self.instance else None)

                if overlapping_screenings.exists():
                    overlapping = overlapping_screenings.first()
                    overlapping_start = timezone.localtime(overlapping.start_time).strftime('%H:%M')
                    overlapping_end = timezone.localtime(overlapping.end_time).strftime('%H:%M')
                    raise ValidationError(
                        f"Сеанс пересекается с другим сеансом:\n"
                        f"• Фильм: {overlapping.movie.title}\n"
                        f"• Время: {overlapping_start} - {overlapping_end}\n"
                        f"Выберите другое время."
                    )

                cleaned_data['start_datetime'] = start_datetime

            except Exception as e:
                if isinstance(e, ValidationError):
                    raise e
                raise ValidationError(f"Ошибка при обработке времени: {str(e)}")

        return cleaned_data

    def save(self, commit=True):
        """Сохраняем объект с вычисленным временем"""
        screening = super().save(commit=False)

        if 'start_datetime' in self.cleaned_data:
            screening.start_time = self.cleaned_data['start_datetime']

            if screening.movie and screening.start_time:
                duration_timedelta = datetime.timedelta(minutes=screening.movie.duration)
                screening.end_time = screening.start_time + duration_timedelta + datetime.timedelta(minutes=10)

        if commit:
            screening.save()

        return screening


class DailyBackupForm(forms.Form):
    backup_date = forms.DateField(
        label='Select date for backup',
        widget=forms.DateInput(attrs={
            'type': 'date',
            'max': str(date.today()),
            'class': 'vDateField form-control'
        })
    )


class PasswordResetRequestForm(forms.Form):
    email = forms.EmailField(
        label='Email',
        max_length=50,
        widget=forms.EmailInput(attrs={
            'placeholder': 'Ваш email',
            'class': 'form-control'
        })
    )


class PasswordResetCodeForm(forms.Form):
    reset_code = forms.CharField(
        label='Код подтверждения',
        max_length=6,
        min_length=6,
        widget=forms.TextInput(attrs={
            'placeholder': '000000',
            'class': 'form-control',
            'style': 'text-align: center; letter-spacing: 5px;'
        })
    )


class PasswordResetForm(forms.Form):
    new_password1 = forms.CharField(
        label='Новый пароль',
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Введите новый пароль',
            'class': 'form-control'
        }),
        help_text=password_validation.password_validators_help_text_html()
    )
    new_password2 = forms.CharField(
        label='Подтверждение нового пароля',
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Повторите новый пароль',
            'class': 'form-control'
        })
    )

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get('new_password1')
        password2 = cleaned_data.get('new_password2')

        if password1 and password2 and password1 != password2:
            raise ValidationError('Пароли не совпадают')

        if password1:
            try:
                password_validation.validate_password(password1)
            except ValidationError as error:
                raise ValidationError(error)

        return cleaned_data


class ReportFilterForm(forms.Form):
    REPORT_TYPE_CHOICES = [
        ('revenue', '📊 Финансовая статистика'),
        ('movies', '🎬 Популярность фильмов'),
        ('halls', '🏛️ Загруженность залов'),
        ('sales', '💰 Статистика продаж'),
    ]

    PERIOD_CHOICES = [
        ('daily', 'По дням'),
        ('weekly', 'По неделям'),
        ('monthly', 'По месяцам'),
    ]

    report_type = forms.ChoiceField(
        choices=REPORT_TYPE_CHOICES,
        label='Тип отчета',
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    period = forms.ChoiceField(
        choices=PERIOD_CHOICES,
        required=False,
        label='Период',
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    start_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control'
        }),
        label='Начальная дата'
    )

    end_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control'
        }),
        label='Конечная дата'
    )


class LogExportForm(forms.Form):
    """Форма для экспорта логов"""

    format_type = forms.ChoiceField(
        choices=LogExporter.get_export_formats(),
        label='Формат экспорта',
        initial='csv',
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    start_date = forms.DateField(
        label='Начальная дата',
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )

    end_date = forms.DateField(
        label='Конечная дата',
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )

    action_type = forms.ChoiceField(
        choices=[('', 'Все действия')],  # Временно только пустой выбор
        label='Тип действия',
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    module_type = forms.ChoiceField(
        choices=[('', 'Все модули')],  # Временно только пустой выбор
        label='Модуль',
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    user = forms.ModelChoiceField(
        queryset=User.objects.all(),
        label='Пользователь',
        required=False,
        empty_label='Все пользователи',
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Динамически заполняем choices после создания формы
        try:
            self.fields['action_type'].choices = [('', 'Все действия')] + [
                (obj.code, obj.name) for obj in ActionType.objects.all()
            ]
            self.fields['module_type'].choices = [('', 'Все модули')] + [
                (obj.code, obj.name) for obj in ModuleType.objects.all()
            ]
        except Exception:
            # Если таблицы еще не существуют, оставляем пустые choices
            pass

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')

        if start_date and end_date and start_date > end_date:
            raise forms.ValidationError('Начальная дата не может быть больше конечной')

        return cleaned_data


class EmailChangeForm(forms.Form):
    new_email = forms.EmailField(
        label='Новый email',
        max_length=50,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Введите новый email'
        })
    )
    verification_code = forms.CharField(
        label='Код подтверждения',
        max_length=6,
        min_length=6,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '000000',
            'style': 'text-align: center; letter-spacing: 5px;'
        })
    )

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

    def clean_new_email(self):
        new_email = self.cleaned_data.get('new_email')

        if not self.user:
            raise ValidationError('Пользователь не определен')

        if new_email == self.user.email:
            raise ValidationError('Новый email совпадает с текущим')

        if User.objects.filter(email=new_email).exclude(pk=self.user.pk).exists():
            raise ValidationError('Пользователь с таким email уже существует')

        return new_email

    def clean(self):
        cleaned_data = super().clean()
        verification_code = cleaned_data.get('verification_code')
        new_email = cleaned_data.get('new_email')

        if verification_code:
            try:
                change_request = EmailChangeRequest.objects.filter(
                    user=self.user,
                    new_email=new_email,
                    is_used=False
                ).order_by('-created_at').first()

                if not change_request:
                    raise ValidationError('Запрос на смену email не найден')

                if change_request.is_expired():
                    change_request.delete()
                    raise ValidationError('Время действия кода истекло. Запросите новый код.')

                if change_request.verification_code != verification_code:
                    raise ValidationError('Неверный код подтверждения')

            except EmailChangeRequest.DoesNotExist:
                raise ValidationError('Запрос на смену email не найден')

        return cleaned_data


class HallTypeForm(forms.ModelForm):
    class Meta:
        model = HallType
        fields = ['name', 'description', 'price_coefficient', 'base_price']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'price_coefficient': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0.5', 'max': '3.0'}),
            'base_price': forms.NumberInput(attrs={'class': 'form-control', 'min': '100', 'step': '50'}),
        }


class CountryForm(forms.ModelForm):
    class Meta:
        model = Country
        fields = ['name', 'code']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'code': forms.TextInput(attrs={'class': 'form-control', 'maxlength': '2', 'placeholder': 'RU'}),
        }

    def clean_code(self):
        code = self.cleaned_data.get('code')
        if code:
            code = code.upper()
            if len(code) != 2:
                raise ValidationError('Код страны должен содержать ровно 2 символа')
        return code