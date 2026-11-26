# Módulo: Define y normaliza las etiquetas y colores configurables de los estados.
import re


ESTADOS_CONFIGURABLES = {
    'domicilio': {
        'label': 'Domiciliarios',
        'estados': (
            ('PENDIENTE', 'Ingresado', '#198754'),
            ('DEMORADO', 'Demorado', '#dc3545'),
            ('ENTREGADO', 'Salió a tiempo', '#198754'),
            ('ENTREGADO_TARDE', 'Salió tarde', '#dc3545'),
        ),
    },
    'visitante': {
        'label': 'Visitantes',
        'estados': (
            ('PENDIENTE', 'Ingresado', '#0d6efd'),
            ('SALIDO', 'Salido', '#6c757d'),
        ),
    },
    'paquete': {
        'label': 'Paquetes',
        'estados': (
            ('PENDIENTE', 'En portería', '#6c757d'),
            ('ENTREGADO', 'Entregado', '#198754'),
            ('DEVUELTO', 'Devuelto', '#dc3545'),
        ),
    },
    'pago': {
        'label': 'Pagos',
        'estados': (
            ('Pagado', 'Pagado', '#198754'),
            ('Pendiente', 'Pendiente', '#ffc107'),
            ('Al día', 'Al día', '#198754'),
        ),
    },
    'nota': {
        'label': 'Notas',
        'estados': (
            ('Registrada', 'Registrada', '#6c757d'),
        ),
    },
    'casa': {
        'label': 'Casas',
        'estados': (
            ('Para Arrendar', 'Para Arrendar', '#0d6efd'),
            ('Ocupada', 'Ocupada', '#198754'),
            ('Deshabilitada', 'Deshabilitada', '#6c757d'),
            ('Otros', 'Otros', '#6c757d'),
        ),
    },
}

ESTADOS_POR_DEFECTO = {
    modulo: {
        estado: {'nombre': nombre, 'color': color}
        for estado, nombre, color in definicion['estados']
    }
    for modulo, definicion in ESTADOS_CONFIGURABLES.items()
}

_COLOR_HEX = re.compile(r'^#[0-9a-fA-F]{6}$')


# Realiza la tarea de normalizar estados y entrega el resultado al flujo que la invoca.
def normalizar_estados(configurados):
    # Parte de los valores predeterminados para que una configuración parcial no oculte estados conocidos.
    normalizados = {
        modulo: {estado: datos.copy() for estado, datos in estados.items()}
        for modulo, estados in ESTADOS_POR_DEFECTO.items()
    }
    if not isinstance(configurados, dict):
        return normalizados

    for modulo, estados in configurados.items():
        if not isinstance(estados, dict):
            continue
        normalizados.setdefault(modulo, {})
        for estado, datos in estados.items():
            if not isinstance(datos, dict):
                continue
            anterior = normalizados[modulo].get(estado, {
                'nombre': estado,
                'color': '#6c757d',
            })
            color = datos.get('color', anterior['color'])
            # Si el color no es un hexadecimal de seis dígitos, conserva el color anterior seguro.
            if not isinstance(color, str) or not _COLOR_HEX.fullmatch(color):
                color = anterior['color']
            nombre = datos.get('nombre', anterior['nombre'])
            normalizados[modulo][estado] = {
                'nombre': nombre if isinstance(nombre, str) and nombre.strip() else anterior['nombre'],
                'color': color.lower(),
            }
    return normalizados


# Realiza la tarea de color texto y entrega el resultado al flujo que la invoca.
def color_texto(color):
    if not isinstance(color, str) or not _COLOR_HEX.fullmatch(color):
        color = '#6c757d'
    rojo, verde, azul = (int(color[indice:indice + 2], 16) for indice in (1, 3, 5))
    # La luminancia pondera los canales RGB para elegir texto oscuro en fondos claros y blanco en fondos oscuros.
    luminancia = (0.299 * rojo + 0.587 * verde + 0.114 * azul)
    return '#212529' if luminancia > 150 else '#ffffff'
