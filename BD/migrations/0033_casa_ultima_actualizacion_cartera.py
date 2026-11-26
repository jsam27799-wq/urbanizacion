# Intención de la migración: registra cuándo se actualizó por última vez la cartera de cada casa.
from django.db import migrations, models
import django.utils.timezone


# Intención de la migración: registra cuándo se actualizó por última vez la cartera de cada casa.
class Migration(migrations.Migration):
    dependencies = [
        ('BD', '0032_configuracion_incremento_cartera'),
    ]

    operations = [
        migrations.AddField(
            model_name='casa',
            name='ultima_actualizacion_cartera',
            field=models.DateTimeField(db_column='Ultima_Actualizacion_Cartera', default=django.utils.timezone.now),
        ),
    ]