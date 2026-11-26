# Intención de la migración: define un estado predeterminado para los pagos.
from django.db import migrations, models


# Intención de la migración: define un estado predeterminado para los pagos.
class Migration(migrations.Migration):

    dependencies = [
        ('BD', '0028_propietario_usuario'),
    ]

    operations = [
        migrations.AlterField(
            model_name='pago',
            name='estado',
            field=models.CharField(db_column='Estado', default='Pendiente', max_length=50),
        ),
    ]