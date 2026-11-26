# Intención de la migración: añade el tipo de novedad y quién la registra.
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


# Intención de la migración: añade el tipo de novedad y quién la registra.
class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('BD', '0010_visitante_tipos'),
    ]

    operations = [
        migrations.AddField(
            model_name='notas',
            name='tipo',
            field=models.CharField(db_column='Tipo', default='General', max_length=80),
        ),
        migrations.AddField(
            model_name='notas',
            name='registrado_por',
            field=models.ForeignKey(blank=True, db_column='Registrado_por', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='novedades_publicadas', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='notas',
            name='id_guardia',
            field=models.ForeignKey(blank=True, db_column='Id_guardia', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='notas', to='BD.guardia'),
        ),
    ]