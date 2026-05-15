import re
from django.core.exceptions import ValidationError


def validate_and_format_phone(number):
    """
    Валидирует и форматирует номер телефона.
    Принимает:
    - 10 цифр (9011234567)
    - 11 цифр с 7 (79011234567)
    - 11 цифр с 8 (89011234567)
    - в любом форматировании

    Возвращает: +7 (XXX) XXX-XX-XX
    """
    if not number:
        return number

    # Очищаем от всех нецифровых символов
    cleaned = re.sub(r'[^\d]', '', str(number))

    # Проверяем длину
    if len(cleaned) == 10:
        # Добавляем +7 для 10 цифр
        formatted = f"+7 ({cleaned[:3]}) {cleaned[3:6]}-{cleaned[6:8]}-{cleaned[8:]}"
    elif len(cleaned) == 11:
        if cleaned.startswith('7'):
            # 79011234567 -> +7 (901) 123-45-67
            formatted = f"+7 ({cleaned[1:4]}) {cleaned[4:7]}-{cleaned[7:9]}-{cleaned[9:]}"
        elif cleaned.startswith('8'):
            # 89011234567 -> +7 (901) 123-45-67
            formatted = f"+7 ({cleaned[1:4]}) {cleaned[4:7]}-{cleaned[7:9]}-{cleaned[9:]}"
        else:
            raise ValidationError('Номер телефона должен начинаться с 7, 8 или быть из 10 цифр')
    else:
        raise ValidationError('Номер телефона должен содержать 10 или 11 цифр')

    return formatted


def validate_phone_number(number):
    """Валидатор для форм"""
    if number:
        try:
            return validate_and_format_phone(number)
        except ValidationError as e:
            raise ValidationError(str(e))
    return number