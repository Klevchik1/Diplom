from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.units import mm
import os
from django.conf import settings
from django.utils import timezone
import qrcode
from PIL import Image as PILImage
import tempfile

# Импорт модели TicketGroup, если используется в функциях
from .models import TicketGroup


def register_custom_fonts():
    """Регистрация кастомных шрифтов"""
    try:
        fonts_dir = os.path.join(settings.BASE_DIR, 'ticket', 'fonts')
        dejavu_sans_path = os.path.join(fonts_dir, 'DejaVuSans.ttf')
        dejavu_sans_bold_path = os.path.join(fonts_dir, 'DejaVuSans-Bold.ttf')

        if os.path.exists(dejavu_sans_path):
            pdfmetrics.registerFont(TTFont('DejaVuSans', dejavu_sans_path))
        if os.path.exists(dejavu_sans_bold_path):
            pdfmetrics.registerFont(TTFont('DejaVuSans-Bold', dejavu_sans_bold_path))
            return True
        return False
    except Exception as e:
        print(f"Font registration error: {e}")
        return False


def create_wrapped_text(text, font_name='Helvetica', font_size=9, alignment=TA_CENTER):
    """Создает Paragraph с переносом текста"""
    wrap_style = ParagraphStyle(
        name='WrapStyle',
        fontName=font_name,
        fontSize=font_size,
        alignment=alignment,
        wordWrap='CJK',
        spaceBefore=2,
        spaceAfter=2
    )
    return Paragraph(str(text), wrap_style)


def generate_qr_code(data):
    """Генерация QR-кода для билета"""
    try:
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=3,
            border=1,
        )
        qr.add_data(data)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")

        # Сохраняем во временный файл
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
        img.save(temp_file.name)
        return temp_file.name
    except Exception as e:
        print(f"QR code generation error: {e}")
        return None


def generate_pdf_report(data, report_type, title, filters, user=None):
    """
    Генерация PDF отчета с метаданными (без эмодзи)
    data - данные отчета
    report_type - тип отчета (revenue, movies, halls, sales)
    title - название отчета
    filters - словарь с фильтрами (период, даты)
    user - пользователь, сформировавший отчет (опционально)
    """
    from django.contrib.auth import get_user_model
    from datetime import datetime
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib.units import mm
    import os
    from django.conf import settings

    buffer = BytesIO()

    # Определяем ориентацию страницы
    if report_type == 'halls':
        pagesize = landscape(A4)
    else:
        pagesize = A4

    doc = SimpleDocTemplate(
        buffer,
        pagesize=pagesize,
        rightMargin=15 * mm,
        leftMargin=15 * mm,
        topMargin=25 * mm,
        bottomMargin=20 * mm
    )
    elements = []

    # Регистрируем шрифты
    has_custom_font = register_custom_fonts()
    font_name = 'DejaVuSans' if has_custom_font else 'Helvetica'
    font_name_bold = 'DejaVuSans-Bold' if has_custom_font else 'Helvetica-Bold'

    # ============================================================
    # ШАПКА ДОКУМЕНТА С МЕТАДАННЫМИ (БЕЗ ЭМОДЗИ)
    # ============================================================

    # 1. Заголовок
    title_style = ParagraphStyle(
        name='CustomTitle',
        fontName=font_name_bold,
        fontSize=16,
        spaceAfter=8,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#2E86AB')
    )
    elements.append(Paragraph(f"<b>КИНОТЕАТР «ПРЕМЬЕРА»</b>", title_style))

    # 2. Название отчета
    report_title_style = ParagraphStyle(
        name='ReportTitle',
        fontName=font_name_bold,
        fontSize=14,
        spaceAfter=15,
        alignment=TA_CENTER,
        textColor=colors.black
    )

    # Маппинг типов отчётов
    title_map = {
        'revenue': 'Отчёт по выручке',
        'movies': 'Отчёт по популярности фильмов',
        'halls': 'Отчёт по загруженности залов',
        'sales': 'Отчёт по продажам'
    }
    report_display_name = title_map.get(report_type, title)
    elements.append(Paragraph(f"<b>{report_display_name}</b>", report_title_style))

    elements.append(Spacer(1, 5 * mm))

    # 3. Информационная таблица с метаданными (без эмодзи)
    # Создаём стили для ячеек
    meta_label_style = ParagraphStyle(
        name='MetaLabel',
        fontName=font_name_bold,
        fontSize=10,
        alignment=TA_LEFT,
        textColor=colors.HexColor('#2E86AB')
    )

    meta_value_style = ParagraphStyle(
        name='MetaValue',
        fontName=font_name,
        fontSize=10,
        alignment=TA_LEFT,
        textColor=colors.black
    )

    # Формируем данные для таблицы метаданных (без эмодзи)
    meta_data = [
        [Paragraph("<b>Название отчёта:</b>", meta_label_style), Paragraph(report_display_name, meta_value_style)],
        [Paragraph("<b>Дата формирования:</b>", meta_label_style),
         Paragraph(datetime.now().strftime('%d.%m.%Y %H:%M:%S'), meta_value_style)],
    ]

    # Добавляем информацию о периоде
    period_text = ""
    if filters.get('period'):
        period_map = {
            'daily': 'по дням',
            'weekly': 'по неделям',
            'monthly': 'по месяцам'
        }
        period_text = period_map.get(filters.get('period'), filters.get('period'))

    if filters.get('start_date') and filters.get('end_date'):
        date_text = f"с {filters['start_date']} по {filters['end_date']}"
        if period_text:
            date_text = f"{period_text}, {date_text}"
    elif filters.get('start_date'):
        date_text = f"с {filters['start_date']}"
        if period_text:
            date_text = f"{date_text} (период: {period_text})"
    elif filters.get('end_date'):
        date_text = f"по {filters['end_date']}"
        if period_text:
            date_text = f"{date_text} (период: {period_text})"
    else:
        date_text = f"период: {period_text}" if period_text else "за всё время"

    meta_data.append([Paragraph("<b>Период:</b>", meta_label_style), Paragraph(date_text, meta_value_style)])

    # Добавляем информацию о пользователе
    if user:
        # Формируем ФИО пользователя
        if user.name and user.surname:
            user_full_name = f"{user.name} {user.surname}"
        elif user.name:
            user_full_name = user.name
        elif user.surname:
            user_full_name = user.surname
        else:
            user_full_name = user.email

        meta_data.append(
            [Paragraph("<b>Сформировал:</b>", meta_label_style), Paragraph(user_full_name, meta_value_style)])
        meta_data.append([Paragraph("<b>Email:</b>", meta_label_style), Paragraph(user.email, meta_value_style)])

    # Создаём таблицу метаданных (2 колонки)
    meta_table = Table(meta_data, colWidths=[50 * mm, 100 * mm])
    meta_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#F0F8FF')),
    ]))

    elements.append(meta_table)
    elements.append(Spacer(1, 8 * mm))

    # Генерация основной таблицы в зависимости от типа отчета
    if report_type == 'revenue':
        elements.extend(generate_revenue_table(data, has_custom_font, filters.get('period')))
    elif report_type == 'movies':
        elements.extend(generate_movies_table(data, has_custom_font))
    elif report_type == 'halls':
        elements.extend(generate_halls_table(data, has_custom_font))
    elif report_type == 'sales':
        elements.extend(generate_sales_table(data, has_custom_font))

    # Подвал документа (без эмодзи)
    elements.append(Spacer(1, 10 * mm))

    footer_style = ParagraphStyle(
        name='Footer',
        fontName=font_name,
        fontSize=8,
        alignment=TA_CENTER,
        textColor=colors.grey
    )

    elements.append(Paragraph("-" * 60, footer_style))
    elements.append(Paragraph(
        f"Отчёт сгенерирован автоматически системой управления кинотеатром «Премьера» | {datetime.now().strftime('%d.%m.%Y')}",
        footer_style
    ))

    doc.build(elements)
    buffer.seek(0)
    return buffer


def generate_revenue_table(data, has_custom_font, period):
    """Генерация таблицы выручки с переносом текста"""
    elements = []
    font_name = 'DejaVuSans' if has_custom_font else 'Helvetica'
    font_name_bold = 'DejaVuSans-Bold' if has_custom_font else 'Helvetica-Bold'

    if not data:
        elements.append(Paragraph("Нет данных для отображения", getSampleStyleSheet()['Normal']))
        return elements

    period_map = {
        'daily': 'по дням',
        'weekly': 'по неделям',
        'monthly': 'по месяцам'
    }
    period_text = period_map.get(period, '')

    if period_text:
        period_style = ParagraphStyle(
            name='PeriodStyle',
            fontName=font_name,
            fontSize=9,
            spaceAfter=8,
            alignment=TA_CENTER
        )
        elements.append(Paragraph(f"<i>Отчет {period_text}</i>", period_style))

    # Заголовки таблицы
    table_data = [[
        create_wrapped_text('Период', font_name_bold, 9, TA_CENTER),
        create_wrapped_text('Выручка (руб.)', font_name_bold, 9, TA_CENTER),
        create_wrapped_text('Продано билетов', font_name_bold, 9, TA_CENTER),
        create_wrapped_text('Средний чек (руб.)', font_name_bold, 9, TA_CENTER)
    ]]

    # Данные таблицы
    for item in data:
        if 'date' in item and item['date']:
            if hasattr(item['date'], 'strftime'):
                period_display = item['date'].strftime('%d.%m.%Y')
            else:
                period_display = str(item['date'])
        elif 'week' in item:
            period_display = f"Неделя {int(item['week'])}, {int(item['year'])}"
        elif 'month' in item:
            period_display = f"{int(item['month']):02d}/{int(item['year'])}"
        else:
            period_display = "Неизвестный период"

        tickets = item.get('tickets_sold', 0)
        revenue = float(item.get('revenue', 0) or 0)
        avg_ticket = revenue / tickets if tickets > 0 else 0

        table_data.append([
            create_wrapped_text(period_display, font_name, 8, TA_CENTER),
            create_wrapped_text(f"{revenue:.2f}", font_name, 8, TA_CENTER),
            create_wrapped_text(str(tickets), font_name, 8, TA_CENTER),
            create_wrapped_text(f"{avg_ticket:.2f}", font_name, 8, TA_CENTER)
        ])

    table = Table(table_data, colWidths=[60 * mm, 40 * mm, 40 * mm, 40 * mm])

    table_style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2E86AB')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('BOX', (0, 0), (-1, -1), 1, colors.black),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ])

    for i in range(1, len(table_data)):
        if i % 2 == 0:
            table_style.add('BACKGROUND', (0, i), (-1, i), colors.HexColor('#F8F9FA'))

    table.setStyle(table_style)
    elements.append(table)
    elements.append(Spacer(1, 10 * mm))

    # Итоги
    total_revenue = sum(float(item.get('revenue', 0) or 0) for item in data)
    total_tickets = sum(item.get('tickets_sold', 0) for item in data)
    total_avg = total_revenue / total_tickets if total_tickets > 0 else 0

    total_style = ParagraphStyle(
        name='TotalStyle',
        fontName=font_name_bold,
        fontSize=10,
        spaceAfter=6,
        textColor=colors.black,
        alignment=TA_CENTER
    )

    elements.append(Paragraph(f"<b>Общая выручка:</b> {total_revenue:.2f} руб.", total_style))
    elements.append(Paragraph(f"<b>Всего билетов:</b> {total_tickets}", total_style))
    elements.append(Paragraph(f"<b>Средний чек:</b> {total_avg:.2f} руб.", total_style))

    return elements


def generate_movies_table(data, has_custom_font):
    """Генерация таблицы популярных фильмов (без эмодзи)"""
    elements = []
    font_name = 'DejaVuSans' if has_custom_font else 'Helvetica'
    font_name_bold = 'DejaVuSans-Bold' if has_custom_font else 'Helvetica-Bold'

    if not data:
        elements.append(Paragraph("Нет данных для отображения", getSampleStyleSheet()['Normal']))
        return elements

    # Заголовки таблицы
    table_data = [[
        create_wrapped_text('Номер', font_name_bold, 9, TA_CENTER),
        create_wrapped_text('Фильм', font_name_bold, 9, TA_CENTER),
        create_wrapped_text('Жанр', font_name_bold, 9, TA_CENTER),
        create_wrapped_text('Продано билетов', font_name_bold, 9, TA_CENTER),
        create_wrapped_text('Общая выручка (руб.)', font_name_bold, 9, TA_CENTER),
        create_wrapped_text('Популярность (%)', font_name_bold, 9, TA_CENTER)
    ]]

    # Данные таблицы
    for idx, movie in enumerate(data, 1):
        title = str(movie.get('title', 'Без названия'))
        genre = str(movie.get('genre', ''))
        tickets_sold = movie.get('tickets_sold', 0)
        total_revenue = float(movie.get('total_revenue', 0))
        popularity = float(movie.get('popularity_percentage', 0))

        table_data.append([
            create_wrapped_text(str(idx), font_name, 8, TA_CENTER),
            create_wrapped_text(title, font_name, 8, TA_CENTER),
            create_wrapped_text(genre, font_name, 8, TA_CENTER),
            create_wrapped_text(str(tickets_sold), font_name, 8, TA_CENTER),
            create_wrapped_text(f"{total_revenue:.2f}", font_name, 8, TA_CENTER),
            create_wrapped_text(f"{popularity:.1f}", font_name, 8, TA_CENTER)
        ])

    table = Table(table_data, colWidths=[20 * mm, 55 * mm, 30 * mm, 35 * mm, 40 * mm, 30 * mm])

    table_style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#28A745')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('BOX', (0, 0), (-1, -1), 1, colors.black),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ])

    for i in range(1, len(table_data)):
        if i % 2 == 0:
            table_style.add('BACKGROUND', (0, i), (-1, i), colors.HexColor('#F8F9FA'))

    table.setStyle(table_style)
    elements.append(table)
    elements.append(Spacer(1, 8 * mm))

    # Итоги
    total_tickets = sum(m.get('tickets_sold', 0) for m in data)
    total_revenue = sum(float(m.get('total_revenue', 0)) for m in data)

    total_style = ParagraphStyle(
        name='MovieTotalStyle',
        fontName=font_name_bold,
        fontSize=10,
        spaceAfter=6,
        textColor=colors.black,
        alignment=TA_CENTER
    )

    elements.append(Paragraph(f"<b>Всего билетов:</b> {total_tickets}", total_style))
    elements.append(Paragraph(f"<b>Общая выручка:</b> {total_revenue:.2f} руб.", total_style))

    return elements


def generate_halls_table(data, has_custom_font):
    """Генерация таблицы загруженности залов с полным переносом текста"""
    elements = []
    font_name = 'DejaVuSans' if has_custom_font else 'Helvetica'
    font_name_bold = 'DejaVuSans-Bold' if has_custom_font else 'Helvetica-Bold'

    if not data:
        elements.append(Paragraph("Нет данных для отображения", getSampleStyleSheet()['Normal']))
        return elements

    # Заголовки таблицы
    table_data = [[
        create_wrapped_text('Зал', font_name_bold, 9, TA_CENTER),
        create_wrapped_text('Всего мест', font_name_bold, 9, TA_CENTER),
        create_wrapped_text('Сеансов', font_name_bold, 9, TA_CENTER),
        create_wrapped_text('Продано билетов', font_name_bold, 9, TA_CENTER),
        create_wrapped_text('Выручка (руб.)', font_name_bold, 9, TA_CENTER),
        create_wrapped_text('Загруженность (%)', font_name_bold, 9, TA_CENTER)
    ]]

    # Данные таблицы
    for hall in data:
        hall_name = str(hall.get('name', ''))
        total_seats = hall.get('total_seats', 0)
        total_screenings = hall.get('total_screenings', 0)
        sold_tickets = hall.get('sold_tickets', 0)
        total_revenue = float(hall.get('total_revenue', 0))
        occupancy_percent = float(hall.get('occupancy_percent', 0))

        table_data.append([
            create_wrapped_text(hall_name, font_name, 8, TA_CENTER),
            create_wrapped_text(str(total_seats), font_name, 8, TA_CENTER),
            create_wrapped_text(str(total_screenings), font_name, 8, TA_CENTER),
            create_wrapped_text(str(sold_tickets), font_name, 8, TA_CENTER),
            create_wrapped_text(f"{total_revenue:.2f}", font_name, 8, TA_CENTER),
            create_wrapped_text(f"{occupancy_percent:.1f}", font_name, 8, TA_CENTER)
        ])

    table = Table(table_data, colWidths=[35 * mm, 25 * mm, 25 * mm, 35 * mm, 35 * mm, 35 * mm])

    table_style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#FFC107')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('BOX', (0, 0), (-1, -1), 1, colors.black),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ])

    for i in range(1, len(table_data)):
        if i % 2 == 0:
            table_style.add('BACKGROUND', (0, i), (-1, i), colors.HexColor('#F8F9FA'))

    table.setStyle(table_style)
    elements.append(table)
    elements.append(Spacer(1, 8 * mm))

    # Итоги
    if data:
        avg_occupancy = sum(float(h.get('occupancy_percent', 0)) for h in data) / len(data) if data else 0
        total_revenue = sum(float(h.get('total_revenue', 0)) for h in data)
        total_tickets = sum(h.get('sold_tickets', 0) for h in data)

        total_style = ParagraphStyle(
            name='HallTotalStyle',
            fontName=font_name_bold,
            fontSize=10,
            spaceAfter=6,
            textColor=colors.black,
            alignment=TA_CENTER
        )

        elements.append(Paragraph(f"<b>Средняя загруженность:</b> {avg_occupancy:.1f}%", total_style))
        elements.append(Paragraph(f"<b>Общая выручка:</b> {total_revenue:.2f} руб.", total_style))
        elements.append(Paragraph(f"<b>Всего билетов:</b> {total_tickets}", total_style))

    return elements


def generate_sales_table(data, has_custom_font):
    """Генерация таблицы общей статистики (без эмодзи)"""
    elements = []
    font_name = 'DejaVuSans' if has_custom_font else 'Helvetica'
    font_name_bold = 'DejaVuSans-Bold' if has_custom_font else 'Helvetica-Bold'

    if not data:
        elements.append(Paragraph("Нет данных для отображения", getSampleStyleSheet()['Normal']))
        return elements

    cell_style = ParagraphStyle(
        name='CellStyle',
        fontName=font_name,
        fontSize=9,
        wordWrap='CJK',
        alignment=TA_CENTER,
        spaceBefore=4,
        spaceAfter=4
    )

    cell_style_bold = ParagraphStyle(
        name='CellStyleBold',
        fontName=font_name_bold,
        fontSize=9,
        wordWrap='CJK',
        alignment=TA_CENTER,
        spaceBefore=4,
        spaceAfter=4
    )

    popular_movie = str(data.get('popular_movie', ''))

    table_data = [
        [
            Paragraph("<b>Показатель</b>", cell_style_bold),
            Paragraph("<b>Значение</b>", cell_style_bold)
        ],
        [
            Paragraph("Всего продано билетов", cell_style),
            Paragraph(str(data.get('total_tickets', 0)), cell_style)
        ],
        [
            Paragraph("Общая выручка (руб.)", cell_style),
            Paragraph(f"{data.get('total_revenue', 0):.2f}", cell_style)
        ],
        [
            Paragraph("Средняя цена билета (руб.)", cell_style),
            Paragraph(f"{data.get('avg_ticket_price', 0):.2f}", cell_style)
        ],
        [
            Paragraph("Самый популярный фильм", cell_style),
            Paragraph(popular_movie, cell_style)
        ],
        [
            Paragraph("Билетов на популярный фильм", cell_style),
            Paragraph(str(data.get('popular_movie_tickets', 0)), cell_style)
        ]
    ]

    table = Table(table_data, colWidths=[80 * mm, 80 * mm])

    table_style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#6F42C1')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('BOX', (0, 0), (-1, -1), 1, colors.black),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ])

    for i in range(1, len(table_data)):
        if i % 2 == 0:
            table_style.add('BACKGROUND', (0, i), (-1, i), colors.HexColor('#F8F9FA'))

    table.setStyle(table_style)
    elements.append(table)
    elements.append(Spacer(1, 10 * mm))

    # Добавляем информацию о доле популярного фильма
    total_tickets = data.get('total_tickets', 0)
    popular_tickets = data.get('popular_movie_tickets', 0)

    if total_tickets > 0:
        share_percent = (popular_tickets / total_tickets) * 100

        share_style = ParagraphStyle(
            name='ShareStyle',
            fontName=font_name_bold,
            fontSize=10,
            spaceBefore=5,
            spaceAfter=5,
            textColor=colors.HexColor('#28A745'),
            alignment=TA_CENTER
        )

        elements.append(Paragraph(f"<b>Доля популярного фильма:</b> {share_percent:.1f}% от всех продаж", share_style))

    return elements