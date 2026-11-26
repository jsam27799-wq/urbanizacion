# Intención de la migración: incorpora la frecuencia de mora usada para pruebas.
from django.db import migrations, models
import django.utils.timezone


# Intención de la migración: incorpora la frecuencia de mora usada para pruebas.
class Migration(migrations.Migration):
    dependencies = [
        ('BD', '0036_separar_saldo_mora'),
    ]

    operations = [
        migrations.AddField(
            model_name='configuracioncartera',
            name='frecuencia_mora',
            field=models.CharField(
                choices=[
                    ('mensual', 'Una vez al mes después del vencimiento'),
                    ('minuto', 'Modo de prueba: cada minuto'),
                ],
                default='mensual',
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name='casa',
            name='ultima_mora_calculada',
            field=models.DateTimeField(db_column='Ultima_Mora_Calculada', default=django.utils.timezone.now),
        ),
    ]