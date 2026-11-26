# Intención de la migración: incorpora información del vehículo del visitante.
from django.db import migrations, models


# Intención de la migración: incorpora información del vehículo del visitante.
class Migration(migrations.Migration):
    dependencies = [
        ('BD', '0008_notas_fecha'),
    ]

    operations = [
        migrations.AddField(
            model_name='visitante',
            name='conductor',
            field=models.CharField(blank=True, db_column='Conductor', max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='visitante',
            name='cantidad_personas',
            field=models.PositiveIntegerField(db_column='Cantidad_Personas', default=1),
        ),
    ]