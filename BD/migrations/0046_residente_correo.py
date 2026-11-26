from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('BD', '0045_registrobitacora_accion'),
    ]

    operations = [
        migrations.AddField(
            model_name='residente',
            name='correo',
            field=models.EmailField(blank=True, db_column='Correo', max_length=100, null=True),
        ),
    ]
