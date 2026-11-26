# Intención de la migración: agrega el estado al registro de procesos.
from django.db import migrations, models


# Intención de la migración: agrega el estado al registro de procesos.
class Migration(migrations.Migration):
    dependencies = [
        ('BD', '0004_remove_casa_foto_alter_propietario_rol'),
    ]

    operations = [
        migrations.AddField(
            model_name='proceso',
            name='estado',
            field=models.CharField(choices=[('PENDIENTE', 'Pendiente'), ('ENTREGADO', 'Entregado'), ('DEMORADO', 'Demorado')], db_column='Estado', default='PENDIENTE', max_length=20),
        ),
    ]