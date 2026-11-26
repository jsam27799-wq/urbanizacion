# Intención de la migración: crea el registro de bitácora para auditar eventos.
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


# Intención de la migración: crea el registro de bitácora para auditar eventos.
class Migration(migrations.Migration):

    dependencies = [
        ('BD', '0043_configuracioncartera_estados_visualizacion'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='RegistroBitacora',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('modulo', models.CharField(max_length=50)),
                ('registro', models.CharField(max_length=150)),
                ('descripcion', models.TextField(blank=True)),
                ('fecha', models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ('casa', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='registros_bitacora', to='BD.casa')),
                ('usuario', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='registros_bitacora', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Registro de bitácora',
                'verbose_name_plural': 'Registros de bitácora',
                'db_table': 'registro_bitacora',
                'ordering': ('-fecha', '-id'),
            },
        ),
    ]
