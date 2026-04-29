from django import template

register = template.Library()

@register.filter
def multiply(value, arg):
    """Умножает value на arg"""
    try:
        return int(value) * int(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def div(value, arg):
    """Делит value на arg"""
    try:
        if int(arg) == 0:
            return 0
        return float(value) / float(arg)
    except (ValueError, TypeError, ZeroDivisionError):
        return 0

@register.filter
def mul(value, arg):
    """Умножает value на arg (синоним для multiply)"""
    return multiply(value, arg)