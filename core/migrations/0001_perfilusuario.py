# Intención de la migración: crea el perfil de usuario asociado a las cuentas de autenticación.
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


# Intención de la migración: crea el perfil de usuario asociado a las cuentas de autenticación.
class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='PerfilUsuario',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('telefono', models.CharField(blank=True, max_length=20)),
                ('usuario', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='perfil_contacto', to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
