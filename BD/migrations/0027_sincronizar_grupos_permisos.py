# Intención de la migración: sincroniza los permisos de los grupos de usuarios.
from django.db import migrations


PERMISOS_GUARDIA = (
    'view_propietario', 'view_residente', 'view_casa', 'view_guardia',
    'view_proceso', 'view_pago', 'view_novedad', 'view_resena',
    'view_visitante', 'add_visitante', 'change_visitante',
    'view_domicilio', 'add_domicilio', 'change_domicilio',
    'view_paquete', 'add_paquete', 'change_paquete',
    'view_notas', 'add_notas', 'change_notas',
)


# Organiza el flujo de sincronizar grupos dentro de este módulo.
def sincronizar_grupos(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Permission = apps.get_model('auth', 'Permission')
    User = apps.get_model('auth', 'User')

    administrador, _ = Group.objects.get_or_create(name='Administrador')
    administrador.permissions.set(Permission.objects.all())

    guardia, _ = Group.objects.get_or_create(name='Guardia')
    guardia.permissions.set(Permission.objects.filter(
        content_type__app_label='BD',
        codename__in=PERMISOS_GUARDIA,
    ))

    for usuario in User.objects.filter(is_staff=True):
        usuario.groups.add(administrador)


# Organiza el flujo de revertir sincronizacion dentro de este módulo.
def revertir_sincronizacion(apps, schema_editor):
    pass


# Intención de la migración: sincroniza los permisos de los grupos de usuarios.
class Migration(migrations.Migration):
    dependencies = (
        ('BD', '0026_configurar_grupos_permisos'),
    )

    operations = (
        migrations.RunPython(sincronizar_grupos, revertir_sincronizacion),
    )