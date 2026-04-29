"""
FPOS-02-тест-pdf-генерации-2
Тестирование генерации PDF отчетов
"""
import os
import tempfile
from datetime import datetime, timedelta
from django.test import TestCase
from django.conf import settings
from ticket.pdf_utils import generate_pdf_report, register_custom_fonts


class PDFGenerationTest(TestCase):
    """Тестирование генерации PDF документов"""

    def setUp(self):
        """Настройка тестовых данных для отчетов"""
        self.test_data = [
            {
                'date': datetime(2024, 1, 1),
                'revenue': 15000.50,
                'tickets_sold': 50
            },
            {
                'date': datetime(2024, 1, 2),
                'revenue': 18000.75,
                'tickets_sold': 60
            }
        ]

        # Создаем тестовую директорию для шрифтов если её нет
        fonts_dir = os.path.join(settings.BASE_DIR, 'ticket', 'fonts')
        if not os.path.exists(fonts_dir):
            os.makedirs(fonts_dir, exist_ok=True)

    def test_fpos_02_pdf_report_generation(self):
        """FPOS-02: Успешная генерация PDF отчетов разных типов"""
        print("\n" + "=" * 60)
        print("FPOS-02-тест-pdf-генерации-2")
        print("Тест: Генерация PDF отчетов")
        print("=" * 60)

        # Шаг 1: Регистрация шрифтов
        print("Шаг 1: Регистрация кастомных шрифтов...")
        fonts_registered = register_custom_fonts()
        if fonts_registered:
            print("✓ Кастомные шрифты зарегистрированы")
        else:
            print("⚠ Используются стандартные шрифты (ожидаемое поведение)")

        # Шаг 2: Генерация финансового отчета
        print("Шаг 2: Генерация финансового отчета...")
        filters = {
            'start_date': '2024-01-01',
            'end_date': '2024-01-31',
            'period': 'daily'
        }

        try:
            pdf_buffer = generate_pdf_report(
                data=self.test_data,
                report_type='revenue',
                title='Тестовый финансовый отчет',
                filters=filters
            )

            # Проверяем что PDF создан
            self.assertIsNotNone(pdf_buffer)
            pdf_content = pdf_buffer.getvalue()
            self.assertGreater(len(pdf_content), 0)
            self.assertIn(b'%PDF', pdf_content[:100])  # Проверяем сигнатуру PDF
            print(f"✓ Финансовый отчет создан, размер: {len(pdf_content)} байт")

        except Exception as e:
            self.fail(f"Ошибка генерации финансового отчета: {e}")

        # Шаг 3: Генерация отчета по фильмам
        print("Шаг 3: Генерация отчета по популярным фильмам...")
        movies_data = [
            {
                'title': 'Тестовый фильм 1',
                'genre': 'Боевик',
                'tickets_sold': 150,
                'total_revenue': 45000.00,
                'popularity_percentage': 45.5
            },
            {
                'title': 'Тестовый фильм 2',
                'genre': 'Комедия',
                'tickets_sold': 120,
                'total_revenue': 36000.00,
                'popularity_percentage': 36.4
            }
        ]

        try:
            pdf_buffer = generate_pdf_report(
                data=movies_data,
                report_type='movies',
                title='Отчет по популярности фильмов',
                filters={}
            )

            pdf_content = pdf_buffer.getvalue()
            self.assertGreater(len(pdf_content), 0)
            print(f"✓ Отчет по фильмам создан, размер: {len(pdf_content)} байт")

        except Exception as e:
            self.fail(f"Ошибка генерации отчета по фильмам: {e}")

        # Шаг 4: Генерация отчета по залам
        print("Шаг 4: Генерация отчета по загруженности залов...")
        halls_data = [
            {
                'name': 'Зал 1 (VIP)',
                'total_seats': 100,
                'total_screenings': 10,
                'sold_tickets': 750,
                'total_revenue': 225000.00,
                'occupancy_percent': 75.0
            }
        ]

        try:
            pdf_buffer = generate_pdf_report(
                data=halls_data,
                report_type='halls',
                title='Отчет по загруженности залов',
                filters={}
            )

            pdf_content = pdf_buffer.getvalue()
            self.assertGreater(len(pdf_content), 0)
            print(f"✓ Отчет по залам создан, размер: {len(pdf_content)} байт")

        except Exception as e:
            self.fail(f"Ошибка генерации отчета по залам: {e}")

        # Шаг 5: Сохранение PDF во временный файл для проверки
        print("Шаг 5: Сохранение PDF во временный файл...")
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_file:
            temp_file.write(pdf_content)
            temp_path = temp_file.name

        # Проверяем что файл существует и не пустой
        self.assertTrue(os.path.exists(temp_path))
        self.assertGreater(os.path.getsize(temp_path), 0)
        print(f"✓ PDF сохранен во временный файл: {temp_path}")

        # Очистка
        os.unlink(temp_path)

        print("\n" + "=" * 60)
        print("РЕЗУЛЬТАТ: ТЕСТ УСПЕШНО ПРОЙДЕН ✅")
        print(f"Все типы отчетов сгенерированы корректно")
        print("=" * 60)