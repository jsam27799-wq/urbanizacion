# Intención de la migración: agrega la configuración del incremento de cartera.
from django.db import migrations, models
from django.utils import timezone


# Crea creación configuración inicial y coordina los datos relacionados.
def crear_configuracion_inicial(apps, schema_editor):
    ConfiguracionCartera = apps.get_model('BD', 'ConfiguracionCartera')
    ConfiguracionCartera.objects.using(schema_editor.connection.alias).get_or_create(
        pk=1,
        defaults={
            'incremento_por_minuto': 200000,
            'ultima_actualizacion': timezone.now(),
        },
    )


# Intención de la migración: agrega la configuración del incremento de cartera.
class Migration(migrations.Migration):
    dependencies = [
        ('BD', '0031_convertir_residentes_huerfanos'),
    ]

    operations = [
        migrations.AlterField(
            model_name='casa',
            name='cartera',
            field=models.DecimalField(db_column='Cartera', decimal_places=2, default=0, max_digits=16),
        ),
        migrations.CreateModel(
            name='ConfiguracionCartera',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('incremento_por_minuto', models.DecimalField(decimal_places=2, default=200000, max_digits=15)),
                ('ultima_actualizacion', models.DateTimeField(default=timezone.now)),
            ],
            options={
                'db_table': 'configuracion_cartera',
                'verbose_name': 'Configuración de cartera',
                'verbose_name_plural': 'Configuración de cartera',
            },
        ),
        migrations.RunPython(crear_configuracion_inicial, migrations.RunPython.noop),
    ]