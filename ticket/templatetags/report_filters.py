from django import template
from decimal import Decimal

register = template.Library()


@register.filter
def sum_revenue(data):
    """Сумма выручки из данных отчета"""
    if not data:
        return 0
    return sum(float(item.get('revenue', 0) or 0) for item in data)

@register.filter
def sum_tickets(data):
    """Сумма билетов из данных отчета"""
    if not data:
        return 0
    return sum(item.get('tickets_sold', 0) for item in data)

@register.filter
def get_period_display(period):
    """Отображение периода на русском"""
    period_map = {
        'daily': 'по дням',
        'weekly': 'по неделям',
        'monthly': 'по месяцам'
    }
    return period_map.get(period, '')


@register.filter
def calculate_width(value, max_value):
    """Расчет ширины для прогресс-бара"""
    if not max_value or max_value <= 0:
        return 0
    width = (float(value) / float(max_value)) * 100
    return min(100, max(0, round(width, 1)))


@register.filter
def aggregate_movies_stats(data):
    """Агрегированные статистики для фильмов"""
    if not data:
        return {'total_tickets': 0, 'total_revenue': 0}

    total_tickets = sum(m.get('tickets_sold', 0) for m in data)
    total_revenue = sum(float(m.get('total_revenue', 0) or 0) for m in data)

    return {
        'total_tickets': total_tickets,
        'total_revenue': round(total_revenue, 2)
    }


@register.filter
def aggregate_halls_stats(data):
    """Агрегированные статистики для залов"""
    if not data:
        return {'avg_occupancy': 0, 'total_revenue': 0, 'total_tickets': 0}

    occupancy_values = [h.get('occupancy_percent', 0) for h in data]
    avg_occupancy = sum(occupancy_values) / len(occupancy_values) if occupancy_values else 0

    total_revenue = sum(float(h.get('total_revenue', 0) or 0) for h in data)
    total_tickets = sum(h.get('sold_tickets', 0) for h in data)

    return {
        'avg_occupancy': round(avg_occupancy, 1),
        'total_revenue': round(total_revenue, 2),
        'total_tickets': total_tickets
    }


@register.filter
def avg_ticket_price(item):
    """Расчет среднего чека для одного элемента"""
    revenue = float(item.get('revenue', 0) or 0)
    tickets = item.get('tickets_sold', 0)

    if tickets > 0:
        return revenue / tickets
    return 0


@register.filter
def total_avg_ticket_price(data):
    """Расчет среднего чека для всех данных"""
    total_revenue = sum(float(item.get('revenue', 0) or 0) for item in data)
    total_tickets = sum(item.get('tickets_sold', 0) for item in data)

    if total_tickets > 0:
        return total_revenue / total_tickets
    return 0


@register.filter
def calculate_avg_occupancy(data):
    """Расчет средней загруженности залов"""
    if not data:
        return 0

    occupancy_values = [h.get('occupancy_percent', 0) for h in data]
    if not occupancy_values:
        return 0

    avg = sum(occupancy_values) / len(occupancy_values)
    return round(avg, 1)


@register.filter
def calculate_total_revenue(data):
    """Общая выручка залов"""
    if not data:
        return 0
    return round(sum(float(h.get('total_revenue', 0) or 0) for h in data), 2)


@register.filter
def calculate_total_tickets(data):
    """Всего билетов залов"""
    if not data:
        return 0
    return sum(h.get('sold_tickets', 0) for h in data)


@register.filter
def calculate_avg_ticket(item):
    """Расчет среднего чека для одного элемента"""
    revenue = float(item.get('revenue', 0) or 0)
    tickets_sold = item.get('tickets_sold', 0)

    if tickets_sold > 0:
        return round(revenue / tickets_sold, 2)
    return 0


@register.filter
def calculate_avg_ticket_total(data):
    """Расчет среднего чека для всех данных"""
    if not data:
        return 0

    total_revenue = sum(float(item.get('revenue', 0) or 0) for item in data)
    total_tickets = sum(item.get('tickets_sold', 0) for item in data)

    if total_tickets > 0:
        return round(total_revenue / total_tickets, 2)
    return 0


@register.filter
def calculate_avg_price(item):
    """Расчет среднего чека для одного элемента"""
    revenue = float(item.get('revenue', 0) or 0)
    tickets = item.get('tickets_sold', 0)

    if tickets > 0 and revenue > 0:
        return round(revenue / tickets, 2)
    return 0


@register.filter
def calculate_total_avg(data):
    """Расчет среднего чека для всех данных"""
    total_revenue = sum(float(item.get('revenue', 0) or 0) for item in data)
    total_tickets = sum(item.get('tickets_sold', 0) for item in data)

    if total_tickets > 0 and total_revenue > 0:
        return round(total_revenue / total_tickets, 2)
    return 0