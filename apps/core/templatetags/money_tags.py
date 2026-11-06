from django import template

from apps.core.currencies import format_money


register = template.Library()


@register.simple_tag
def money(value, currency="USD"):
    return format_money(value, currency)
