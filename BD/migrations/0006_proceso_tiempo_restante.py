# Intención de la migración: añade el tiempo restante al proceso.
from django.db import migrations, models


# Intención de la migración: añade el tiempo restante al proceso.
class Migration(migrations.Migration):
    dependencies = [
        ('BD', '0005_proceso_estado'),
    ]

    operations = [
        migrations.AddField(
            model_name='proceso',
            name='tiempo_restante',
            field=models.PositiveIntegerField(db_column='Tiempo_Restante', default=60),
        ),
    ]