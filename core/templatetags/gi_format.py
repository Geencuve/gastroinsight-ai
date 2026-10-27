from django import template

register = template.Library()


@register.filter
def clp(value):
    """Formatea un monto en pesos chilenos: 162281 -> $162.281"""
    try:
        return "$" + f"{int(round(float(value or 0))):,}".replace(",", ".")
    except (TypeError, ValueError):
        return "$0"
