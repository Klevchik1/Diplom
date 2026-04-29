# ticket/export_utils.py - ИСПРАВЛЕННАЯ ВЕРСИЯ

import json
import os
from io import BytesIO
from django.conf import settings
from django.http import HttpResponse
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer


class LogExporter:
    """Утилита для экспорта логов в различные форматы"""

    @staticmethod
    def export_logs_to_json(queryset, filename=None):
        """Экспорт логов в JSON"""
        if filename is None:
            filename = f"logs_export_{timezone.now().strftime('%Y%m%d_%H%M')}.json"

        logs_data = []
        for log in queryset:
            log_data = {
                'timestamp': log.timestamp.isoformat(),
                'user': log.user.email if log.user else None,
                'action_type': log.action_type,
                'action_type_display': log.get_action_type_display(),
                'module_type': log.module_type,
                'module_type_display': log.get_module_type_display(),
                'description': log.description,
                'object_repr': log.object_repr,
                'object_id': log.object_id,
                'ip_address': log.ip_address,
                'user_agent': log.user_agent,
                'additional_data': log.additional_data
            }
            logs_data.append(log_data)

        response = HttpResponse(
            json.dumps(logs_data, ensure_ascii=False, indent=2),
            content_type='application/json; charset=utf-8'
        )
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    @staticmethod
    def export_logs_to_pdf(queryset, filename=None):
        """Экспорт логов в PDF с фиксированными ширинами столбцов и переносом текста"""
        if filename is None:
            filename = f"logs_export_{timezone.now().strftime('%Y%m%d_%H%M')}.pdf"

        buffer = BytesIO()
        # Книжная ориентация с увеличенными отступами
        doc = SimpleDocTemplate(buffer, pagesize=A4,
                                rightMargin=20, leftMargin=20, topMargin=30, bottomMargin=30)
        elements = []

        # Регистрируем шрифты
        has_custom_font = LogExporter._register_custom_fonts()

        # Заголовок
        title_style = ParagraphStyle(
            name='CustomTitle',
            fontName='DejaVuSans' if has_custom_font else 'Helvetica-Bold',
            fontSize=16,
            spaceAfter=25,
            alignment=1,
            textColor=colors.black
        )

        title_text = Paragraph(f"Экспорт логов операций - {timezone.now().strftime('%d.%m.%Y %H:%M')}", title_style)
        elements.append(title_text)

        # Статистика
        stats_style = ParagraphStyle(
            name='StatsStyle',
            fontName='DejaVuSans' if has_custom_font else 'Helvetica',
            fontSize=10,
            spaceAfter=20,
            alignment=1
        )

        total_logs = queryset.count()
        stats_text = Paragraph(f"Всего записей: {total_logs}", stats_style)
        elements.append(stats_text)

        # Таблица логов
        if queryset.exists():
            # Создаем данные таблицы с форматированием текста для переноса
            table_data = [['Время', 'Пользователь', 'Действие', 'Модуль', 'Описание', 'Объект']]

            for log in queryset:
                # Форматируем текст с переносами
                description = LogExporter._format_text_for_wrapping(log.description, 120)
                object_repr = LogExporter._format_text_for_wrapping(log.object_repr or '-', 60)
                user_email = log.user.email if log.user else 'Система'

                # Создаем Paragraph объекты для автоматического переноса текста
                time_para = Paragraph(log.timestamp.strftime('%d.%m.%Y<br/>%H:%M'),
                                      LogExporter._get_cell_style(has_custom_font))
                user_para = Paragraph(user_email, LogExporter._get_cell_style(has_custom_font))
                action_para = Paragraph(log.get_action_type_display(),
                                        LogExporter._get_cell_style(has_custom_font))
                module_para = Paragraph(log.get_module_type_display(),
                                        LogExporter._get_cell_style(has_custom_font))
                desc_para = Paragraph(description, LogExporter._get_cell_style(has_custom_font))
                object_para = Paragraph(object_repr, LogExporter._get_cell_style(has_custom_font))

                table_data.append([
                    time_para,
                    user_para,
                    action_para,
                    module_para,
                    desc_para,
                    object_para
                ])

            # Фиксированные ширины столбцов (в points)
            col_widths = [60, 90, 70, 70, 180, 100]  # Сумма: 570pt (вмещается в A4 с отступами)

            table = Table(table_data, colWidths=col_widths, repeatRows=1)
            table.setStyle(TableStyle([
                # Заголовок таблицы
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2E86AB')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),
                ('FONTNAME', (0, 0), (-1, 0), 'DejaVuSans' if has_custom_font else 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
                ('TOPPADDING', (0, 0), (-1, 0), 10),

                # Стиль для данных
                ('ALIGN', (0, 1), (-1, -1), 'LEFT'),
                ('VALIGN', (0, 1), (-1, -1), 'TOP'),
                ('FONTNAME', (0, 1), (-1, -1), 'DejaVuSans' if has_custom_font else 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 8),

                # Отступы в ячейках
                ('LEFTPADDING', (0, 0), (-1, -1), 6),
                ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                ('TOPPADDING', (0, 0), (-1, -1), 5),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 5),

                # Границы и фон
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8F9FA')]),
            ]))

            elements.append(table)

            # Добавляем информацию о дополнительных данных
            if any(log.additional_data for log in queryset):
                info_style = ParagraphStyle(
                    name='InfoStyle',
                    fontName='DejaVuSans' if has_custom_font else 'Helvetica-Oblique',
                    fontSize=7,
                    spaceAfter=10,
                    alignment=0,
                    textColor=colors.grey,
                    leftIndent=10
                )
                elements.append(Spacer(1, 15))
                elements.append(Paragraph("* Для просмотра полных данных используйте JSON экспорт", info_style))

        else:
            no_data_style = ParagraphStyle(
                name='NoDataStyle',
                fontName='DejaVuSans' if has_custom_font else 'Helvetica',
                fontSize=12,
                spaceAfter=20,
                alignment=1,
                textColor=colors.grey
            )
            elements.append(Paragraph("Нет данных для экспорта", no_data_style))

        doc.build(elements)
        buffer.seek(0)

        response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    @staticmethod
    def _format_text_for_wrapping(text, max_length):
        """Форматирует текст для переноса - добавляет пробелы для длинных слов"""
        if not text:
            return "-"

        # Если текст короткий, возвращаем как есть
        if len(text) <= max_length:
            return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

        # Для длинного текста добавляем пробелы после каждых max_length символов
        words = text.split()
        result = []
        current_line = ""

        for word in words:
            # Если слово очень длинное, разбиваем его
            if len(word) > max_length:
                if current_line:
                    result.append(current_line)
                    current_line = ""

                # Разбиваем длинное слово на части
                for i in range(0, len(word), max_length):
                    result.append(word[i:i + max_length])
            else:
                if len(current_line + " " + word) <= max_length:
                    if current_line:
                        current_line += " " + word
                    else:
                        current_line = word
                else:
                    if current_line:
                        result.append(current_line)
                    current_line = word

        if current_line:
            result.append(current_line)

        return "<br/>".join(result)

    @staticmethod
    def _get_cell_style(has_custom_font):
        """Возвращает стиль для ячеек таблицы"""
        return ParagraphStyle(
            name='CellStyle',
            fontName='DejaVuSans' if has_custom_font else 'Helvetica',
            fontSize=8,
            leading=9,  # Межстрочный интервал
            leftIndent=0,
            rightIndent=0,
            wordWrap='LTR',  # Исправлено: строка вместо булева значения
            spaceBefore=0,
            spaceAfter=0
        )

    @staticmethod
    def _register_custom_fonts():
        """Регистрация кастомных шрифтов для PDF"""
        try:
            fonts_dir = os.path.join(settings.BASE_DIR, 'ticket', 'fonts')
            dejavu_sans_path = os.path.join(fonts_dir, 'DejaVuSans.ttf')

            if os.path.exists(dejavu_sans_path):
                pdfmetrics.registerFont(TTFont('DejaVuSans', dejavu_sans_path))
                return True
            return False
        except Exception:
            return False

    @staticmethod
    def get_export_formats():
        """Возвращает доступные форматы экспорта"""
        return [
            ('json', 'JSON'),
            ('pdf', 'PDF'),
        ]