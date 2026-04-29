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
                        hour, minute = value.split(':')[:2]
                        return [hour.zfill(2), minute.zfill(2)]
                except:
                    pass
        return [None, None]

    def value_from_datadict(self, data, files, name):
        """Собираем часы и минуты обратно в строку времени"""
        hour = data.get(f'{name}_0', '').zfill(2)
        minute = data.get(f'{name}_1', '').zfill(2)

        if hour and minute:
            return f'{hour}:{minute}:00'
        return ''

    def format_output(self, rendered_widgets):
        """Форматируем вывод с двоеточием между полями"""
        return f'{rendered_widgets[0]} : {rendered_widgets[1]}'