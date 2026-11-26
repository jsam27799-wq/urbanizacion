# Módulo: Inyecta datos de configuración compartidos en el contexto de las plantillas.
from .estados import normalizar_estados
from .models import ConfiguracionCartera


# Añade al contexto global las etiquetas y colores de estado que usan las plantillas.
def estados_modulos(request):
    # Lee la personalización persistida y normaliza valores faltantes o inválidos antes de compartirlos con las plantillas.
    configurados = ConfiguracionCartera.objects.filter(pk=1).values_list(
        'estados_visualizacion', flat=True,
    ).first()
    return {'estados_visualizacion': normalizar_estados(configurados)}
