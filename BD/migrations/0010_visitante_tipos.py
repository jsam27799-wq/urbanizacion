# Intención de la migración: define los tipos de visitante.
from django.db import migrations, models


# Intención de la migración: define los tipos de visitante.
class Migration(migrations.Migration):
    dependencies = [
        ('BD', '0009_visitante_datos_vehiculo'),
    ]

    operations = [
        migrations.AddField(
            model_name='visitante',
            name='tipo_residente',
            field=models.CharField(blank=True, db_column='Tipo_Residente', max_length=50, null=True),
        ),
        migrations.AddField(
            model_name='visitante',
            name='vehiculo_tipo',
            field=models.CharField(blank=True, db_column='Vehiculo_Tipo', max_length=50, null=True),
        ),
    ]