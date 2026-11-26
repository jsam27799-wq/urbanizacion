# Módulo: Prepara y carga datos de demostración para probar el sistema.
import os
import shutil
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Piemonte.settings')

import django

django.setup()

from django.conf import settings
from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone

from BD.models import (
    Casa,
    CasaResidente,
    Domicilio,
    Guardia,
    Notas,
    Novedad,
    Paquete,
    Pago,
    Proceso,
    Propietario,
    Resena,
    Residente,
    Visitante,
)
from BD.views import asignar_grupo_por_rol
from core.models import PerfilUsuario


BACKUP_DIR = Path(settings.BASE_DIR) / 'backups'
BACKUP_DIR.mkdir(exist_ok=True)
STAMP = timezone.now().strftime('%Y%m%d_%H%M%S')
# Conserva una copia fechada de la base y de los archivos multimedia antes de modificar los datos de demostración.
shutil.copy2(settings.DATABASES['default']['NAME'], BACKUP_DIR / f'BD_antes_demo_{STAMP}.sqlite3')
media_dir = Path(settings.MEDIA_ROOT)
if media_dir.exists():
    shutil.copytree(media_dir, BACKUP_DIR / f'media_antes_demo_{STAMP}', dirs_exist_ok=True)

NOMBRES = [
    ('Carlos', 'Mendoza', 'carlos.mendoza@piemonte.com'),
    ('Mariana', 'Rojas', 'mariana.rojas@piemonte.com'),
    ('Andres', 'Salazar', 'andres.salazar@piemonte.com'),
    ('Valentina', 'Gomez', 'valentina.gomez@piemonte.com'),
    ('Felipe', 'Castro', 'felipe.castro@piemonte.com'),
]
CONTRASENA = 'Piemonte2026!'


# Organiza el flujo de evidencia dentro de este módulo.
def evidencia(modelo, campo, nombre, texto):
    # Guarda el contenido de ejemplo en el campo de archivo sin persistir aún el objeto relacionado.
    registro = modelo()
    getattr(registro, campo).save(nombre, ContentFile(texto.encode('utf-8')), save=False)
    return registro


with transaction.atomic():
    # Se eliminan primero las relaciones dependientes de los modulos que se limpian.
    Proceso.objects.all().delete()
    CasaResidente.objects.all().delete()
    Visitante.objects.all().delete()
    Domicilio.objects.all().delete()
    Resena.objects.all().delete()

    # Los pagos conservados protegen sus casas; esas casas se mantienen y se reutilizan.
    casas_protegidas = list(Casa.objects.filter(pagos__isnull=False).distinct())
    Casa.objects.exclude(pk__in=[casa.pk for casa in casas_protegidas]).delete()
    Guardia.objects.all().delete()
    Propietario.objects.all().delete()
    Residente.objects.all().delete()
    PerfilUsuario.objects.all().delete()
    User.objects.filter(is_superuser=False).delete()

    residentes = [Residente.objects.create(
        cedula=2100000000 + indice,
        nombre=nombre,
        apellido=apellido,
        telefono=f'31050000{indice}',
    ) for indice, (nombre, apellido, _) in enumerate(NOMBRES, start=1)]

    propietarios = [Propietario.objects.create(
        cedula=2200000000 + indice,
        nombre=nombre,
        apellido=apellido,
        telefono=f'30060000{indice}',
        correo=correo,
        rol='Propietario',
    ) for indice, (nombre, apellido, correo) in enumerate(NOMBRES, start=1)]

    # Continúa la numeración desde la casa más alta existente para no colisionar con registros preservados.
    max_numero = max(Casa.objects.values_list('numero_casa', flat=True), default=0)
    casas = [Casa.objects.create(
        # El importe de cartera aumenta en pasos fijos para probar saldos distintos en reportes y paneles.
        numero_casa=max_numero + indice,
        cantidad_personas=4 if indice < 4 else 3,
        cantidad_residentes=1,
        estado='Ocupada',
        cartera=indice * 85000,
        id_residente=residentes[indice - 1],
        id_propietario=propietarios[indice - 1],
    ) for indice in range(1, 6)]
    casas_libres = [Casa.objects.create(
        # Estas viviendas sin ocupante permiten probar formularios de asignación y filtros por estado.
        numero_casa=max_numero + 5 + indice,
        cantidad_personas=4,
        cantidad_residentes=1,
        estado='Para Arrendar',
        cartera=0,
    ) for indice in range(1, 6)]

    usuarios_guardia = []
    for indice, (nombre, apellido, correo) in enumerate(NOMBRES[:3], start=1):
        usuario = User.objects.create_user(
            username=f'guardia{indice}.piemonte',
            email=correo,
            password=CONTRASENA,
            first_name=nombre,
            last_name=apellido,
            is_active=True,
        )
        PerfilUsuario.objects.create(usuario=usuario, telefono=f'32070000{indice}')
        asignar_grupo_por_rol(usuario, 'guardia')
        Guardia.objects.create(
            cedula=2300000000 + indice,
            nombre=nombre,
            apellido=apellido,
            telefono=f'32070000{indice}',
            turno='Mañana' if indice != 2 else 'Tarde',
            usuario=usuario,
        )
        usuarios_guardia.append(usuario)

    administrador = User.objects.create_user(
        username='admin.piemonte',
        email='admin@piemonte.com',
        password=CONTRASENA,
        first_name='Administracion',
        last_name='Piemonte',
        is_staff=True,
        is_active=True,
    )
    PerfilUsuario.objects.create(usuario=administrador, telefono='3007000000')
    asignar_grupo_por_rol(administrador, 'administrador')

    usuarios_propietario = []
    for indice, (nombre, apellido, correo) in enumerate(NOMBRES, start=1):
        usuario = User.objects.create_user(
            username=f'propietario{indice}.piemonte',
            email=correo,
            password=CONTRASENA,
            first_name=nombre,
            last_name=apellido,
            is_active=True,
        )
        PerfilUsuario.objects.create(usuario=usuario, telefono=propietarios[indice - 1].telefono)
        asignar_grupo_por_rol(usuario, 'propietario')
        propietarios[indice - 1].usuario = usuario
        propietarios[indice - 1].save(update_fields=('usuario',))
        usuarios_propietario.append(usuario)

    for indice, casa in enumerate(casas, start=1):
        CasaResidente.objects.create(casa=casa, residente=residentes[(indice % 5)], rol='SECUNDARIO')

    for indice in range(1, 6):
        nombre, apellido, _ = NOMBRES[indice - 1]
        visitante = Visitante.objects.create(
            nombre=f'Visitante {nombre}',
            apellido=apellido,
            cedula=str(2400000000 + indice),
            vehiculo_trae='SI' if indice % 2 else 'NO',
            tipo_v='Familiar' if indice % 2 else 'Proveedor',
            tipo_residente='Residente',
            placa_v=f'VST{indice}1' if indice % 2 else None,
            vehiculo_tipo='Automovil' if indice % 2 else None,
            conductor=f'Visitante {nombre}' if indice % 2 else None,
            cantidad_personas=1 if indice % 2 else 2,
            residente_secundario=residentes[indice - 1],
            propietario_autorizador=propietarios[indice - 1],
            autoriza='SI',
        )
        Proceso.objects.create(
            tipo='Visitante', estado='ENTREGADO', cedula=visitante.cedula,
            nombre=f'{visitante.nombre} {visitante.apellido}', fecha=timezone.now() - timedelta(days=indice),
            id_guardia=Guardia.objects.all()[indice % 3], id_casa=casas[indice - 1], id_visitante=visitante,
            vehiculo_tiene=visitante.vehiculo_trae, vehiculo_tipo=visitante.vehiculo_tipo, placa=visitante.placa_v,
            descripcion='Visita autorizada por el residente.',
        )

        domicilio = Domicilio.objects.create(
            nombre=f'Repartidor {nombre}', apellido=apellido,
            telefono_negocio=f'31580000{indice}', descripcion_negocio='Entrega de alimentos y productos del hogar',
            vehiculo_tipo='Motocicleta', vehiculo_placa=f'DOM{indice}7', residente_secundario=residentes[indice - 1],
            propietario_autorizador=propietarios[indice - 1], autoriza='SI',
        )
        Proceso.objects.create(
            tipo='Domicilio', estado='ENTREGADO', nombre=f'{domicilio.nombre} {domicilio.apellido}', fecha=timezone.now() - timedelta(days=indice),
            id_guardia=Guardia.objects.all()[indice % 3], id_casa=casas[indice - 1], id_domicilio=domicilio,
            vehiculo_tiene='SI', vehiculo_tipo=domicilio.vehiculo_tipo, placa=domicilio.vehiculo_placa,
            descripcion=domicilio.descripcion_negocio,
        )

    guardias = list(Guardia.objects.order_by('id_guardia'))
    for indice in range(1, 6):
        paquete = Paquete.objects.filter(pk__in=list(Paquete.objects.values_list('pk', flat=True))[:5]).order_by('id_paquete')[indice - 1] if Paquete.objects.count() >= 5 else None
        if paquete is None:
            paquete = evidencia(Paquete, 'evidencia', f'demo_paquete_{indice}.txt', f'Evidencia demo del paquete {indice}.')
            paquete.nombre = f'Remitente {NOMBRES[indice - 1][0]}'
            paquete.apellido = NOMBRES[indice - 1][1]
            paquete.transportadora = 'Servientrega'
            paquete.telefono_t = f'31690000{indice}'
            paquete.desc_tipo = 'Paquete para residente'
            paquete.guia = f'GUIA-DEMO-{indice:03d}'
            paquete.residente_secundario = residentes[indice - 1]
            paquete.propietario_autorizador = propietarios[indice - 1]
            paquete.llamada = 'CONTESTO'
            paquete.informacion_adicional = 'Entrega coordinada con el residente.'
            paquete.save()
        Proceso.objects.create(
            tipo='Paquete', estado='ENTREGADO', nombre=f'{paquete.nombre} {paquete.apellido}', fecha=timezone.now() - timedelta(days=indice),
            id_guardia=guardias[(indice - 1) % len(guardias)], id_casa=casas[indice - 1], id_paquete=paquete,
            descripcion='Paquete recibido en porteria.',
        )

    for indice in range(1, 6):
        if Pago.objects.count() < 5:
            pago = evidencia(Pago, 'evidencia', f'demo_pago_{indice}.txt', f'Comprobante demo de pago {indice}.')
            pago.valor = Decimal(180000 + indice * 25000)
            pago.fecha = timezone.now().date() - timedelta(days=indice)
            pago.estado = 'Pagado'
            pago.id_casa = casas[indice - 1]
            pago.save()

    for indice in range(1, 6):
        if Notas.objects.count() < 5:
            nota = evidencia(Notas, 'evidencia', f'demo_nota_{indice}.txt', f'Evidencia demo de nota {indice}.')
            nota.nombre = 'Porteria'
            nota.apellido = f'Turno {indice}'
            nota.telefono = f'32070000{indice}'
            nota.nota = 'Se verifico el funcionamiento normal de la porteria.'
            nota.id_guardia = guardias[(indice - 1) % len(guardias)]
            nota.save()

    for indice in range(1, 6):
        if Novedad.objects.count() < 5:
            novedad = evidencia(Novedad, 'evidencia', f'demo_novedad_{indice}.txt', f'Evidencia demo de novedad {indice}.')
            novedad.titulo = f'Revision de zona comun {indice}'
            novedad.tipo = 'Mantenimiento'
            novedad.nota = 'Revision programada sin afectaciones para los residentes.'
            novedad.fecha_suceso = timezone.now() - timedelta(days=indice)
            novedad.registrado_por = administrador
            novedad.save()

    comentarios = [
        'La atencion en porteria fue clara y amable.',
        'El proceso de ingreso fue rapido y ordenado.',
        'La administracion respondio oportunamente.',
        'Las zonas comunes se mantienen en buen estado.',
        'La informacion entregada fue util y completa.',
    ]
    for indice, comentario in enumerate(comentarios, start=1):
        Resena.objects.create(
            nombre=f'Residente {indice}', comentario=comentario,
            calificacion=5 if indice != 2 else 4, aprobada=True,
            usuario=usuarios_propietario[indice - 1],
        )

print(f'Datos demo cargados. Respaldo creado en: {BACKUP_DIR / f"BD_antes_demo_{STAMP}.sqlite3"}')
print('Usuarios creados: admin.piemonte, guardia1.piemonte a guardia3.piemonte y propietario1.piemonte a propietario5.piemonte')
print(f'Contraseña de todos: {CONTRASENA}')
