# Módulo: Proporciona filtros de plantilla para presentar valores con formato.
from django import template


register = template.Library()


# Organiza el flujo de moneda dentro de este módulo.
@register.filter
def moneda(valor):
    if valor in (None, ''):
        return ''
    return f'{valor:,.0f}'.replace(',', '.')