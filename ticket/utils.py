import os
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from django.conf import settings
import qrcode
from io import BytesIO
from reportlab.lib.pagesizes import A5
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle
from reportlab.lib.units import cm
from django.utils import timezone
import logging
logger = logging.getLogger(__name__)
import zipfile
from io import BytesIO
import re


try:
    font_path = os.path.join(settings.BASE_DIR, 'ticket', 'fonts', 'DejaVuSans.ttf')
    pdfmetrics.registerFont(TTFont('DejaVuSans', font_path))
    base_font_name = 'DejaVuSans'
except:
    base_font_name = 'Helvetica'

try:
    font_path = os.path.join(settings.BASE_DIR, 'ticket', 'fonts', 'DejaVuSans.ttf')
    bold_font_path = os.path.join(settings.BASE_DIR, 'ticket', 'fonts', 'DejaVuSans-Bold.ttf')

    pdfmetrics.registerFont(TTFont('DejaVuSans', font_path))
    pdfmetrics.registerFont(TTFont('DejaVuSans-Bold', bold_font_path))

    base_font_name = 'DejaVuSans'
    bold_font_name = 'DejaVuSans-Bold'
except Exception as e:
    print(f"Error loading fonts: {e}")
    base_font_name = 'Helvetica'
    bold_font_name = 'Helvetica-Bold'

styles = getSampleStyleSheet()
custom_styles = {
    'Title': ParagraphStyle(
        name='Title',
        fontName=base_font_name,
        fontSize=18,
        alignment=1,
        spaceAfter=12
    ),
    'Header': ParagraphStyle(
        name='Header',
        fontName=base_font_name,
        fontSize=12,
        textColor=colors.darkblue,
        spaceAfter=6
    ),
    'NormalCenter': ParagraphStyle(
        name='NormalCenter',
        fontName=base_font_name,
        fontSize=10,
        alignment=1,
        spaceAfter=6
    ),
    'SmallCenter': ParagraphStyle(
        name='SmallCenter',
        fontName=base_font_name,
        fontSize=8,
        alignment=1,
        textColor=colors.grey
    ),
    'Bold': ParagraphStyle(
        name='Bold',
        fontName=base_font_name,
        fontSize=10,
        leading=14,
        textColor=colors.black,
        spaceAfter=6,
        alignment=1
    )
}

def generate_ticket_pdf(tickets):
    """Старая функция для обратной совместимости"""
    return generate_enhanced_ticket_pdf(tickets)


def generate_enhanced_ticket_pdf(tickets):
    """Классический минималистичный дизайн билета"""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A5,
        title=f"Билеты на сеанс - Кинотеатр Премьера",
        leftMargin=1 * cm,
        rightMargin=1 * cm,
        topMargin=0.5 * cm,
        bottomMargin=0.5 * cm
    )

    elements = []

    first_ticket = tickets[0]
    total_price = sum(ticket.price for ticket in tickets)

    # Минималистичные стили
    minimal_styles = {
        'Header': ParagraphStyle(
            name='Header',
            fontName=bold_font_name,
            fontSize=12,
            alignment=1,
            textColor=colors.black,
            spaceAfter=6
        ),
        'Title': ParagraphStyle(
            name='Title',
            fontName=bold_font_name,
            fontSize=10,
            alignment=0,
            textColor=colors.black,
            spaceAfter=4
        ),
        'Info': ParagraphStyle(
            name='Info',
            fontName=base_font_name,
            fontSize=9,
            alignment=0,
            textColor=colors.black,
            spaceAfter=3
        ),
        'Small': ParagraphStyle(
            name='Small',
            fontName=base_font_name,
            fontSize=7,
            alignment=1,
            textColor=colors.grey
        ),
        'Seat': ParagraphStyle(
            name='Seat',
            fontName=bold_font_name,
            fontSize=9,
            alignment=1,
            textColor=colors.black
        )
    }

    # === ЗАГОЛОВОК ===
    elements.append(Paragraph("КИНОТЕАТР ПРЕМЬЕРА", minimal_styles['Header']))
    elements.append(Spacer(1, 0.2 * cm))

    # Горизонтальная линия
    elements.append(Table([['']], colWidths=[doc.width], style=[
        ('LINEABOVE', (0, 0), (-1, -1), 1, colors.black)
    ]))
    elements.append(Spacer(1, 0.2 * cm))

    # === ФИЛЬМ ===
    elements.append(Paragraph(f"<b>ФИЛЬМ:</b> {first_ticket.screening.movie.title}", minimal_styles['Title']))
    genres_list = ", ".join(g.name for g in first_ticket.screening.movie.genres.all())
    elements.append(Paragraph(f"Жанр: {genres_list}", minimal_styles['Info']))

    # ИСПРАВЛЕНИЕ: Форматируем длительность правильно
    duration_minutes = first_ticket.screening.movie.duration
    if duration_minutes:
        hours = duration_minutes // 60
        minutes = duration_minutes % 60
        if hours > 0:
            duration_str = f"{hours} ч {minutes} мин"
        else:
            duration_str = f"{minutes} мин"
    else:
        duration_str = "Не указано"

    elements.append(Paragraph(f"Продолжительность: {duration_str}", minimal_styles['Info']))
    elements.append(Spacer(1, 0.2 * cm))

    # === СЕАНС ===
    screening_time = f"{first_ticket.screening.start_time.strftime('%d.%m.%Y %H:%M')}"
    elements.append(Paragraph(f"<b>СЕАНС:</b> {screening_time}", minimal_styles['Title']))
    elements.append(Paragraph(f"Зал: {first_ticket.screening.hall.name}", minimal_styles['Info']))
    elements.append(Spacer(1, 0.2 * cm))

    # === ПОКУПАТЕЛЬ ===
    elements.append(
        Paragraph(f"<b>ПОКУПАТЕЛЬ:</b> {first_ticket.user.name} {first_ticket.user.surname}", minimal_styles['Title']))
    elements.append(Paragraph(f"Телефон: {first_ticket.user.number}", minimal_styles['Info']))
    elements.append(Spacer(1, 0.2 * cm))

    # === МЕСТА ===
    elements.append(Paragraph("<b>ВЫБРАННЫЕ МЕСТА:</b>", minimal_styles['Title']))

    seats_data = [['Ряд', 'Место', 'Цена']]
    for ticket in tickets:
        seats_data.append([
            Paragraph(str(ticket.seat.row), minimal_styles['Seat']),
            Paragraph(str(ticket.seat.number), minimal_styles['Seat']),
            Paragraph(f"{ticket.price} ₽", minimal_styles['Seat'])
        ])

    # УВЕЛИЧИВАЕМ РАЗМЕРЫ ЯЧЕЕК: было [2*cm, 2*cm, 2*cm]
    seats_table = Table(seats_data, colWidths=[3.5 * cm, 3.5 * cm, 4 * cm], repeatRows=1)
    seats_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, 0), bold_font_name),
        ('FONTSIZE', (0, 0), (-1, 0), 11),  # Увеличили шрифт заголовков
        ('FONTSIZE', (0, 1), (-1, -1), 10),  # Увеличили шрифт данных
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),  # Добавили фон для заголовка
        ('TOPPADDING', (0, 0), (-1, -1), 8),  # Увеличили верхний отступ
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),  # Увеличили нижний отступ
        ('LEFTPADDING', (0, 0), (-1, -1), 10),  # Увеличили левый отступ
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),  # Увеличили правый отступ
    ]))
    elements.append(seats_table)
    elements.append(Spacer(1, 0.3 * cm))  # Увеличили отступ после таблицы

    # === ИТОГО ===
    elements.append(
        Paragraph(f"<b>ИТОГО: {len(tickets)} билет(а) на сумму {total_price} ₽</b>", minimal_styles['Title']))
    elements.append(Spacer(1, 0.3 * cm))

    # === QR-КОД ===
    qr_data = {
        "ticket_id": tickets[0].id,
        "group_id": str(tickets[0].ticket_group.group_uuid) if tickets[0].ticket_group else None,
        "film": first_ticket.screening.movie.title,
        "datetime": first_ticket.screening.start_time.isoformat(),
        "hall": first_ticket.screening.hall.name,
        "seats": ", ".join(f"{t.seat.row}-{t.seat.number}" for t in tickets),
        "total_price": total_price,
        "user": f"{first_ticket.user.name} {first_ticket.user.surname}",
        "cinema": "Кинотеатр Премьера"
    }

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=6,
        border=1,
    )
    qr.add_data(str(qr_data))
    qr.make(fit=True)

    qr_img = qr.make_image(fill_color="black", back_color="white")
    qr_buffer = BytesIO()
    qr_img.save(qr_buffer, format="PNG")
    qr_buffer.seek(0)

    # QR-код по центру
    qr_table = Table([[Image(qr_buffer, width=3.5 * cm, height=3.5 * cm)]], colWidths=[doc.width])
    qr_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
    ]))
    elements.append(qr_table)
    elements.append(Spacer(1, 0.1 * cm))

    # === ИНФОРМАЦИЯ ПОД QR-КОДОМ ===
    from django.utils import timezone
    elements.append(
        Paragraph(f"ID: {tickets[0].id} | {timezone.now().strftime('%d.%m.%Y %H:%M')}", minimal_styles['Small']))
    elements.append(Spacer(1, 0.2 * cm))

    # === ПРАВИЛА ===
    rules_text = """
    • Билет действителен только на указанный сеанс
    • Сохраняйте билет до конца сеанса
    """
    elements.append(Paragraph(rules_text, minimal_styles['Small']))

    # === ИНФОРМАЦИЯ О ВОЗВРАТЕ ===
    elements.append(Spacer(1, 0.2 * cm))
    refund_text = """
    <b>Политика возврата билетов:</b><br/>
    • Возврат возможен не позднее чем за 30 минут до начала сеанса<br/>
    • Возвращается полная стоимость билета<br/>
    • Для возврата обратитесь в личном кабинете<br/>
    """
    elements.append(Paragraph(refund_text, minimal_styles['Small']))
    elements.append(Spacer(1, 0.2 * cm))

    # Контакты
    elements.append(Paragraph(" +7 (950) 080-19-02", minimal_styles['Small']))

    doc.build(elements)
    buffer.seek(0)
    return buffer


def generate_individual_tickets_zip(tickets):
    """
    Генерация ZIP-архива с отдельными PDF-билетами на каждое место

    Args:
        tickets: QuerySet или список объектов Ticket

    Returns:
        BytesIO: ZIP-архив в памяти
    """
    buffer = BytesIO()

    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for ticket in tickets:
            # Используем существующую функцию generate_enhanced_ticket_pdf из этого же файла
            pdf_buffer = generate_enhanced_ticket_pdf([ticket])

            # Формируем имя файла
            seat_info = f"ряд{ticket.seat.row}_место{ticket.seat.number}"
            movie_title = ticket.screening.movie.title
            # Очищаем название от недопустимых символов для имени файла
            safe_title = re.sub(r'[\\/*?:"<>|]', '', movie_title)
            filename = f"{safe_title}_{seat_info}.pdf"

            zip_file.writestr(filename, pdf_buffer.getvalue())

    buffer.seek(0)
    return buffer