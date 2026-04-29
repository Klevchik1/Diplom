from django import template
from django.utils import timezone
import locale
import logging

logger = logging.getLogger(__name__)

register = template.Library()


@register.filter
def russian_date(value):
    """
    Фильтр для преобразования даты в русский формат
    Пример: 07 Nov → 07 ноября
    """
    if not value:
        return ""

    try:
        # Устанавливаем русскую локаль
        try:
            locale.setlocale(locale.LC_TIME, 'ru_RU.UTF-8')
        except:
            try:
                locale.setlocale(locale.LC_TIME, 'Russian_Russia.1251')
            except:
                logger.warning("Не удалось установить русскую локаль, используются стандартные названия")

        # Форматируем дату
        if isinstance(value, str):
            from datetime import datetime
            value = datetime.strptime(value, '%Y-%m-%d %H:%M:%S')

        # Получаем полное русское название месяца
        month_names = {
            1: 'января', 2: 'февраля', 3: 'марта', 4: 'апреля',
            5: 'мая', 6: 'июня', 7: 'июля', 8: 'августа',
            9: 'сентября', 10: 'октября', 11: 'ноября', 12: 'декабря'
        }

        day = value.day
        month = month_names[value.month]
        year = value.year

        return f"{day} {month} {year}"

    except Exception as e:
        logger.error(f"Ошибка форматирования даты: {e}")
        return value.strftime("%d %B %Y") if hasattr(value, 'strftime') else str(value)


@register.filter
def russian_datetime(value):
    """
    Фильтр для преобразования даты и времени в русский формат
    Пример: 07 Nov 21:17 → 07 ноября 21:17
    """
    if not value:
        return ""

    try:
        # Получаем русскую дату
        russian_date_part = russian_date(value)

        # Добавляем время
        time_part = value.strftime("%H:%M")

        return f"{russian_date_part} {time_part}"

    except Exception as e:
        logger.error(f"Ошибка форматирования даты и времени: {e}")
        return value.strftime("%d %B %Y %H:%M") if hasattr(value, 'strftime') else str(value)


@register.filter
def russian_date_short(value):
    """
    Фильтр для преобразования даты в короткий русский формат (без года)
    Пример: 07 Nov → 07 ноября
    """
    if not value:
        return ""

    try:
        # Получаем русскую дату
        russian_date_part = russian_date(value)

        # Убираем год
        parts = russian_date_part.split()
        if len(parts) >= 2:
            return f"{parts[0]} {parts[1]}"

        return russian_date_part

    except Exception as e:
        logger.error(f"Ошибка форматирования короткой даты: {e}")
        return value.strftime("%d %B") if hasattr(value, 'strftime') else str(value)


@register.filter
def ru_date_format(value):
    """Форматирование даты на русском"""
    if not value:
        return ""

    # Локализуем время
    local_time = timezone.localtime(value)

    months = {
        1: 'января', 2: 'февраля', 3: 'марта', 4: 'апреля',
        5: 'мая', 6: 'июня', 7: 'июля', 8: 'августа',
        9: 'сентября', 10: 'октября', 11: 'ноября', 12: 'декабря'
    }

    return f"{local_time.day} {months[local_time.month]} {local_time.year}"

@register.filter
def ru_month(date):
    """Возвращает месяц на русском языке"""
    months = {
        1: 'января', 2: 'февраля', 3: 'марта', 4: 'апреля',
        5: 'мая', 6: 'июня', 7: 'июля', 8: 'августа',
        9: 'сентября', 10: 'октября', 11: 'ноября', 12: 'декабря'
    }
    return months[date.month]

@register.filter
def ru_short_date(date):
    """Короткий формат даты: '15 ноября'"""
    months = {
        1: 'янв', 2: 'фев', 3: 'мар', 4: 'апр',
        5: 'мая', 6: 'июн', 7: 'июл', 8: 'авг',
        9: 'сен', 10: 'окт', 11: 'ноя', 12: 'дек'
    }
    return f"{date.day} {months[date.month]}"