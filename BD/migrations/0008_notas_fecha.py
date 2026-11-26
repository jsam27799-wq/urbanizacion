# Intención de la migración: añade la fecha a las notas.
from django.db import migrations, models
import django.utils.timezone


# Intención de la migración: añade la fecha a las notas.
class Migration(migrations.Migration):
    dependencies = [
        ('BD', '0007_proceso_estado_entregado_tarde'),
    ]

    operations = [
        migrations.AddField(
            model_name='notas',
            name='fecha',
            field=models.DateTimeField(db_column='Fecha', default=django.utils.timezone.now),
        ),
    ]