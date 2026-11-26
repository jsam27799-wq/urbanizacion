# Intención de la migración: amplía los estados de proceso para identificar entregas tardías.
from django.db import migrations, models


# Intención de la migración: amplía los estados de proceso para identificar entregas tardías.
class Migration(migrations.Migration):
    dependencies = [
        ('BD', '0006_proceso_tiempo_restante'),
    ]

    operations = [
        migrations.AlterField(
            model_name='proceso',
            name='estado',
            field=models.CharField(choices=[('PENDIENTE', 'Pendiente'), ('ENTREGADO', 'Entregado'), ('ENTREGADO_TARDE', 'Entregado tarde'), ('DEMORADO', 'Demorado')], db_column='Estado', default='PENDIENTE', max_length=20),
        ),
    ]
