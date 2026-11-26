# Intención de la migración: crea y asigna los grupos y permisos iniciales según roles.
from django.db import migrations


MODELOS_BD = (
    'propietario',
    'residente',
    'casa',
    'guardia',
    'domicilio',
    'visitante',
    'paquete',
    'proceso',
    'pago',
    'notas',
    'novedad',
    'resena',
)

MODELOS_OPERATIVOS_GUARDIA = (
    'visitante',
    'domicilio',
    'paquete',
    'notas',
)

MODELOS_SOLO_LECTURA_GUARDIA = (
    'propietario',
    'residente',
    'casa',
    'guardia',
    'proceso',
    'pago',
    'novedad',
    'resena',
)


# Organiza el flujo de configurar grupos permisos dentro de este módulo.
def configurar_grupos_permisos(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Permission = apps.get_model('auth', 'Permission')
    User = apps.get_model('auth', 'User')
    Guardia = apps.get_model('BD', 'Guardia')

    permisos_bd = Permission.objects.filter(content_type__app_label='BD')
    grupo_administrador, _ = Group.objects.get_or_create(name='Administrador')
    grupo_administrador.permissions.set(permisos_bd)

    permisos_guardia = Permission.objects.filter(
        content_type__app_label='BD',
        content_type__model__in=MODELOS_OPERATIVOS_GUARDIA + MODELOS_SOLO_LECTURA_GUARDIA,
        codename__in=(
            'view_propietario',
            'view_residente',
            'view_casa',
            'view_guardia',
            'view_proceso',
            'view_pago',
            'view_novedad',
            'view_resena',
            'view_visitante',
            'add_visitante',
            'change_visitante',
            'view_domicilio',
            'add_domicilio',
            'change_domicilio',
            'view_paquete',
            'add_paquete',
            'change_paquete',
            'view_notas',
            'add_notas',
            'change_notas',
        ),
    )
    grupo_guardia, _ = Group.objects.get_or_create(name='Guardia')
    grupo_guardia.permissions.set(permisos_guardia)

    for usuario in User.objects.filter(is_staff=True):
        usuario.groups.add(grupo_administrador)

    for guardia in Guardia.objects.exclude(usuario=None):
        guardia.usuario.groups.add(grupo_guardia)


# Organiza el flujo de quitar grupos permisos dentro de este módulo.
def quitar_grupos_permisos(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Group.objects.filter(name__in=('Administrador', 'Guardia')).delete()


# Intención de la migración: crea y asigna los grupos y permisos iniciales según roles.
class Migration(migrations.Migration):
    dependencies = (
        ('BD', '0025_alter_casa_cartera'),
    )

    operations = (
        migrations.RunPython(configurar_grupos_permisos, quitar_grupos_permisos),
    )
