from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('BD', '0046_residente_correo'),
    ]

    operations = [
        migrations.AddField(
            model_name='proceso',
            name='fecha_salida',
            field=models.DateTimeField(blank=True, db_column='Fecha_Salida', null=True),
        ),
    ]
