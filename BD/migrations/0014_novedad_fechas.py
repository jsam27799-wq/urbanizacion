# Intención de la migración: añade fechas de referencia a las novedades.
from django.db import migrations, models
import django.utils.timezone


# Intención de la migración: añade fechas de referencia a las novedades.
class Migration(migrations.Migration):
    dependencies = [
        ('BD', '0013_separar_novedades'),
    ]

    operations = [
        migrations.RenameField(
            model_name='novedad',
            old_name='fecha',
            new_name='fecha_suceso',
        ),
        migrations.AddField(
            model_name='novedad',
            name='fecha_creacion',
            field=models.DateTimeField(auto_now_add=True, db_column='Fecha_Creacion', default=django.utils.timezone.now),
            preserve_default=False,
        ),
    ]
