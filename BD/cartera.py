# Módulo: Calcula vencimientos, mora y saldos pendientes asociados a las casas.
from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .models import Casa, ConfiguracionCartera


# Calcula el interés sobre la deuda acumulada neta antes de sumar la administración del nuevo período.
def _aplicar_cargo_periodico(casa, configuracion):
    saldo_anterior = max(casa.cartera, 0) + max(casa.saldo_mora, 0) - max(casa.saldo_favor, 0)
    if saldo_anterior > 0:
        mora_nueva = (saldo_anterior * configuracion.porcentaje_mora / Decimal('100')).quantize(
            Decimal('0.01'),
            rounding=ROUND_HALF_UP,
        )
        casa.saldo_mora += mora_nueva
    else:
        mora_nueva = Decimal('0.00')

    administracion_nueva = configuracion.monto_aumento_mensual.quantize(
        Decimal('0.01'),
        rounding=ROUND_HALF_UP,
    )
    casa.cartera += administracion_nueva
    return mora_nueva > 0 or administracion_nueva > 0


# Limita el día de vencimiento al último día disponible en el mes indicado.
def _fecha_vencimiento(year, month, dia_vencimiento):
    ultimo_dia = monthrange(year, month)[1]
    # Si el día configurado no existe en ese mes, se usa su último día válido.
    return date(year, month, min(dia_vencimiento, ultimo_dia))


# Avanza un mes y normaliza el cambio de año antes de calcular el nuevo vencimiento.
def _siguiente_vencimiento(fecha, dia_vencimiento):
    year, month = fecha.year, fecha.month + 1
    if month == 13:
        year += 1
        month = 1
    return _fecha_vencimiento(year, month, dia_vencimiento)


# Aplica los cargos vencidos dentro de una transacción y bloquea las filas para evitar dobles cálculos concurrentes.
def aplicar_mora_vencida(hoy=None, ahora=None):
    ahora = ahora or timezone.now()
    hoy = hoy or timezone.localdate(ahora)
    with transaction.atomic():
        configuracion, _ = ConfiguracionCartera.objects.select_for_update().get_or_create(
            pk=1,
            defaults={'porcentaje_mora': Decimal('2.00'), 'dia_vencimiento': 30},
        )
        vencimiento_actual = _fecha_vencimiento(hoy.year, hoy.month, configuracion.dia_vencimiento)
        if hoy <= vencimiento_actual:
            year, month = hoy.year, hoy.month - 1
            if month == 0:
                year -= 1
                month = 12
            vencimiento_maximo = _fecha_vencimiento(year, month, configuracion.dia_vencimiento)
        else:
            vencimiento_maximo = vencimiento_actual

        casas = Casa.objects.select_for_update().order_by('pk')
        if configuracion.frecuencia_mora == 'minuto':
            casas = casas.filter(
                Q(pagos__isnull=False) | Q(cartera__gt=0) | Q(saldo_mora__gt=0),
            ).distinct()
        else:
            casas = casas.filter(pagos__isnull=False).distinct()
        casas_actualizadas = 0
        for casa in casas:
            if configuracion.frecuencia_mora == 'minuto':
                # En modo de prueba, calcula cuántos intervalos completos han pasado desde la última ejecución.
                minutos = int((ahora - casa.ultima_mora_calculada).total_seconds() // 60)
                if minutos <= 0:
                    continue
                for _ in range(minutos):
                    if _aplicar_cargo_periodico(casa, configuracion):
                        casas_actualizadas += 1
                casa.ultima_mora_calculada += timedelta(minutes=minutos)
                casa.save(update_fields=('cartera', 'saldo_mora', 'ultima_mora_calculada'))
                continue

            if casa.ultima_mora_aplicada is None:
                casa.ultima_mora_aplicada = vencimiento_maximo
                casa.save(update_fields=('ultima_mora_aplicada',))
                continue
            vencimiento = _siguiente_vencimiento(casa.ultima_mora_aplicada, configuracion.dia_vencimiento)
            while vencimiento < hoy and vencimiento <= vencimiento_maximo:
                if _aplicar_cargo_periodico(casa, configuracion):
                    casas_actualizadas += 1
                casa.ultima_mora_aplicada = vencimiento
                vencimiento = _siguiente_vencimiento(vencimiento, configuracion.dia_vencimiento)
            casa.save(update_fields=('cartera', 'saldo_mora', 'ultima_mora_aplicada'))
    return casas_actualizadas


# Calcula para cada casa la deuda positiva agregando cartera y mora acumulada.
def saldos_actuales_por_casa(casas):
    return {
        casa.pk: max(
            max(casa.cartera, 0) + max(casa.saldo_mora, 0) - max(casa.saldo_favor, 0),
            0,
        )
        for casa in casas
    }