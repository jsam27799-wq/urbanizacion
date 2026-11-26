# Módulo: Define y normaliza las etiquetas y colores configurables de los estados.
from django import template

from BD.estados import color_texto


register = template.Library()


# Devuelve la etiqueta y los colores legibles de un estado para las plantillas.
@register.simple_tag(takes_context=True)
def estado_ui(context, modulo, estado):
    configuraciones = context.get('estados_visualizacion', {})
    estados = configuraciones.get(modulo, {})
    datos = estados.get(str(estado))
    if not datos:
        datos = {'nombre': str(estado), 'color': '#6c757d'}
    return {
        **datos,
        'color_texto': color_texto(datos.get('color')),
    }
