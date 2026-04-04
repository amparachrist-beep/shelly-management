# apps/dashboard/templatetags/math_filters.py
from django import template

register = template.Library()

@register.filter
def mul(value, arg):
    """Multiplier value par arg"""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def div(value, arg):
    """Diviser value par arg"""
    try:
        return float(value) / float(arg) if float(arg) != 0 else 0
    except (ValueError, TypeError):
        return 0

@register.filter
def sub(value, arg):
    """Soustraire arg à value"""
    try:
        return float(value) - float(arg)
    except (ValueError, TypeError):
        return 0
