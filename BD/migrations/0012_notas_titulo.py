# Intención de la migración: agrega un título a las notas.
from django.db import migrations, models


# Intención de la migración: agrega un título a las notas.
class Migration(migrations.Migration):
    dependencies = [
        ('BD', '0011_novedad_tipo_registrado_por'),
    ]

    operations = [
        migrations.AddField(
            model_name='notas',
            name='titulo',
            field=models.CharField(db_column='Titulo', default='Novedad de Piemonte', max_length=120),
        ),
    ]