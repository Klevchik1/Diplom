from django import forms
from django.utils import timezone
import datetime


class TimePickerWidget(forms.MultiWidget):
    """Виджет для удобного выбора времени (часы:минуты)"""

    def __init__(self, attrs=None):
        # Создаем выбор часов (8-23 для кинотеатра)
        hours = [(str(h).zfill(2), str(h).zfill(2)) for h in range(8, 24)]

        # Создаем выбор минут с шагом 10 минут
        minutes = [(str(m).zfill(2), str(m).zfill(2)) for m in range(0, 60, 10)]

        widgets = [
            forms.Select(choices=hours, attrs={'class': 'time-hour', 'style': 'min-width: 70px;'}),
            forms.Select(choices=minutes, attrs={'class': 'time-minute', 'style': 'min-width: 70px;'})
        ]

        super().__init__(widgets, attrs)

    def decompress(self, value):
        """Разбиваем значение времени на часы и минуты"""
        if value:
            if isinstance(value, datetime.time):
                return [value.hour, value.minute]
            elif isinstance(value, str):
                try:
                    if ':' in value:
                        parts = value.split(':')
                        hour = parts[0].zfill(2) if parts[0] else '00'
                        minute = parts[1].zfill(2) if len(parts) > 1 else '00'
                        return [hour, minute]
                except:
                    pass
        return [None, None]

    def value_from_datadict(self, data, files, name):
        """Собираем часы и минуты обратно в строку времени (ТОЛЬКО ЧЧ:ММ)"""
        hour = data.get(f'{name}_0', '').zfill(2)
        minute = data.get(f'{name}_1', '').zfill(2)

        if hour and minute and hour != 'None' and minute != 'None':
            return f'{hour}:{minute}'
        return ''

    def format_output(self, rendered_widgets):
        """Форматируем вывод с двоеточием между полями"""
        return f'{rendered_widgets[0]} : {rendered_widgets[1]}'