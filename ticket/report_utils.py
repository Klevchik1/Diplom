import logging
from django.db.models import Sum, Count, Q, F
from decimal import Decimal
from .models import Ticket, Movie, Hall, Screening

logger = logging.getLogger(__name__)


class ReportGenerator:
    @staticmethod
    def get_revenue_stats(period='daily', start_date=None, end_date=None):
        """Статистика выручки по периодам - УЛУЧШЕННАЯ ВЕРСИЯ"""
        tickets = Ticket.objects.select_related('screening').filter(
            screening__isnull=False,
            status__code='active'  # Только активные билеты
        )

        # Фильтр по дате если указан
        if start_date:
            tickets = tickets.filter(purchase_date__date__gte=start_date)
        if end_date:
            tickets = tickets.filter(purchase_date__date__lte=end_date)

        if period == 'daily':
            data = tickets.extra({
                'date': "date(purchase_date)"
            }).values('date').annotate(
                revenue=Sum('screening__price'),
                tickets_sold=Count('id')
            ).order_by('date')

        elif period == 'weekly':
            data = tickets.extra({
                'week': "EXTRACT(week FROM purchase_date)",
                'year': "EXTRACT(year FROM purchase_date)"
            }).values('year', 'week').annotate(
                revenue=Sum('screening__price'),
                tickets_sold=Count('id')
            ).order_by('year', 'week')

        elif period == 'monthly':
            data = tickets.extra({
                'month': "EXTRACT(month FROM purchase_date)",
                'year': "EXTRACT(year FROM purchase_date)"
            }).values('year', 'month').annotate(
                revenue=Sum('screening__price'),
                tickets_sold=Count('id')
            ).order_by('year', 'month')

        # Преобразуем в список
        result = []
        for item in data:
            revenue = float(item['revenue'] or 0)
            result.append({
                'date': item.get('date'),
                'week': item.get('week'),
                'month': item.get('month'),
                'year': item.get('year'),
                'revenue': revenue,
                'tickets_sold': item['tickets_sold'] or 0
            })

        return result

    @staticmethod
    def get_popular_movies(limit=10, start_date=None, end_date=None):
        """Самые популярные фильмы - ПРАВИЛЬНЫЕ ПРОГРЕСС-БАРЫ"""
        # Базовый запрос для билетов
        tickets = Ticket.objects.filter(
            status__code='active'
        ).select_related('screening', 'screening__movie')

        # Фильтр по дате
        if start_date:
            tickets = tickets.filter(purchase_date__date__gte=start_date)
        if end_date:
            tickets = tickets.filter(purchase_date__date__lte=end_date)

        # Группируем по фильмам
        from collections import defaultdict
        movie_stats = defaultdict(lambda: {'tickets_sold': 0, 'total_revenue': 0})

        for ticket in tickets:
            if ticket.screening and ticket.screening.movie:
                movie_id = ticket.screening.movie.id
                movie_stats[movie_id]['movie'] = ticket.screening.movie
                movie_stats[movie_id]['tickets_sold'] += 1
                movie_stats[movie_id]['total_revenue'] += float(ticket.screening.price or 0)

        # Общее количество всех билетов
        total_all_tickets = sum(stats['tickets_sold'] for stats in movie_stats.values())

        # Преобразуем в список
        movies_list = []
        for movie_id, stats in movie_stats.items():
            movie = stats['movie']
            tickets_sold = stats['tickets_sold']

            # ПРАВИЛЬНЫЙ РАСЧЕТ ПРОЦЕНТОВ: от общего количества билетов
            popularity_percentage = 0
            if total_all_tickets > 0:
                popularity_percentage = round((tickets_sold / total_all_tickets) * 100, 1)

            movies_list.append({
                'id': movie.id,
                'title': movie.title,
                'genre': movie.genre.name if movie.genre else '',
                'age_rating': str(movie.age_rating) if movie.age_rating else '',
                'duration': movie.duration if hasattr(movie, 'duration') else None,
                'tickets_sold': tickets_sold,
                'total_revenue': round(stats['total_revenue'], 2),
                'popularity_percentage': popularity_percentage,  # Это уже процент от 0 до 100
                'max_popularity': 100  # Для прогресс-бара
            })

        # Сортируем по количеству проданных билетов
        movies_list.sort(key=lambda x: x['tickets_sold'], reverse=True)

        return movies_list[:limit] if limit else movies_list

    @staticmethod
    def get_hall_occupancy(start_date=None, end_date=None):
        """Загруженность залов - ИСПРАВЛЕННАЯ ФОРМУЛА"""
        halls = Hall.objects.all()
        hall_list = []

        for hall in halls:
            # Получаем сеансы в выбранном периоде
            screenings = hall.screening_set.all()
            if start_date:
                screenings = screenings.filter(start_time__date__gte=start_date)
            if end_date:
                screenings = screenings.filter(start_time__date__lte=end_date)

            total_screenings = screenings.count()

            if total_screenings == 0:
                # Если нет сеансов в выбранном периоде
                hall_data = {
                    'id': hall.id,
                    'name': hall.name,
                    'description': hall.description or '',
                    'rows': hall.rows,
                    'seats_per_row': hall.seats_per_row,
                    'total_seats': hall.rows * hall.seats_per_row,
                    'total_screenings': 0,
                    'sold_tickets': 0,
                    'total_revenue': 0,
                    'occupancy_percent': 0,
                    'free_seats': 0
                }
                hall_list.append(hall_data)
                continue

            # Получаем билеты для этих сеансов
            screening_ids = screenings.values_list('id', flat=True)
            tickets = Ticket.objects.filter(
                screening_id__in=screening_ids,
                status__code='active'
            )

            sold_tickets = tickets.count()
            total_seats = hall.rows * hall.seats_per_row

            # ПРАВИЛЬНАЯ ФОРМУЛА: (проданные_билеты / (мест_в_зале × сеансов)) × 100
            if total_screenings > 0 and total_seats > 0:
                total_possible_tickets = total_seats * total_screenings
                # Умножаем на 100, чтобы получить проценты
                occupancy_percent = (sold_tickets / total_possible_tickets) * 100
            else:
                occupancy_percent = 0

            # Выручка
            revenue_result = tickets.aggregate(total=Sum('screening__price'))
            total_revenue = float(revenue_result['total'] or 0)

            hall_data = {
                'id': hall.id,
                'name': hall.name,
                'description': hall.description or '',
                'rows': hall.rows,
                'seats_per_row': hall.seats_per_row,
                'total_seats': total_seats,
                'total_screenings': total_screenings,
                'sold_tickets': sold_tickets,
                'total_revenue': round(total_revenue, 2),
                'occupancy_percent': round(occupancy_percent, 1),  # Уже в процентах
                'free_seats': (total_seats * total_screenings) - sold_tickets
            }
            hall_list.append(hall_data)

        # Сортируем по загруженности
        return sorted(hall_list, key=lambda x: x['occupancy_percent'], reverse=True)

    @staticmethod
    def get_sales_statistics(start_date=None, end_date=None):
        """Общая статистика продаж - УЛУЧШЕННАЯ ВЕРСИЯ"""
        tickets = Ticket.objects.filter(
            status__code='active'
        ).select_related('screening', 'screening__movie')

        # Фильтр по дате
        if start_date:
            tickets = tickets.filter(purchase_date__date__gte=start_date)
        if end_date:
            tickets = tickets.filter(purchase_date__date__lte=end_date)

        total_tickets = tickets.count()

        # Выручка
        revenue = sum(float(t.screening.price or 0) for t in tickets)

        # Средняя цена
        avg_ticket_price = round(revenue / total_tickets, 2) if total_tickets > 0 else 0

        # Самый популярный фильм
        from collections import Counter
        movie_counter = Counter()
        for ticket in tickets:
            if ticket.screening and ticket.screening.movie:
                movie_counter[ticket.screening.movie.title] += 1

        if movie_counter:
            popular_movie, popular_movie_tickets = movie_counter.most_common(1)[0]
        else:
            popular_movie = "Нет данных"
            popular_movie_tickets = 0

        # Рассчитываем процент для прогресс-бара (от 0 до 1000 рублей)
        if avg_ticket_price > 1000:
            progress_percent = 100
        elif avg_ticket_price <= 0:
            progress_percent = 0
        else:
            progress_percent = round((avg_ticket_price / 1000) * 100, 1)

        return {
            'total_tickets': total_tickets,
            'total_revenue': round(revenue, 2),
            'avg_ticket_price': avg_ticket_price,
            'progress_percent': progress_percent,
            'popular_movie': popular_movie,
            'popular_movie_tickets': popular_movie_tickets,
            'avg_ticket_price_progress': min(100, progress_percent)  # Для прогресс-бара
        }

    @staticmethod
    def get_aggregated_metrics_for_movies(report_data):
        """Расчет агрегированных метрик для фильмов"""
        if not report_data:
            return {'total_tickets': 0, 'total_revenue': 0, 'avg_ticket_price': 0}

        total_tickets = sum(m.get('tickets_sold', 0) for m in report_data)
        total_revenue = sum(m.get('total_revenue', 0) for m in report_data)

        avg_ticket_price = round(total_revenue / total_tickets, 2) if total_tickets > 0 else 0

        return {
            'total_tickets': total_tickets,
            'total_revenue': round(total_revenue, 2),
            'avg_ticket_price': avg_ticket_price
        }

    @staticmethod
    def get_aggregated_metrics_for_halls(report_data):
        """Расчет агрегированных метрик для залов"""
        if not report_data:
            return {'avg_occupancy': 0, 'total_revenue': 0, 'total_tickets': 0}

        # Средняя загруженность
        occupancy_values = [h.get('occupancy_percent', 0) for h in report_data]
        avg_occupancy = round(sum(occupancy_values) / len(occupancy_values), 1) if occupancy_values else 0

        # Общая выручка
        total_revenue = sum(h.get('total_revenue', 0) for h in report_data)

        # Всего билетов
        total_tickets = sum(h.get('sold_tickets', 0) for h in report_data)

        return {
            'avg_occupancy': avg_occupancy,
            'total_revenue': round(total_revenue, 2),
            'total_tickets': total_tickets
        }