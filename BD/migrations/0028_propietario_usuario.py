# Intención de la migración: relaciona propietarios con cuentas de usuario.
from django.db import migrations, models
import django.db.models.deletion


# Intención de la migración: relaciona propietarios con cuentas de usuario.
class Migration(migrations.Migration):
    dependencies = (
        ('BD', '0027_sincronizar_grupos_permisos'),
    )

    operations = (
        migrations.AddField(
            model_name='propietario',
            name='usuario',
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='propietario',
                to='auth.user',
            ),
        ),
    )
