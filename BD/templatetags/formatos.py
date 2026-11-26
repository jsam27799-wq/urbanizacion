# Módulo: Proporciona filtros de plantilla para presentar valores con formato.
from django import template


register = template.Library()


# Presenta una cantidad como pesos enteros, con puntos para separar miles.
@register.filter
def moneda(valor):
    if valor in (None, ''):
        return ''
    return f'{valor:,.0f}'.replace(',', '.')
