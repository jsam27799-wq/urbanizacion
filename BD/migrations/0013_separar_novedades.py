# Intención de la migración: separa las novedades de los registros anteriores y migra su información.
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


# Organiza el flujo de copiar novedades administrativas dentro de este módulo.
def copiar_novedades_administrativas(apps, schema_editor):
    Notas = apps.get_model('BD', 'Notas')
    Novedad = apps.get_model('BD', 'Novedad')
    for nota in Notas.objects.exclude(registrado_por_id=None).iterator():
        Novedad.objects.create(
            titulo=nota.titulo,
            tipo=nota.tipo,
            nota=nota.nota,
            evidencia=nota.evidencia.name if nota.evidencia else None,
            fecha=nota.fecha,
            registrado_por_id=nota.registrado_por_id,
        )


# Intención de la migración: separa las novedades de los registros anteriores y migra su información.
class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('BD', '0012_notas_titulo'),
    ]

    operations = [
        migrations.CreateModel(
            name='Novedad',
            fields=[
                ('id_novedad', models.AutoField(db_column='Id_novedad', primary_key=True, serialize=False)),
                ('titulo', models.CharField(db_column='Titulo', max_length=120)),
                ('tipo', models.CharField(db_column='Tipo', default='General', max_length=80)),
                ('nota', models.CharField(db_column='Nota', max_length=200)),
                ('evidencia', models.FileField(blank=True, db_column='Evidencia', max_length=255, null=True, upload_to='evidencias_novedades/')),
                ('fecha', models.DateTimeField(db_column='Fecha', default=django.utils.timezone.now)),
                ('registrado_por', models.ForeignKey(blank=True, db_column='Registrado_por', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='novedades_publicadas', to=settings.AUTH_USER_MODEL)),
            ],
            options={'db_table': 'novedad', 'ordering': ('fecha', 'id_novedad'), 'verbose_name': 'Novedad', 'verbose_name_plural': 'Novedades'},
        ),
        migrations.RunPython(copiar_novedades_administrativas, migrations.RunPython.noop),
        migrations.RemoveField(model_name='notas', name='titulo'),
        migrations.RemoveField(model_name='notas', name='tipo'),
        migrations.RemoveField(model_name='notas', name='registrado_por'),
    ]