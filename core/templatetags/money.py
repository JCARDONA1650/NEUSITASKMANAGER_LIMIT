from django import template

register = template.Library()

@register.filter
def cop(value):
    """
    Formatea a COP: $ 2.000.000
    """
    try:
        n = float(value or 0)
    except (TypeError, ValueError):
        return "$ 0"
    s = f"{n:,.0f}"           # 2,000,000
    s = s.replace(",", ".")   # 2.000.000
    return f"$ {s}"
