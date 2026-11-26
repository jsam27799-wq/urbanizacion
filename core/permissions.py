# Módulo: Centraliza la determinación de roles y permisos para las acciones de usuario.
# Resuelve el rol reconocido del usuario, priorizando privilegios administrativos sobre grupos.
def obtener_rol_resena(user):
    if not user.is_authenticated:
        return ''
    if user.is_staff or user.is_superuser:
        return 'Administrador'
    for rol in ('Administrador', 'Guardia', 'Propietario', 'Residente'):
        if user.groups.filter(name__iexact=rol).exists():
            return rol
    return ''


# Solo permite publicar reseñas a usuarios autenticados que tengan un rol de la aplicación.
def puede_enviar_resena(user):
    return bool(obtener_rol_resena(user))