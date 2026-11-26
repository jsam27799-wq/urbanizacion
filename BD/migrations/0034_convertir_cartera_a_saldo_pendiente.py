# Intención de la migración: convierte los valores históricos de cartera al saldo pendiente.
from django.db import migrations
from django.db.models import Sum


# Organiza el flujo de conversión carteras a saldo pendiente dentro de este módulo.
def convertir_carteras_a_saldo_pendiente(apps, schema_editor):
    Casa = apps.get_model('BD', 'Casa')
    Pago = apps.get_model('BD', 'Pago')
    alias = schema_editor.connection.alias

    for casa in Casa.objects.using(alias).filter(id_propietario__isnull=False).iterator():
        pagos_confirmados = Pago.objects.using(alias).filter(
            id_casa_id=casa.pk,
            estado='Pagado',
        ).aggregate(total=Sum('valor'))['total'] or 0
        saldo_actual = max(casa.cartera - pagos_confirmados, 0)
        Casa.objects.using(alias).filter(pk=casa.pk).update(cartera=saldo_actual)


# Intención de la migración: convierte los valores históricos de cartera al saldo pendiente.
class Migration(migrations.Migration):
    dependencies = [
        ('BD', '0033_casa_ultima_actualizacion_cartera'),
    ]

    operations = [
        migrations.RunPython(convertir_carteras_a_saldo_pendiente, migrations.RunPython.noop),
    ]