# Intención de la migración: asocia las reseñas con el rol de quien las publica.
from django.db import migrations, models


# Organiza el flujo de completar roles reseñas dentro de este módulo.
def completar_roles_resenas(apps, schema_editor):
    Resena = apps.get_model('BD', 'Resena')
    alias = schema_editor.connection.alias
    roles = ('Administrador', 'Guardia', 'Propietario', 'Residente')

    for resena in Resena.objects.using(alias).select_related('usuario').iterator():
        usuario = resena.usuario
        if usuario is None:
            continue
        if usuario.is_staff or usuario.is_superuser:
            rol = 'Administrador'
        else:
            grupos = {nombre.casefold() for nombre in usuario.groups.using(alias).values_list('name', flat=True)}
            rol = next((nombre for nombre in roles if nombre.casefold() in grupos), '')
        if rol:
            Resena.objects.using(alias).filter(pk=resena.pk).update(rol_usuario=rol)


# Intención de la migración: asocia las reseñas con el rol de quien las publica.
class Migration(migrations.Migration):
    dependencies = [
        ('BD', '0029_pago_estado_default'),
    ]

    operations = [
        migrations.AddField(
            model_name='resena',
            name='rol_usuario',
            field=models.CharField(blank=True, db_column='Rol_Usuario', default='', max_length=20),
        ),
        migrations.RunPython(completar_roles_resenas, migrations.RunPython.noop),
    ]