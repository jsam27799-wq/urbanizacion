# Intención de la migración: agrega el monto fijo del aumento mensual.
from django.db import migrations, models


# Intención de la migración: agrega el monto fijo del aumento mensual.
class Migration(migrations.Migration):
    dependencies = [
        ('BD', '0037_frecuencia_mora_prueba'),
    ]

    operations = [
        migrations.AddField(
            model_name='configuracioncartera',
            name='monto_aumento_mensual',
            field=models.DecimalField(db_column='Monto_Aumento_Mensual', decimal_places=2, default=0, max_digits=16),
        ),
    ]
