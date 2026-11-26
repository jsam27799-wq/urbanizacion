# Intención de la migración: separa el saldo de mora del saldo de cartera.
from django.db import migrations, models


# Intención de la migración: separa el saldo de mora del saldo de cartera.
class Migration(migrations.Migration):
    dependencies = [
        ('BD', '0035_configurar_mora_por_vencimiento'),
    ]

    operations = [
        migrations.AddField(
            model_name='casa',
            name='saldo_mora',
            field=models.DecimalField(db_column='Saldo_Mora', decimal_places=2, default=0, max_digits=16),
        ),
        migrations.AddField(
            model_name='pago',
            name='valor_mora_aplicada',
            field=models.DecimalField(db_column='Valor_Mora_Aplicada', decimal_places=2, default=0, max_digits=12),
        ),
        migrations.AddField(
            model_name='pago',
            name='valor_cartera_aplicada',
            field=models.DecimalField(db_column='Valor_Cartera_Aplicada', decimal_places=2, default=0, max_digits=12),
        ),
    ]