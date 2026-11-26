# Intención de la migración: configura la aplicación de mora de acuerdo con fechas de vencimiento.
from django.db import migrations, models
import django.utils.timezone


# Intención de la migración: configura la aplicación de mora de acuerdo con fechas de vencimiento.
class Migration(migrations.Migration):
    dependencies = [
        ('BD', '0034_convertir_cartera_a_saldo_pendiente'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='configuracioncartera',
            name='incremento_por_minuto',
        ),
        migrations.RemoveField(
            model_name='configuracioncartera',
            name='ultima_actualizacion',
        ),
        migrations.AddField(
            model_name='configuracioncartera',
            name='porcentaje_mora',
            field=models.DecimalField(decimal_places=2, default=2, max_digits=5),
        ),
        migrations.AddField(
            model_name='configuracioncartera',
            name='dia_vencimiento',
            field=models.PositiveSmallIntegerField(default=30),
        ),
        migrations.RemoveField(
            model_name='casa',
            name='ultima_actualizacion_cartera',
        ),
        migrations.AddField(
            model_name='casa',
            name='ultima_mora_aplicada',
            field=models.DateField(db_column='Ultima_Mora_Aplicada', default=django.utils.timezone.localdate),
        ),
    ]