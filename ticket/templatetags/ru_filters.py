from django import template

register = template.Library()


@register.filter
def russian_date(value):
    """
    Фильтр для преобразования даты в русский формат
    """
    if not value:
        return ""

    # Русские названия месяцев
    month_names = {
        1: 'января', 2: 'февраля', 3: 'марта', 4: 'апреля',
        5: 'мая', 6: 'июня', 7: 'июля', 8: 'августа',
        9: 'сентября', 10: 'октября', 11: 'ноября', 12: 'декабря'
    }

    try:
        # Если значение - datetime объект
        day = value.day
        month = month_names[value.month]
        year = value.year

        return f"{day} {month} {year}"
    except (AttributeError, KeyError):
        return str(value)


@register.filter
def russian_datetime(value):
    """
    Фильтр для преобразования даты и времени в русский формат
    """
    if not value:
        return ""

    try:
        date_part = russian_date(value)
        time_part = value.strftime("%H:%M")

        return f"{date_part} {time_part}"
    except AttributeError:
        return str(value)


@register.filter
def russian_date_short(value):
    """
    Фильтр для короткого формата даты (без года)
    """
    if not value:
        return ""

    try:
        # Русские названия месяцев
        month_names = {
            1: 'января', 2: 'февраля', 3: 'марта', 4: 'апреля',
            5: 'мая', 6: 'июня', 7: 'июля', 8: 'августа',
            9: 'сентября', 10: 'октября', 11: 'ноября', 12: 'декабря'
        }

        day = value.day
        month = month_names[value.month]

        return f"{day} {month}"
    except (AttributeError, KeyError):
        return str(value)


@register.filter
def ru_pluralize(value, variants):
    """
    Фильтр для правильного склонения слов после числительных
    Использование: {{ count|ru_pluralize:"сеанс,сеанса,сеансов" }}
    """
    try:
        value = int(value)
        variants = variants.split(',')

        if value % 10 == 1 and value % 100 != 11:
            return variants[0]
        elif 2 <= value % 10 <= 4 and (value % 100 < 10 or value % 100 >= 20):
            return variants[1] if len(variants) > 1 else variants[0]
        else:
            return variants[2] if len(variants) > 2 else variants[0]
    except (ValueError, IndexError):
        return variants[0] if variants else ''

# Добавляем остальные фильтры для отчетов
@register.filter
def sum_revenue(data):
    """Сумма выручки из списка данных"""
    return sum(item.get('revenue', 0) or 0 for item in data)

@register.filter
def sum_tickets(data):
    """Сумма билетов из списка данных"""
    return sum(item.get('tickets_sold', 0) for item in data)

@register.filter
def sum_movie_revenue(movies):
    """Сумма выручки по всем фильмам"""
    return sum(movie.total_revenue or 0 for movie in movies)

@register.filter
def div(value, arg):
    """Деление значения"""
    try:
        return float(value) / float(arg)
    except (ValueError, ZeroDivisionError):
        return 0

@register.filter
def calculate_avg(revenue, tickets):
    """Расчет среднего значения"""
    try:
        if tickets > 0:
            return revenue / tickets
        return 0
    except (TypeError, ValueError):
        return 0

@register.filter
def multiply(value, arg):
    """Умножает значение на аргумент"""
    try:
        return int(value) * int(arg)
    except (ValueError, TypeError):
        return 0