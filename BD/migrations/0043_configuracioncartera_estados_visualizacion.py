# Intención de la migración: agrega la configuración de etiquetas y colores visuales de estados.
from django.db import migrations, models


# Intención de la migración: agrega la configuración de etiquetas y colores visuales de estados.
class Migration(migrations.Migration):

    dependencies = [
        ('BD', '0042_alter_copiaseguridad_sha256'),
    ]

    operations = [
        migrations.AddField(
            model_name='configuracioncartera',
            name='estados_visualizacion',
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
