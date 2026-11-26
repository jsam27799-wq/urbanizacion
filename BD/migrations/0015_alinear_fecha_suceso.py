# Intención de la migración: alinea el campo de fecha de suceso con el modelo.
from django.db import migrations, models
import django.utils.timezone


# Intención de la migración: alinea el campo de fecha de suceso con el modelo.
class Migration(migrations.Migration):
    dependencies = [
        ('BD', '0014_novedad_fechas'),
    ]

    operations = [
        migrations.AlterField(
            model_name='novedad',
            name='fecha_suceso',
            field=models.DateTimeField(db_column='Fecha', default=django.utils.timezone.now),
        ),
    ]