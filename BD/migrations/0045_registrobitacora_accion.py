# Intención de la migración: añade el tipo de acción a los eventos de bitácora.
from django.db import migrations, models


# Intención de la migración: añade el tipo de acción a los eventos de bitácora.
class Migration(migrations.Migration):

    dependencies = [
        ('BD', '0044_registrobitacora'),
    ]

    operations = [
        migrations.AddField(
            model_name='registrobitacora',
            name='accion',
            field=models.CharField(default='Registro', max_length=30),
        ),
    ]
