# Intención de la migración: crea la entidad para reseñas.
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


# Intención de la migración: crea la entidad para reseñas.
class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('BD', '0015_alinear_fecha_suceso'),
    ]

    operations = [
        migrations.CreateModel(
            name='Resena',
            fields=[
                ('id_resena', models.AutoField(db_column='Id_resena', primary_key=True, serialize=False)),
                ('nombre', models.CharField(db_column='Nombre', max_length=100)),
                ('comentario', models.TextField(db_column='Comentario', max_length=500)),
                ('calificacion', models.PositiveSmallIntegerField(choices=[(1, '1 estrella'), (2, '2 estrellas'), (3, '3 estrellas'), (4, '4 estrellas'), (5, '5 estrellas')], db_column='Calificacion')),
                ('fecha_creacion', models.DateTimeField(auto_now_add=True, db_column='Fecha_Creacion')),
                ('aprobada', models.BooleanField(db_column='Aprobada', default=False)),
                ('usuario', models.ForeignKey(blank=True, db_column='Usuario', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='resenas', to=settings.AUTH_USER_MODEL)),
            ],
            options={'db_table': 'resena', 'ordering': ('-fecha_creacion', 'id_resena'), 'verbose_name': 'Reseña', 'verbose_name_plural': 'Reseñas'},
        ),
    ]