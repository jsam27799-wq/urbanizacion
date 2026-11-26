# Módulo: Proporciona el registro común de eventos de auditoría.
from .models import RegistroBitacora


# Registra los datos del evento y sus referencias para mantener una única vía de escritura de auditoría.
def registrar_evento_bitacora(*, modulo, registro, accion='Registro', descripcion='', usuario=None, casa=None):
    return RegistroBitacora.objects.create(
        modulo=modulo,
        accion=accion,
        registro=registro,
        descripcion=descripcion,
        usuario=usuario,
        casa=casa,
    )
