# Intención de la migración: migra residentes sin relación principal a la estructura de relaciones vigente.
from django.db import migrations


# Organiza el flujo de conversión residentes huerfanos dentro de este módulo.
def convertir_residentes_huerfanos(apps, schema_editor):
    Propietario = apps.get_model('BD', 'Propietario')
    Residente = apps.get_model('BD', 'Residente')
    Casa = apps.get_model('BD', 'Casa')
    Visitante = apps.get_model('BD', 'Visitante')
    Domicilio = apps.get_model('BD', 'Domicilio')
    Paquete = apps.get_model('BD', 'Paquete')
    alias = schema_editor.connection.alias

    propietarios = Propietario.objects.using(alias).filter(rol__iexact='Residente', usuario__isnull=True)
    for propietario in propietarios.iterator():
        tiene_relaciones = (
            Casa.objects.using(alias).filter(id_propietario_id=propietario.pk).exists()
            or Visitante.objects.using(alias).filter(propietario_autorizador_id=propietario.pk).exists()
            or Domicilio.objects.using(alias).filter(propietario_autorizador_id=propietario.pk).exists()
            or Paquete.objects.using(alias).filter(propietario_autorizador_id=propietario.pk).exists()
        )
        if tiene_relaciones or Residente.objects.using(alias).filter(cedula=propietario.cedula).exists():
            continue
        Residente.objects.using(alias).create(
            cedula=propietario.cedula,
            nombre=propietario.nombre,
            apellido=propietario.apellido,
            telefono=propietario.telefono,
        )
        propietario.delete(using=alias)


# Intención de la migración: migra residentes sin relación principal a la estructura de relaciones vigente.
class Migration(migrations.Migration):
    dependencies = [
        ('BD', '0030_resena_rol_usuario'),
    ]

    operations = [
        migrations.RunPython(convertir_residentes_huerfanos, migrations.RunPython.noop),
    ]