# Módulo: Coordina las solicitudes, reglas de negocio y respuestas de las pantallas de la aplicación.
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.db import DatabaseError, transaction
from django.http import FileResponse, Http404, HttpResponseForbidden, JsonResponse
from django.contrib.auth.models import Group, Permission, User
from django.contrib.auth import update_session_auth_hash
from django.conf import settings
from django.db.models import Prefetch, Q, Sum
from django.utils import timezone
from datetime import datetime, timedelta
from math import ceil
from pathlib import Path

from .forms import AdminResetPasswordForm, CasaEdicionForm, CasaForm, ConfiguracionCarteraForm, ConfiguracionCopiasSeguridadForm, DomicilioForm, DomicilioIngresoForm, GuardiaEdicionForm, GuardiaForm, NotaForm, NovedadForm, PagoForm, PaqueteForm, PaqueteIngresoForm, PropietarioForm, ResenaForm, ResidenteDirectorioForm, ResidenteForm, ResidenteSecundarioFormSet, UsuarioForm, VisitanteEstadoForm, VisitanteForm, VisitanteIngresoForm
from .auditoria import registrar_evento_bitacora
from .models import Casa, CasaResidente, ConfiguracionCartera, ConfiguracionCopiasSeguridad, CopiaSeguridad, Domicilio, Guardia, Notas, Novedad, Paquete, Pago, Proceso, Propietario, Resena, Residente, Visitante
from .reportes import DATE_FILTER_REPORTS, HOUSE_FILTER_REPORTS, REPORT_OPTIONS, build_payment_summary, build_report_rows, generate_payment_receipt_pdf, generate_payments_excel, generate_report_pdf
from .cartera import aplicar_mora_vencida, saldos_actuales_por_casa
from .copias_seguridad import CopiaInformacionIdentica, crear_copia_seguridad, directorio_copias, intervalo_configurado, restaurar_copia_informacion, ruta_archivo_copia, subir_copia_proyecto
from core.models import PerfilUsuario
from core.permissions import obtener_rol_resena, puede_enviar_resena
import logging
import os
import sqlite3
from django.views.decorators.http import require_GET


logger = logging.getLogger(__name__)


def redirectar_a_registros(nombre_url):
	return redirect(f'{reverse(nombre_url)}?registros=1')


def _residentes_con_otras_casas(residentes, casa_actual=None):
	residentes_por_id = {residente.pk: residente for residente in residentes}
	if not residentes_por_id:
		return []

	casas_por_residente = {residente_id: set() for residente_id in residentes_por_id}
	casas_principales = Casa.objects.filter(id_residente_id__in=residentes_por_id)
	asignaciones_secundarias = CasaResidente.objects.filter(residente_id__in=residentes_por_id)
	if casa_actual:
		casas_principales = casas_principales.exclude(pk=casa_actual.pk)
		asignaciones_secundarias = asignaciones_secundarias.exclude(casa_id=casa_actual.pk)

	for residente_id, numero_casa in casas_principales.values_list('id_residente_id', 'numero_casa'):
		casas_por_residente[residente_id].add(numero_casa)
	for residente_id, numero_casa in asignaciones_secundarias.values_list('residente_id', 'casa__numero_casa'):
		casas_por_residente[residente_id].add(numero_casa)

	return [
		{'residente': residentes_por_id[residente_id], 'casas': sorted(numeros)}
		for residente_id, numeros in casas_por_residente.items()
		if numeros
	]


def _obtener_residente_secundario(item):
	residente = item.get('residente_existente')
	if residente:
		return residente
	return Residente.objects.create(
		cedula=item['cedula'],
		nombre=item['nombre'],
		apellido=item['apellido'],
		telefono=item.get('telefono'),
	)


def _asociar_residente_secundario(casa, item, usuario):
	residente = _obtener_residente_secundario(item)
	_, creada = CasaResidente.objects.get_or_create(
		casa=casa,
		residente=residente,
		defaults={'rol': 'SECUNDARIO'},
	)
	if creada:
		registrar_evento_bitacora(
			modulo='Residente',
			registro=f'{residente.nombre} {residente.apellido}',
			descripcion=f'Residente asociado a Casa {casa.numero_casa}.',
			usuario=usuario,
			casa=casa,
		)
	return residente


# Determina si se cumple la condición es administrador.
def es_administrador(user):
	return user.is_authenticated and (
		user.is_staff
		or user.is_superuser
		or user.groups.filter(name__iexact='Administrador').exists()
	)


# Determina si se cumple la condición es guardia.
def es_guardia(user):
	return user.is_authenticated and user.groups.filter(name__iexact='Guardia').exists()


# Determina si se cumple la condición es propietario.
def es_propietario(user):
	return user.is_authenticated and user.groups.filter(name__iexact='Propietario').exists()


# Obtiene el perfil de guardia asociado con la cuenta autenticada, si existe.
def guardia_del_usuario(user):
	return Guardia.objects.filter(usuario=user).first()


PERMISOS_GUARDIA = (
	'view_propietario', 'view_residente', 'view_casa', 'view_guardia',
	'view_proceso', 'view_pago', 'view_novedad', 'view_resena',
	'view_visitante', 'add_visitante', 'change_visitante',
	'view_domicilio', 'add_domicilio', 'change_domicilio',
	'view_paquete', 'add_paquete', 'change_paquete',
	'view_notas', 'add_notas', 'change_notas',
)

PERMISOS_PROPIETARIO = ('view_pago', 'add_pago')


# Crea o reutiliza el grupo del rol indicado y sincroniza sus permisos con la cuenta.
def asignar_grupo_por_rol(usuario, rol):
	nombres_grupo = {
		'administrador': 'Administrador',
		'guardia': 'Guardia',
		'propietario': 'Propietario',
	}
	nombre_grupo = nombres_grupo[rol]
	grupo = Group.objects.filter(name__iexact=nombre_grupo).first()
	if grupo is None:
		grupo = Group.objects.create(name=nombre_grupo)
	permisos = Permission.objects.all()
	if rol == 'guardia':
		permisos = permisos.filter(content_type__app_label='BD', codename__in=PERMISOS_GUARDIA)
	elif rol == 'propietario':
		permisos = permisos.filter(content_type__app_label='BD', codename__in=PERMISOS_PROPIETARIO)
	grupo.permissions.set(permisos)
	usuario.groups.set((grupo,))

# Valida el tipo de reporte, aplica los filtros y prepara las filas y el resumen para la página.
@login_required(login_url='/login/')
@user_passes_test(es_administrador, login_url='/login/')
def reportes_view(request):
	aplicar_mora_vencida()
	reporte_seleccionado = request.GET.get('reporte', 'pagos')
	valid_reports = {value for value, _ in REPORT_OPTIONS}
	if reporte_seleccionado not in valid_reports:
		reporte_seleccionado = 'pagos'
	reporte_titulo, reporte_headers, reporte_rows = build_report_rows(request, reporte_seleccionado)
	casas_reporte = Casa.objects.order_by('numero_casa')
	if reporte_seleccionado == 'pagos':
		casas_reporte = casas_reporte.filter(id_propietario__isnull=False)
	return render(request, 'BD/reportes.html', {
		'report_options': REPORT_OPTIONS,
		'date_filter_reports': DATE_FILTER_REPORTS,
		'house_filter_reports': HOUSE_FILTER_REPORTS,
		'casas': casas_reporte,
		'reporte_seleccionado': reporte_seleccionado,
		'reporte_titulo': reporte_titulo,
		'reporte_headers': reporte_headers,
		'reporte_rows': reporte_rows,
		'resumen_pagos': build_payment_summary(request) if reporte_seleccionado == 'pagos' else None,
		'filtro_casa': request.GET.get('casa', '') if reporte_seleccionado in HOUSE_FILTER_REPORTS else '',
		'filtro_desde': request.GET.get('desde', '') if reporte_seleccionado in DATE_FILTER_REPORTS else '',
		'filtro_hasta': request.GET.get('hasta', '') if reporte_seleccionado in DATE_FILTER_REPORTS else '',
		'filtro_casa_numero': casas_reporte.filter(pk=request.GET.get('casa')).values_list('numero_casa', flat=True).first() if reporte_seleccionado in HOUSE_FILTER_REPORTS and request.GET.get('casa', '').isdigit() else None,
		'active_nav': 'reportes',
	})

# Genera el PDF del informe solicitado después de validar el identificador del tipo de reporte.
@login_required(login_url='/login/')
@user_passes_test(es_administrador, login_url='/login/')
def reporte_pdf_view(request):
	aplicar_mora_vencida()
	report_type = request.GET.get('reporte', 'pagos')
	valid_reports = {value for value, _ in REPORT_OPTIONS}
	if report_type not in valid_reports:
		report_type = 'pagos'
	return generate_report_pdf(request, report_type)


# Exporta a Excel los pagos correspondientes a los filtros recibidos en la solicitud.
@login_required(login_url='/login/')
@user_passes_test(es_administrador, login_url='/login/')
def reporte_excel_pagos_view(request):
	aplicar_mora_vencida()
	return generate_payments_excel(request)


# Presenta y guarda la configuración de cartera, reiniciando referencias de mora si cambia su frecuencia.
@login_required(login_url='/login/')
@user_passes_test(es_administrador, login_url='/login/')
def configuracion_cartera_view(request):
	aplicar_mora_vencida()
	configuracion = ConfiguracionCartera.objects.get(pk=1)
	frecuencia_anterior = configuracion.frecuencia_mora
	estados_casa = set(Casa.objects.values_list('estado', flat=True).distinct())
	form = ConfiguracionCarteraForm(
		request.POST or None,
		instance=configuracion,
		estados_casa=estados_casa,
	)
	if request.method == 'POST' and form.is_valid():
		configuracion = form.save(commit=False)
		configuracion.save()
		if configuracion.frecuencia_mora != frecuencia_anterior:
			ahora = timezone.now()
			Casa.objects.all().update(
				ultima_mora_calculada=ahora,
				ultima_mora_aplicada=timezone.localdate(ahora),
			)
		messages.success(request, 'Configuración actualizada correctamente.')
		return redirect('configuracion_cartera')
	return render(request, 'BD/configuracion_cartera.html', {
		'form': form,
		'active_nav': 'configuracion_cartera',
	})


# Administra la programación de respaldos y permite solicitar una copia manual.
@login_required(login_url='/login/')
@user_passes_test(es_administrador, login_url='/login/')
def copias_seguridad_view(request):
	configuracion, _ = ConfiguracionCopiasSeguridad.objects.get_or_create(pk=1)
	form = ConfiguracionCopiasSeguridadForm(instance=configuracion)
	if request.method == 'POST':
		accion = request.POST.get('accion')
		if accion == 'guardar_programacion':
			form = ConfiguracionCopiasSeguridadForm(request.POST, instance=configuracion)
			if form.is_valid():
				configuracion = form.save(commit=False)
				configuracion.proxima_automatica = (
					timezone.now() + intervalo_configurado(configuracion)
					if configuracion.automaticas_activas else None
				)
				configuracion.save()
				messages.success(request, 'La programación y la carpeta de destino se guardaron correctamente.')
				return redirect('copias_seguridad')
		elif accion == 'crear_manual':
			# Los errores del sistema de archivos se registran en bitácora técnica sin exponer detalles internos al formulario.
			try:
				copia, creada = crear_copia_seguridad(tipo='manual', usuario=request.user)
			except (DatabaseError, OSError, RuntimeError, ValueError):
				logger.exception('No se pudo crear una copia manual de seguridad.')
				messages.error(request, 'No se pudo crear la copia de seguridad. Revisa el espacio y permisos de la carpeta de destino.')
			else:
				messages.success(
					request,
					f'Copia manual creada: {copia.archivo}' if creada
					else f'No se generó un duplicado; el contenido ya está respaldado en {copia.archivo}.',
				)
			return redirect('copias_seguridad')
		elif accion == 'crear_informacion':
			try:
				copia, _ = crear_copia_seguridad(
					tipo='manual',
					usuario=request.user,
					alcance='informacion',
				)
			except (DatabaseError, OSError, RuntimeError, ValueError, sqlite3.Error):
				logger.exception('No se pudo crear una copia de información.')
				messages.error(request, 'No se pudo crear la copia de información. Revisa el espacio y los permisos de la carpeta de destino.')
			else:
				messages.success(request, f'Copia de información actualizada: {copia.archivo}')
			return redirect('copias_seguridad')
		else:
			return HttpResponseForbidden('Acción de copias de seguridad no válida.')

	copias = CopiaSeguridad.objects.all()[:100]
	return render(request, 'BD/copias_seguridad.html', {
		'form': form,
		'configuracion': configuracion,
		'copias': copias,
		'ruta_copias': directorio_copias(configuracion),
		'active_nav': 'copias_seguridad',
	})


# Fusiona una copia SQLite de información con los datos actuales, conservando la versión más reciente disponible.
@login_required(login_url='/login/')
@user_passes_test(es_administrador, login_url='/login/')
def restaurar_copia_informacion_view(request):
	if request.method != 'POST':
		return HttpResponseForbidden('La restauración requiere una solicitud POST.')
	if request.POST.get('confirmar_restauracion') != 'on':
		messages.error(request, 'Confirma que deseas fusionar la información antes de restaurar.')
		return redirect('copias_seguridad')
	archivo = request.FILES.get('archivo_copia')
	if archivo is None:
		messages.error(request, 'Selecciona el archivo de copia de información que deseas restaurar.')
		return redirect('copias_seguridad')
	try:
		_, copia, agregados, actualizados = restaurar_copia_informacion(archivo, request.user)
	except CopiaInformacionIdentica as aviso:
		messages.warning(request, str(aviso))
	except ValueError as error:
		messages.error(request, str(error))
	except (DatabaseError, OSError, RuntimeError, sqlite3.Error) as error:
		logger.exception('No se pudo restaurar una copia de información.')
		messages.error(request, f'No se pudo restaurar la copia: {error}')
	else:
		messages.success(
			request,
			f'Información fusionada desde {copia.archivo}: {agregados} registros agregados y '
			f'{actualizados} actualizados. Los registros sin fecha confiable conservaron la versión actual.',
		)
	return redirect('copias_seguridad')


# Valida y registra un ZIP completo sin extraerlo ni reemplazar el código que está ejecutándose.
@login_required(login_url='/login/')
@user_passes_test(es_administrador, login_url='/login/')
def subir_copia_proyecto_view(request):
	if request.method != 'POST':
		return HttpResponseForbidden('La carga de una copia requiere una solicitud POST.')
	archivo = request.FILES.get('archivo_proyecto')
	if archivo is None:
		messages.error(request, 'Selecciona el ZIP de la copia completa del proyecto.')
		return redirect('copias_seguridad')
	try:
		copia, _ = subir_copia_proyecto(archivo, request.user)
	except ValueError as error:
		messages.error(request, str(error))
	except (DatabaseError, OSError, RuntimeError, sqlite3.Error):
		logger.exception('No se pudo almacenar la copia completa del proyecto.')
		messages.error(request, 'No se pudo guardar el ZIP. Revisa el espacio disponible y los permisos de la carpeta de copias.')
	else:
		messages.success(request, f'Copia completa validada y guardada: {copia.archivo}')
	return redirect('copias_seguridad')


# Expone las carpetas locales navegables para elegir destino de respaldos y rechaza enlaces simbólicos.
@login_required(login_url='/login/')
@user_passes_test(es_administrador, login_url='/login/')
@require_GET
def explorar_carpetas_copias_seguridad_view(request):
	ruta_solicitada = request.GET.get('ruta', '').strip()
	if not ruta_solicitada:
		# La primera consulta muestra raíces locales disponibles sin asumir una letra de unidad o plataforma.
		if os.name == 'nt' and hasattr(os, 'listdrives'):
			rutas = [Path(unidad) for unidad in os.listdrives()]
		else:
			rutas = [Path(Path(settings.BASE_DIR).anchor or '/')]
		return JsonResponse({
			'actual': '',
			'carpetas': [
				{'nombre': ruta.anchor or str(ruta), 'ruta': str(ruta)}
				for ruta in rutas if ruta.is_dir()
			],
		})

	try:
		ruta_original = Path(ruta_solicitada).expanduser()
		# Se rechazan enlaces simbólicos antes de resolver rutas para limitar la navegación a carpetas directas.
		if ruta_original.is_symlink():
			return JsonResponse({'error': 'No se pueden explorar enlaces simbólicos.'}, status=400)
		ruta_actual = ruta_original.resolve(strict=True)
		if not ruta_actual.is_dir():
			return JsonResponse({'error': 'La ruta seleccionada no es una carpeta.'}, status=400)
		carpetas = [
			{'nombre': entrada.name, 'ruta': str(entrada)}
			for entrada in ruta_actual.iterdir()
			if not entrada.is_symlink() and entrada.is_dir()
		]
		carpetas.sort(key=lambda carpeta: carpeta['nombre'].casefold())
	except (OSError, RuntimeError, ValueError) as error:
		return JsonResponse({'error': f'No se pudo abrir esa carpeta: {error}'}, status=400)

	return JsonResponse({
		'actual': str(ruta_actual),
		'padre': str(ruta_actual.parent) if ruta_actual.parent != ruta_actual else None,
		'carpetas': carpetas,
	})


# Verifica el nombre y la existencia del archivo antes de descargar la copia identificada.
@login_required(login_url='/login/')
@user_passes_test(es_administrador, login_url='/login/')
def descargar_copia_seguridad_view(request, copia_id):
	copia = get_object_or_404(CopiaSeguridad, pk=copia_id)
	ruta = ruta_archivo_copia(copia)
	# El nombre de base y el nombre resuelto deben coincidir para impedir que un identificador apunte fuera del archivo esperado.
	if Path(copia.archivo).name != copia.archivo or ruta.name != copia.archivo or not ruta.is_file():
		raise Http404('El archivo de copia de seguridad no está disponible.')
	return FileResponse(ruta.open('rb'), as_attachment=True, filename=copia.archivo)


# Elimina una copia únicamente mediante POST, retirando tanto el archivo como su registro.
@login_required(login_url='/login/')
@user_passes_test(es_administrador, login_url='/login/')
def eliminar_copia_seguridad_view(request, copia_id):
	if request.method != 'POST':
		return HttpResponseForbidden('La eliminación requiere una solicitud POST.')
	copia = get_object_or_404(CopiaSeguridad, pk=copia_id)
	ruta = ruta_archivo_copia(copia)
	if Path(copia.archivo).name != copia.archivo or ruta.name != copia.archivo:
		raise Http404('La ruta de la copia no es válida.')
	if ruta.exists():
		ruta.unlink()
	copia.delete()
	messages.success(request, 'La copia de seguridad se eliminó correctamente.')
	return redirect('copias_seguridad')


# Actualiza la mora vencida y devuelve saldos a administración o al propietario de cada casa.
@login_required(login_url='/login/')
@user_passes_test(lambda user: es_administrador(user) or es_propietario(user), login_url='/login/')
def actualizar_saldos_cartera_view(request):
	aplicar_mora_vencida()
	configuracion = ConfiguracionCartera.objects.get(pk=1)
	casas = Casa.objects.all()
	if configuracion.frecuencia_mora == 'minuto':
		casas = casas.filter(
			Q(pagos__isnull=False) | Q(cartera__gt=0) | Q(saldo_mora__gt=0),
		).distinct()
	else:
		casas = casas.filter(pagos__isnull=False).distinct()
	# Los propietarios solo reciben los saldos de sus propias viviendas; administración conserva el conjunto completo.
	if es_propietario(request.user) and not es_administrador(request.user):
		casas = casas.filter(id_propietario__usuario=request.user)
	saldos = saldos_actuales_por_casa(casas)
	return JsonResponse({'saldos': {str(casa_id): str(saldo) for casa_id, saldo in saldos.items()}})


# Añade el número de una casa al historial del propietario sin guardar duplicados.
def registrar_casa_historica(propietario, numero_casa):
	if not propietario or numero_casa is None:
		return
	numeros = list(propietario.casas_historicas or [])
	if numero_casa not in numeros:
		numeros.append(numero_casa)
		propietario.casas_historicas = numeros
		propietario.save(update_fields=('casas_historicas',))


# Adjunta el saldo calculado a cada instancia para mostrarlo en listados de casas.
def _casas_con_saldo_actual(queryset):
	casas = list(queryset)
	saldos = saldos_actuales_por_casa(Casa.objects.filter(pk__in=[casa.pk for casa in casas]))
	for casa in casas:
		casa.saldo_actual = saldos.get(casa.pk, 0)
	return casas


# Construye por casa las opciones de autorización de residentes y propietarios, sin repetir residentes.
def personas_autorizantes_por_casa():
	casas = Casa.objects.select_related('id_residente', 'id_propietario').prefetch_related('residentes_secundarios').order_by('numero_casa')
	resultado = {}
	for casa in casas:
		personas = []
		residentes = ([casa.id_residente] if casa.id_residente else []) + list(casa.residentes_secundarios.all())
		ids_residentes = set()
		for residente in residentes:
			# El mismo residente puede aparecer como principal y secundario; se expone una sola opción por casa.
			if residente.pk in ids_residentes:
				continue
			ids_residentes.add(residente.pk)
			personas.append({
				'id': f'residente:{residente.pk}',
				'nombre': f'{residente.nombre} {residente.apellido}',
				'telefono': residente.telefono or 'Sin teléfono',
			})
		if casa.id_propietario:
			personas.append({
				'id': f'propietario:{casa.id_propietario.pk}',
				'nombre': f'{casa.id_propietario.nombre} {casa.id_propietario.apellido}',
				'telefono': casa.id_propietario.telefono or 'Sin teléfono',
			})
		resultado[str(casa.pk)] = personas
	return resultado


# Crea un rango consecutivo de casas solo después de comprobar que sus números no estén registrados.
def generar_casas_en_lote(*, cantidad, numero_inicial, residente=None, propietario=None, cantidad_personas=1, estado='Activa', cartera=0, cantidad_residentes=1):
	if cantidad < 1:
		raise ValueError('La cantidad de casas debe ser mayor que cero.')
	if numero_inicial < 1:
		raise ValueError('El número inicial debe ser mayor que cero.')
	# Comprueba todo el rango antes de insertar para evitar comenzar una generación con números ya ocupados.
	numeros = list(range(numero_inicial, numero_inicial + cantidad))
	duplicados = [numero for numero in numeros if Casa.objects.filter(numero_casa=numero).exists()]
	if duplicados:
		raise ValueError(f'No se pueden crear casas duplicadas. Los números ya registrados son: {duplicados}')
	casas = []
	for numero in numeros:
		casa = Casa.objects.create(
			numero_casa=numero,
			cantidad_personas=cantidad_personas,
			cantidad_residentes=cantidad_residentes,
			estado=estado,
			cartera=cartera,
			id_residente=residente,
			id_propietario=propietario,
		)
		casas.append(casa)
	return casas


# Actualiza el contador de residentes cuando los vínculos existentes superan el total guardado.
def sincronizar_cantidad_residentes(casa):
	# El total persistido nunca se reduce por debajo de los vínculos principales y secundarios existentes.
	residentes_vinculados = CasaResidente.objects.filter(casa=casa).count() + int(bool(casa.id_residente_id))
	if residentes_vinculados > casa.cantidad_residentes:
		casa.cantidad_residentes = residentes_vinculados
		casa.save(update_fields=('cantidad_residentes',))


# Valida el rol y el método de solicitud antes de guardar una reseña vinculada con su autor.
def resena_submit(request):
	is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest'
	if not puede_enviar_resena(request.user):
		if is_ajax:
			return JsonResponse({'success': False, 'message': 'No tienes permiso para enviar una reseña.'}, status=403)
		return redirect('/#testimonials')
	if request.method != 'POST':
		if is_ajax:
			return JsonResponse({'success': False, 'message': 'Método de solicitud no permitido.'}, status=405)
		return redirect('/#testimonials')
	form = ResenaForm(request.POST)
	if form.is_valid():
		resena = form.save(commit=False)
		resena.usuario = request.user
		resena.rol_usuario = obtener_rol_resena(request.user)
		resena.save()
		if is_ajax:
			return JsonResponse({'success': True, 'message': 'Tu reseña fue enviada para revisión.'})
		return redirect('/#testimonials')
	if is_ajax:
		mensaje = next(iter(form.errors.values()), ['Revisa los datos de la reseña.'])[0]
		return JsonResponse({'success': False, 'message': str(mensaje)}, status=400)
	return redirect('/#testimonials')


# Lista reseñas para administración y procesa acciones de aprobación, ocultamiento o eliminación.
@login_required(login_url='/login/')
@user_passes_test(es_administrador, login_url='/login/')
def resenas_view(request):
	if request.method == 'POST':
		resena = get_object_or_404(Resena, pk=request.POST.get('resena_id'))
		action = request.POST.get('action')
		if action == 'delete':
			resena.delete()
			messages.success(request, 'Reseña eliminada correctamente.')
		elif action in ('approve', 'reject'):
			resena.aprobada = action == 'approve'
			resena.save(update_fields=['aprobada'])
			messages.success(request, 'Reseña actualizada correctamente.')
		return redirect('resenas')
	estado_filtro = request.GET.get('estado', '')
	if estado_filtro not in ('aprobada', 'pendiente'):
		estado_filtro = ''
	calificacion_filtro = request.GET.get('calificacion', '')
	resenas = Resena.objects.select_related('usuario').order_by('-id_resena')
	if estado_filtro == 'aprobada':
		resenas = resenas.filter(aprobada=True)
	elif estado_filtro == 'pendiente':
		resenas = resenas.filter(aprobada=False)
	if calificacion_filtro in {'1', '2', '3', '4', '5'}:
		resenas = resenas.filter(calificacion=int(calificacion_filtro))
	else:
		calificacion_filtro = ''
	return render(request, 'BD/resenas.html', {
		'resenas': resenas,
		'estado_filtro': estado_filtro,
		'calificacion_filtro': calificacion_filtro,
		'calificaciones': Resena.CALIFICACIONES,
		'active_nav': 'resenas',
	})


# Registra o edita residentes y prepara la lista filtrada para la gestión administrativa.
@login_required(login_url='/login/')
@user_passes_test(es_administrador, login_url='/login/')
def residentes_view(request, residente_id=None):
	residente = get_object_or_404(Residente, pk=residente_id) if residente_id else None

	if request.method == 'POST':
		if request.POST.get('action') == 'delete':
			residente = get_object_or_404(Residente, pk=request.POST.get('residente_id'))
			residente.delete()
			messages.success(request, 'Residente eliminado correctamente.')
			return redirectar_a_registros('residentes')

		form = ResidenteForm(request.POST, instance=residente)
		if form.is_valid():
			residente_guardado = form.save()
			if residente is None:
				registrar_evento_bitacora(
					modulo='Residente',
					registro=f'{residente_guardado.nombre} {residente_guardado.apellido}',
					descripcion=f'Residente registrado con cédula {residente_guardado.cedula}.',
					usuario=request.user,
				)
			messages.success(
				request,
				'Residente actualizado correctamente.' if residente else 'Residente registrado correctamente.',
			)
			return redirectar_a_registros('residentes')
	else:
		form = ResidenteForm(instance=residente)

	return render(request, 'BD/residente.html', {
		'residentes': Residente.objects.order_by('-id_residente'),
		'form': form,
		'residente_editando': residente,
		'active_nav': 'residentes',
	})


# Registra o edita visitantes y guarda sus datos de ingreso, vivienda y autorización.
@login_required(login_url='/login/')
def visitante_ingreso_view(request, visitante_id=None):
	visitante = get_object_or_404(Visitante, pk=visitante_id) if visitante_id else None
	guardia = guardia_del_usuario(request.user)
	proceso_visitante = Proceso.objects.filter(
		id_visitante=visitante,
		tipo='Visitante',
	).select_related('id_casa').order_by('-fecha', '-id_proceso').first() if visitante else None
	casa_id = request.POST.get('vivienda') if request.method == 'POST' else (proceso_visitante.id_casa_id if proceso_visitante else None)
	if request.method == 'POST' and request.POST.get('action') == 'delete':
		get_object_or_404(Visitante, pk=request.POST.get('visitante_id')).delete()
		messages.success(request, 'Visitante eliminado correctamente.')
		return redirectar_a_registros('registrar_visitante')
	if request.method == 'POST':
		form = VisitanteEstadoForm(request.POST) if visitante else VisitanteIngresoForm(request.POST, guardia=guardia, casa_id=casa_id)
		if form.is_valid():
			if visitante:
				if not proceso_visitante:
					messages.error(request, 'No se encontró el ingreso asociado para actualizar el estado del visitante.')
				else:
					estado_nuevo = form.cleaned_data['estado']
					if proceso_visitante.estado != estado_nuevo or (
						estado_nuevo == 'SALIDO' and proceso_visitante.fecha_salida is None
					):
						proceso_visitante.estado = estado_nuevo
						proceso_visitante.fecha_salida = timezone.now() if estado_nuevo == 'SALIDO' else None
						proceso_visitante.save(update_fields=('estado', 'fecha_salida'))
					messages.success(request, 'Estado del visitante actualizado correctamente.')
					return redirectar_a_registros('registrar_visitante')
			else:
				with transaction.atomic():
					visitante = form.save(commit=False)
					visitante.save()
					Proceso.objects.create(tipo='Visitante', cedula=visitante.cedula, nombre=f'{visitante.nombre} {visitante.apellido}', vehiculo_tiene=visitante.vehiculo_trae, vehiculo_tipo=visitante.vehiculo_tipo, placa=visitante.placa_v, descripcion=f'Tipo visitante: {visitante.tipo_v}; Conductor: {visitante.conductor or "N/A"}; Personas: {visitante.cantidad_personas}', fecha=timezone.now(), id_guardia=form.cleaned_data['guardia'], id_casa=form.cleaned_data['vivienda'], id_visitante=visitante)
				messages.success(request, 'Ingreso del visitante registrado correctamente.')
				return redirectar_a_registros('registrar_visitante')
	else:
		form = VisitanteEstadoForm(initial={'estado': proceso_visitante.estado}) if visitante and proceso_visitante else VisitanteEstadoForm() if visitante else VisitanteIngresoForm(guardia=guardia)

	casa_filtro = request.GET.get('casa', '').strip()
	entrada_filtro = request.GET.get('entrada', '').strip()
	documento_filtro = request.GET.get('documento', '').strip()
	procesos_visitante = Prefetch(
		'procesos',
		queryset=Proceso.objects.filter(tipo='Visitante').select_related('id_casa').order_by('-fecha', '-id_proceso'),
		to_attr='procesos_visitante',
	)
	visitantes = Visitante.objects.prefetch_related(procesos_visitante).order_by('-id_visitante')
	if casa_filtro.isdigit():
		visitantes = visitantes.filter(procesos__tipo='Visitante', procesos__id_casa_id=int(casa_filtro))
	if entrada_filtro in ('SI', 'NO'):
		visitantes = visitantes.filter(vehiculo_trae=entrada_filtro)
	if documento_filtro:
		visitantes = visitantes.filter(cedula__icontains=documento_filtro)
	return render(request, 'BD/visitante.html', {
		'form': form,
		'casas_residentes': personas_autorizantes_por_casa(),
		'visitantes': visitantes.distinct(),
		'casas_filtro': Casa.objects.order_by('numero_casa'),
		'casa_filtro': casa_filtro,
		'entrada_filtro': entrada_filtro,
		'documento_filtro': documento_filtro,
		'active_nav': 'visitantes',
		'visitante_editando': visitante,
	})


# Registra o edita domiciliarios y asocia el ingreso con la casa y persona que lo autoriza.
@login_required(login_url='/login/')
def domicilio_ingreso_view(request, domicilio_id=None):
	domicilio = get_object_or_404(Domicilio, pk=domicilio_id) if domicilio_id else None
	configuracion = ConfiguracionCartera.objects.get(pk=1)
	tiempo_domiciliario_segundos = configuracion.tiempo_domiciliario_minutos * 60
	guardia = guardia_del_usuario(request.user)
	proceso_domicilio = Proceso.objects.filter(id_domicilio=domicilio, tipo='Domicilio').select_related('id_casa').first() if domicilio else None
	casa_id = request.POST.get('vivienda') or (proceso_domicilio.id_casa_id if proceso_domicilio else None)
	action = request.POST.get('action') if request.method == 'POST' else None
	if action in ('delete', 'delivered') and not domicilio:
		domicilio = get_object_or_404(Domicilio, pk=request.POST.get('domicilio_id'))
	if domicilio and action == 'delete':
		domicilio.delete()
		messages.success(request, 'Domiciliario eliminado correctamente.')
		return redirectar_a_registros('registrar_domicilio')
	if domicilio and action == 'delivered':
		proceso = Proceso.objects.filter(id_domicilio=domicilio, tipo='Domicilio').order_by('-fecha').first()
		if proceso:
			segundos_transcurridos = (timezone.now() - proceso.fecha).total_seconds()
			tiempo_restante = max(0, min(tiempo_domiciliario_segundos, ceil(tiempo_domiciliario_segundos - segundos_transcurridos)))
			proceso.estado = 'ENTREGADO_TARDE' if tiempo_restante == 0 else 'ENTREGADO'
			proceso.tiempo_restante = tiempo_restante
			proceso.save(update_fields=('estado', 'tiempo_restante'))
			messages.success(request, 'Domiciliario marcado como entrega tardía.' if tiempo_restante == 0 else 'Domiciliario marcado como entregado.')
		else:
			messages.error(request, 'No se encontró el ingreso del domiciliario para actualizar su salida.')
		return redirectar_a_registros('registrar_domicilio')
	if request.method == 'POST':
		form = DomicilioForm(request.POST, instance=domicilio, casa_id=casa_id) if domicilio else DomicilioIngresoForm(request.POST, guardia=guardia, casa_id=casa_id)
		if form.is_valid():
			with transaction.atomic():
				domicilio = form.save()
				if domicilio_id:
					Proceso.objects.filter(id_domicilio=domicilio, tipo='Domicilio').update(nombre=f'{domicilio.nombre} {domicilio.apellido}', vehiculo_tipo=domicilio.vehiculo_tipo, placa=domicilio.vehiculo_placa)
				else:
					Proceso.objects.create(tipo='Domicilio', nombre=f'{domicilio.nombre} {domicilio.apellido}', fecha=timezone.now(), id_guardia=form.cleaned_data['guardia'], id_casa=form.cleaned_data['vivienda'], id_domicilio=domicilio, vehiculo_tiene='SI', vehiculo_tipo=domicilio.vehiculo_tipo, placa=domicilio.vehiculo_placa)
			messages.success(request, 'Domiciliario actualizado correctamente.' if domicilio_id else 'Ingreso del domiciliario registrado correctamente.')
			return redirectar_a_registros('registrar_domicilio')
	else:
		form = DomicilioForm(instance=domicilio, casa_id=casa_id) if domicilio else DomicilioIngresoForm(guardia=guardia)

	procesos_domicilio = Prefetch('procesos', queryset=Proceso.objects.filter(tipo='Domicilio').select_related('id_casa').order_by('-fecha'), to_attr='domicilio_procesos')
	vivienda_filtro = request.GET.get('vivienda', '')
	domicilios = Domicilio.objects.prefetch_related(procesos_domicilio).order_by('-id_domicilio')
	if vivienda_filtro.isdigit():
		domicilios = domicilios.filter(procesos__tipo='Domicilio', procesos__id_casa_id=int(vivienda_filtro))
	return render(request, 'BD/domicilio.html', {
		'form': form,
		'domicilios': domicilios,
		'casas': Casa.objects.order_by('numero_casa'),
		'vivienda_filtro': vivienda_filtro,
		'active_nav': 'domicilios',
		'domicilio_editando': domicilio,
		'casas_residentes': personas_autorizantes_por_casa(),
		'tiempo_domiciliario_segundos': tiempo_domiciliario_segundos,
		'tiempo_domiciliario_formateado': f'{configuracion.tiempo_domiciliario_minutos:02d}:00',
	})


# Calcula qué ingresos de domiciliarios superan el tiempo configurado y muestra sus alertas.
@login_required(login_url='/login/')
def domicilios_demorados_view(request):
	configuracion = ConfiguracionCartera.objects.get(pk=1)
	limite = timezone.now() - timedelta(minutes=configuracion.tiempo_domiciliario_minutos)
	procesos = Proceso.objects.filter(
		tipo='Domicilio',
		estado='PENDIENTE',
		fecha__lte=limite,
	).select_related('id_casa').order_by('fecha', 'id_proceso')
	return JsonResponse({
		'domicilios': [
			{'id': proceso.id_proceso, 'nombre': proceso.nombre, 'casa': proceso.id_casa.numero_casa}
			for proceso in procesos
		]
	})


# Registra o edita paquetes recibidos, su destinatario, estado y datos de seguimiento.
@login_required(login_url='/login/')
def paquete_ingreso_view(request, paquete_id=None):
	paquete = get_object_or_404(Paquete, pk=paquete_id) if paquete_id else None
	guardia = guardia_del_usuario(request.user)
	proceso_paquete = Proceso.objects.filter(id_paquete=paquete, tipo='Paquete').select_related('id_casa').first() if paquete else None
	casa_id = request.POST.get('vivienda') or (proceso_paquete.id_casa_id if proceso_paquete else None)
	action = request.POST.get('action') if request.method == 'POST' else None
	if action in ('delete', 'delivered', 'update_status') and not paquete:
		paquete = get_object_or_404(Paquete, pk=request.POST.get('paquete_id'))
	if paquete and action == 'delete':
		paquete.delete()
		messages.success(request, 'Paquete eliminado correctamente.')
		return redirectar_a_registros('registrar_paquete')
	if paquete and action == 'delivered':
		Proceso.objects.filter(id_paquete=paquete, tipo='Paquete').update(estado='ENTREGADO')
		messages.success(request, 'Paquete marcado como entregado.')
		return redirectar_a_registros('registrar_paquete')
	if paquete and action == 'update_status':
		estado = request.POST.get('estado_paquete')
		if estado in ('PENDIENTE', 'ENTREGADO', 'DEVUELTO'):
			Proceso.objects.filter(id_paquete=paquete, tipo='Paquete').update(estado=estado)
			messages.success(request, 'Estado del paquete actualizado.')
		return redirectar_a_registros('registrar_paquete')
	if request.method == 'POST':
		form = PaqueteForm(request.POST, request.FILES, instance=paquete, casa_id=casa_id, estado_actual=proceso_paquete.estado if proceso_paquete else None) if paquete else PaqueteIngresoForm(request.POST, request.FILES, guardia=guardia, casa_id=casa_id)
		if form.is_valid():
			with transaction.atomic():
				paquete = form.save()
				if paquete_id:
					Proceso.objects.filter(id_paquete=paquete, tipo='Paquete').update(nombre=f'{paquete.nombre} {paquete.apellido}', descripcion=paquete.desc_tipo, estado=form.cleaned_data['estado_paquete'])
				else:
					Proceso.objects.create(tipo='Paquete', nombre=f'{paquete.nombre} {paquete.apellido}', descripcion=paquete.desc_tipo, estado=form.cleaned_data['estado_paquete'], fecha=timezone.now(), id_guardia=form.cleaned_data['guardia'], id_casa=form.cleaned_data['vivienda'], id_paquete=paquete)
			messages.success(request, 'Paquete actualizado correctamente.' if paquete_id else 'Paquete registrado correctamente.')
			return redirectar_a_registros('registrar_paquete')
	else:
		form = PaqueteForm(instance=paquete, casa_id=casa_id, estado_actual=proceso_paquete.estado if proceso_paquete else None) if paquete else PaqueteIngresoForm(guardia=guardia)

	procesos_paquete = Prefetch('procesos', queryset=Proceso.objects.filter(tipo='Paquete').select_related('id_casa').order_by('-fecha'), to_attr='paquete_procesos')
	vivienda_filtro = request.GET.get('vivienda', '')
	paquetes = Paquete.objects.select_related('residente_secundario', 'propietario_autorizador').prefetch_related(procesos_paquete).order_by('-id_paquete')
	if vivienda_filtro.isdigit():
		paquetes = paquetes.filter(procesos__tipo='Paquete', procesos__id_casa_id=int(vivienda_filtro))
	return render(request, 'BD/paquete.html', {'form': form, 'paquetes': paquetes, 'casas': Casa.objects.order_by('numero_casa'), 'vivienda_filtro': vivienda_filtro, 'active_nav': 'paquetes', 'paquete_editando': paquete, 'casas_residentes': personas_autorizantes_por_casa()})


# Registra y administra novedades de la comunidad, incluyendo fecha del suceso y evidencia adjunta.
@login_required(login_url='/login/')
@user_passes_test(es_administrador, login_url='/login/')
def novedad_view(request, nota_id=None):
	nota = get_object_or_404(Novedad, pk=nota_id) if nota_id else None
	if request.method == 'POST' and request.POST.get('action') == 'delete':
		get_object_or_404(Novedad, pk=request.POST.get('nota_id')).delete()
		messages.success(request, 'Novedad eliminada correctamente.')
		return redirectar_a_registros('registrar_novedad')
	form = NovedadForm(request.POST or None, request.FILES or None, instance=nota)
	if request.method == 'POST' and form.is_valid():
		novedad = form.save(commit=False)
		novedad.registrado_por = request.user
		novedad.save()
		messages.success(request, 'Novedad actualizada correctamente.' if nota else 'Novedad publicada correctamente.')
		return redirectar_a_registros('registrar_novedad')
	tipos_comunes = ('Corte de luz', 'Corte de agua', 'Corte de gas')
	tipo_filtro = request.GET.get('tipo', '').strip()
	fecha_filtro = request.GET.get('fecha', '').strip()
	tipos_existentes = set(Novedad.objects.values_list('tipo', flat=True))
	tipos_filtro = [tipo for tipo in tipos_comunes if tipo in tipos_existentes]
	hay_otros = any(tipo not in tipos_comunes for tipo in tipos_existentes)
	novedades = Novedad.objects.select_related('registrado_por').order_by('-id_novedad')
	if tipo_filtro in tipos_comunes:
		novedades = novedades.filter(tipo=tipo_filtro)
	elif tipo_filtro == 'Otros':
		novedades = novedades.exclude(tipo__in=tipos_comunes)
	if fecha_filtro:
		novedades = novedades.filter(fecha_suceso__date=fecha_filtro)
	return render(request, 'BD/novedad.html', {
		'form': form,
		'novedades': novedades,
		'tipos_filtro': tipos_filtro,
		'hay_otros': hay_otros,
		'tipo_filtro': tipo_filtro,
		'fecha_filtro': fecha_filtro,
		'active_nav': 'novedades',
		'novedad_editando': nota,
	})


# Registra o edita notas de portería y las relaciona con el guardia responsable.
@login_required(login_url='/login/')
def nota_view(request, nota_id=None):
	nota = get_object_or_404(Notas, pk=nota_id) if nota_id else None
	guardia = guardia_del_usuario(request.user)
	if request.method == 'POST' and request.POST.get('action') == 'delete':
		get_object_or_404(Notas, pk=request.POST.get('nota_id')).delete()
		messages.success(request, 'Nota eliminada correctamente.')
		return redirectar_a_registros('registrar_nota')
	form = NotaForm(request.POST or None, request.FILES or None, instance=nota, guardia=guardia if not nota else nota.id_guardia)
	if request.method == 'POST' and form.is_valid():
		nota_guardada = form.save(commit=False)
		if not nota and guardia:
			nota_guardada.id_guardia = guardia
		nota_guardada.save()
		messages.success(request, 'Nota actualizada correctamente.' if nota else 'Nota registrada correctamente.')
		return redirectar_a_registros('registrar_nota')
	fecha_filtro = request.GET.get('fecha', '').strip()
	notas = Notas.objects.select_related('id_guardia').order_by('-id_nota')
	if fecha_filtro:
		notas = notas.filter(fecha__date=fecha_filtro)
	return render(request, 'BD/notas.html', {
		'form': form,
		'notas': notas,
		'fecha_filtro': fecha_filtro,
		'active_nav': 'notas',
		'nota_editando': nota,
	})


# Gestiona pagos según el rol, aplica abonos a mora y capital al confirmar, y revierte esos importes al anular.
@login_required(login_url='/login/')
@user_passes_test(lambda user: es_administrador(user) or es_propietario(user), login_url='/login/')
def pago_view(request, pago_id=None):
	aplicar_mora_vencida()
	propietario_usuario = Propietario.objects.filter(usuario=request.user).first() if es_propietario(request.user) else None
	if es_propietario(request.user) and propietario_usuario is None:
		return HttpResponseForbidden('La cuenta de propietario no tiene una casa asignada.')
	if propietario_usuario and pago_id:
		return HttpResponseForbidden('El propietario no puede editar pagos.')
	pago_queryset = Pago.objects.select_related('id_casa')
	if propietario_usuario:
		pago_queryset = pago_queryset.filter(id_casa__id_propietario=propietario_usuario)
	pago = get_object_or_404(pago_queryset, pk=pago_id) if pago_id else None
	estado_original = pago.estado if pago else ''
	if request.method == 'POST' and request.POST.get('action') == 'delete':
		if propietario_usuario:
			messages.error(request, 'El propietario no puede eliminar pagos.')
			return redirectar_a_registros('registrar_pago')
		with transaction.atomic():
			pago_eliminar = get_object_or_404(Pago.objects.select_for_update(), pk=request.POST.get('pago_id'))
			if pago_eliminar.estado == 'Pagado':
				casa = Casa.objects.select_for_update().get(pk=pago_eliminar.id_casa_id)
				mora_aplicada = pago_eliminar.valor_mora_aplicada
				capital_aplicado = pago_eliminar.valor_cartera_aplicada
				saldo_favor_aplicado = pago_eliminar.valor_saldo_favor_aplicado
				casa.saldo_favor -= saldo_favor_aplicado
				if mora_aplicada == 0 and capital_aplicado == 0 and saldo_favor_aplicado == 0:
					capital_aplicado = pago_eliminar.valor
				casa.saldo_mora += mora_aplicada
				casa.cartera += capital_aplicado
				casa.save(update_fields=('saldo_mora', 'cartera', 'saldo_favor'))
			pago_eliminar.delete()
		messages.success(request, 'Pago eliminado correctamente.')
		return redirectar_a_registros('registrar_pago')
	form = PagoForm(
		request.POST or None,
		request.FILES or None,
		instance=pago,
		propietario=bool(propietario_usuario),
		solo_estado=bool(pago and not propietario_usuario),
	)
	if propietario_usuario:
		form.fields['id_casa'].queryset = propietario_usuario.casas.order_by('numero_casa')
	if not propietario_usuario and 'id_casa' in form.fields:
		form.fields['id_casa'].queryset = form.fields['id_casa'].queryset.filter(id_propietario__isnull=False)
	if request.method == 'POST' and form.is_valid():
		with transaction.atomic():
			pago_guardado = form.save(commit=False)
			if estado_original != pago_guardado.estado:
				casa = Casa.objects.select_for_update().get(pk=pago_guardado.id_casa_id)
				if pago_guardado.estado == 'Pagado':
					# El pago cubre primero la mora y luego el capital; cada parte queda registrada para poder revertirla.
					pago_guardado.valor_mora_aplicada = min(casa.saldo_mora, pago_guardado.valor)
					pago_guardado.valor_cartera_aplicada = min(
						casa.cartera,
						pago_guardado.valor - pago_guardado.valor_mora_aplicada,
					)
					pago_guardado.valor_saldo_favor_aplicado = max(
						pago_guardado.valor - pago_guardado.valor_mora_aplicada - pago_guardado.valor_cartera_aplicada,
						0,
					)
					casa.saldo_mora -= pago_guardado.valor_mora_aplicada
					casa.cartera -= pago_guardado.valor_cartera_aplicada
					casa.saldo_favor += pago_guardado.valor_saldo_favor_aplicado
					pago_guardado.saldo_pendiente_despues = max(
						max(casa.cartera, 0) + max(casa.saldo_mora, 0) - max(casa.saldo_favor, 0),
						0,
					)
				elif estado_original == 'Pagado':
					# Al retirar el estado pagado se devuelve a la casa exactamente lo aplicado por este pago.
					mora_aplicada = pago.valor_mora_aplicada
					capital_aplicado = pago.valor_cartera_aplicada
					saldo_favor_aplicado = pago.valor_saldo_favor_aplicado
					casa.saldo_favor -= saldo_favor_aplicado
					if mora_aplicada == 0 and capital_aplicado == 0 and saldo_favor_aplicado == 0:
						capital_aplicado = pago.valor
					casa.saldo_mora += mora_aplicada
					casa.cartera += capital_aplicado
					pago_guardado.valor_mora_aplicada = 0
					pago_guardado.valor_cartera_aplicada = 0
					pago_guardado.valor_saldo_favor_aplicado = 0
					pago_guardado.saldo_pendiente_despues = None
				casa.save(update_fields=('saldo_mora', 'cartera', 'saldo_favor'))
			pago_guardado.save()
		messages.success(request, 'Pago actualizado correctamente.' if pago else 'Pago registrado correctamente.')
		return redirectar_a_registros('registrar_pago')
	vivienda_filtro = request.GET.get('vivienda', '')
	desde_filtro = request.GET.get('desde', '')
	hasta_filtro = request.GET.get('hasta', '')
	estado_filtro = request.GET.get('estado', '')
	try:
		fecha_desde = datetime.strptime(desde_filtro, '%Y-%m-%d').date() if desde_filtro else None
	except ValueError:
		fecha_desde = None
		desde_filtro = ''
	try:
		fecha_hasta = datetime.strptime(hasta_filtro, '%Y-%m-%d').date() if hasta_filtro else None
	except ValueError:
		fecha_hasta = None
		hasta_filtro = ''
	pagos = pago_queryset.select_related('id_casa').order_by('-fecha', '-id_pago')
	if vivienda_filtro.isdigit():
		pagos = pagos.filter(id_casa_id=int(vivienda_filtro))
	if estado_filtro in {'Pagado', 'Pendiente'}:
		pagos = pagos.filter(estado=estado_filtro)
	else:
		estado_filtro = ''
	if fecha_desde and fecha_hasta and fecha_desde > fecha_hasta:
		messages.error(request, 'La fecha desde no puede ser posterior a la fecha hasta.')
		pagos = pagos.none()
	else:
		if fecha_desde:
			pagos = pagos.filter(fecha__gte=fecha_desde)
		if fecha_hasta:
			pagos = pagos.filter(fecha__lte=fecha_hasta)
	for pago_item in pagos:
		if pago_item.saldo_pendiente_despues is not None:
			pago_item.saldo_restante = pago_item.saldo_pendiente_despues
		elif pago_item.estado != 'Pagado':
			# Un pago aún no confirmado no tiene saldo histórico; se presenta la deuda neta actual provisional.
			pago_item.saldo_restante = max(
				pago_item.id_casa.cartera + pago_item.id_casa.saldo_mora - pago_item.id_casa.saldo_favor,
				0,
			)
		else:
			pago_item.saldo_restante = None
	casas = propietario_usuario.casas.order_by('numero_casa') if propietario_usuario else Casa.objects.order_by('numero_casa')
	casas_con_saldo = casas.filter(pagos__isnull=False).distinct().select_related('id_propietario')
	if vivienda_filtro.isdigit():
		casas_con_saldo = casas_con_saldo.filter(pk=int(vivienda_filtro))
	saldos_actuales = saldos_actuales_por_casa(casas_con_saldo)
	saldos_actuales_casas = []
	for casa in casas_con_saldo:
		saldo = saldos_actuales.get(casa.pk, 0)
		deuda_bruta = max(casa.cartera, 0) + max(casa.saldo_mora, 0)
		saldos_actuales_casas.append({
			'casa': casa,
			'saldo': saldo,
			'saldo_favor': max(casa.saldo_favor - deuda_bruta, 0),
			'pendiente': saldo > 0,
		})
	return render(request, 'BD/pagos.html', {
		'form': form,
		'pagos': pagos,
		'casas': casas,
		'vivienda_filtro': vivienda_filtro,
		'desde_filtro': desde_filtro,
		'hasta_filtro': hasta_filtro,
		'estado_filtro': estado_filtro,
		'saldos_actuales_casas': saldos_actuales_casas,
		'active_nav': 'pagos',
		'pago_editando': pago,
		'es_propietario': bool(propietario_usuario),
	})


# Autoriza el acceso al pago y genera su comprobante PDF individual.
@login_required(login_url='/login/')
@user_passes_test(lambda user: es_administrador(user) or es_propietario(user), login_url='/login/')
def recibo_pago_view(request, pago_id):
	pagos = Pago.objects.select_related('id_casa', 'id_casa__id_propietario')
	if es_propietario(request.user) and not es_administrador(request.user):
		propietario = Propietario.objects.filter(usuario=request.user).first()
		if propietario is None:
			return HttpResponseForbidden('La cuenta no tiene una casa asignada.')
		pagos = pagos.filter(id_casa__id_propietario=propietario)
	pago = get_object_or_404(pagos, pk=pago_id)
	return generate_payment_receipt_pdf(pago)


# Crea, edita o elimina casas y residentes asociados dentro de una transacción, con auditoría de los cambios.
@login_required(login_url='/login/')
@user_passes_test(es_administrador, login_url='/login/')
def registrar_casa_view(request, casa_id=None):
	aplicar_mora_vencida()
	casa = get_object_or_404(Casa, pk=casa_id) if casa_id else None
	es_casa_nueva = casa is None
	casa_filtro = request.GET.get('casa', '').strip()
	if request.method == 'POST' and request.POST.get('action') == 'delete':
		casa_para_eliminar = get_object_or_404(Casa, pk=request.POST.get('casa_id'))
		if casa_para_eliminar.pagos.exists():
			messages.error(
				request,
				'No se puede eliminar esta casa porque tiene pagos registrados.',
				extra_tags='casa-protegida',
			)
			return redirectar_a_registros('registrar_casa')
		registrar_casa_historica(casa_para_eliminar.id_propietario, casa_para_eliminar.numero_casa)
		casa_para_eliminar.delete()
		messages.success(request, 'Casa eliminada correctamente.')
		return redirectar_a_registros('registrar_casa')
	form_class = CasaEdicionForm if casa else CasaForm
	form = form_class(request.POST or None, instance=casa)
	residentes_formset = ResidenteSecundarioFormSet(request.POST or None, prefix='secundarios')
	if request.method == 'POST' and form.is_valid() and residentes_formset.is_valid():
		principal = form.cleaned_data.get('id_residente')
		secundarios = [item.cleaned_data for item in residentes_formset if item.cleaned_data]
		identificadores_secundarios = set()
		hay_residentes_duplicados = principal is not None and any(
			item.get('residente_existente') == principal
			or item.get('cedula') == principal.cedula
			for item in secundarios
		)
		for item in secundarios:
			residente_existente = item.get('residente_existente')
			identificador = (
				('residente', residente_existente.pk)
				if residente_existente
				else ('cedula', str(item.get('cedula')))
			)
			if identificador in identificadores_secundarios:
				hay_residentes_duplicados = True
			identificadores_secundarios.add(identificador)

		if hay_residentes_duplicados:
			residentes_formset._non_form_errors = residentes_formset.error_class([
				'No agregue dos veces al mismo residente en esta casa.'
			])
		else:
			residentes_a_validar = [principal] if principal else []
			if casa and principal and casa.id_residente_id == principal.pk:
				residentes_a_validar = []
			for item in secundarios:
				residente_existente = item.get('residente_existente')
				if not residente_existente:
					continue
				ya_asociado_a_esta_casa = casa and (
					casa.id_residente_id == residente_existente.pk
					or CasaResidente.objects.filter(casa=casa, residente=residente_existente).exists()
				)
				if not ya_asociado_a_esta_casa:
					residentes_a_validar.append(residente_existente)
			residentes_por_confirmar = _residentes_con_otras_casas(residentes_a_validar, casa)
			if residentes_por_confirmar and request.POST.get('confirmar_residentes_otra_casa') != '1':
				casas = Casa.objects.select_related('id_residente', 'id_propietario').prefetch_related(
					'residentes_asociados__residente',
				).order_by('-id_casa')
				if casa_filtro.isdigit():
					casas = casas.filter(numero_casa=int(casa_filtro))
				return render(request, 'BD/casa.html', {
					'form': form,
					'residentes_formset': residentes_formset,
					'residentes_por_confirmar': residentes_por_confirmar,
					'casas': _casas_con_saldo_actual(casas),
					'casas_filtro': Casa.objects.order_by('numero_casa'),
					'casa_filtro': casa_filtro,
					'active_nav': 'casas',
					'casa_editando': casa,
				})

			# Casa, residentes asociados y eventos de auditoría se guardan juntos para evitar registros parciales.
			with transaction.atomic():
				if form.cleaned_data.get('crear_en_lote'):
					cantidad = int(form.cleaned_data['cantidad_casas'])
					numero_inicial = int(form.cleaned_data['numero_inicial'])
					try:
						casas_creadas = generar_casas_en_lote(
							cantidad=cantidad,
							numero_inicial=numero_inicial,
							residente=principal,
							propietario=None,
							cantidad_personas=int(form.cleaned_data.get('cantidad_personas') or 1),
							estado=form.cleaned_data.get('estado') or 'Activa',
							cartera=form.cleaned_data.get('cartera') or 0,
							cantidad_residentes=int(form.cleaned_data.get('cantidad_residentes') or 1),
						)
					except ValueError as exc:
						form.add_error('numero_inicial', str(exc))
						return render(request, 'BD/casa.html', {
							'form': form,
							'residentes_formset': residentes_formset,
							'casas': _casas_con_saldo_actual(Casa.objects.select_related('id_residente', 'id_propietario').prefetch_related('residentes_asociados__residente').order_by('-id_casa')),
							'active_nav': 'casas',
							'casa_editando': casa,
						})
					for casa_creada in casas_creadas:
						registrar_casa_historica(casa_creada.id_propietario, casa_creada.numero_casa)
						registrar_evento_bitacora(
							modulo='Casa',
							registro=f'Casa {casa_creada.numero_casa}',
							descripcion=f'Casa registrada con estado {casa_creada.estado}.',
							usuario=request.user,
							casa=casa_creada,
						)
						for item in secundarios:
							_asociar_residente_secundario(casa_creada, item, request.user)
						sincronizar_cantidad_residentes(casa_creada)
				else:
					nuevo_propietario = casa.id_propietario if casa else None
					if casa and casa.id_propietario_id != (nuevo_propietario.pk if nuevo_propietario else None):
						registrar_casa_historica(casa.id_propietario, casa.numero_casa)
					casa = form.save(commit=False)
					if es_casa_nueva and principal is None and secundarios:
						residente_principal = secundarios.pop(0)
						principal = _obtener_residente_secundario(residente_principal)
						registrar_evento_bitacora(
							modulo='Residente',
							registro=f'{principal.nombre} {principal.apellido}',
							descripcion=(
								'Residente existente asignado como principal.'
								if residente_principal.get('residente_existente')
								else 'Residente principal registrado.'
							),
							usuario=request.user,
						)
						casa.id_residente = principal
					casa.save()
					registrar_casa_historica(casa.id_propietario, casa.numero_casa)
					if es_casa_nueva:
						registrar_evento_bitacora(
							modulo='Casa',
							registro=f'Casa {casa.numero_casa}',
							descripcion=f'Casa registrada con estado {casa.estado}.',
							usuario=request.user,
							casa=casa,
						)
					for item in secundarios:
						_asociar_residente_secundario(casa, item, request.user)
					sincronizar_cantidad_residentes(casa)
			if form.cleaned_data.get('crear_en_lote'):
				messages.success(request, f'Las {cantidad} casas se registraron correctamente desde el número {numero_inicial}.')
			else:
				messages.success(request, 'Casa registrada correctamente.')
			return redirectar_a_registros('registrar_casa')
	casas = Casa.objects.select_related('id_residente', 'id_propietario').prefetch_related('residentes_asociados__residente').order_by('-id_casa')
	if casa_filtro.isdigit():
		casas = casas.filter(numero_casa=int(casa_filtro))
	casas = _casas_con_saldo_actual(casas)
	return render(request, 'BD/casa.html', {
		'form': form,
		'residentes_formset': residentes_formset,
		'casas': casas,
		'casas_filtro': Casa.objects.order_by('numero_casa'),
		'casa_filtro': casa_filtro,
		'active_nav': 'casas',
		'casa_editando': casa,
	})


# Gestiona la ficha del guardia y sincroniza su cuenta de usuario y estado de acceso.
@login_required(login_url='/login/')
@user_passes_test(es_administrador, login_url='/login/')
def registrar_guardia_view(request, guardia_id=None):
	guardia_existente = get_object_or_404(Guardia, pk=guardia_id) if guardia_id else None
	if request.method == 'POST' and request.POST.get('action') == 'delete':
		guardia = get_object_or_404(Guardia, pk=request.POST.get('guardia_id'))
		with transaction.atomic():
			if guardia.usuario_id:
				User.objects.filter(pk=guardia.usuario_id).update(is_active=False)
			guardia.delete()
		messages.success(request, 'Guardia eliminado correctamente.')
		return redirectar_a_registros('registrar_guardia')
	form = (GuardiaEdicionForm(request.POST or None, instance=guardia_existente) if guardia_existente else GuardiaForm(request.POST or None))
	if request.method == 'POST' and form.is_valid():
		with transaction.atomic():
			guardia = form.save(commit=False)
			if not guardia.usuario:
				usuario = User.objects.create_user(username=str(guardia.cedula), password=form.cleaned_data['password'], first_name=guardia.nombre, last_name=guardia.apellido)
				usuario.is_active = form.cleaned_data.get('activo', True)
				usuario.save(update_fields=('is_active',))
				registrar_evento_bitacora(
					modulo='Usuario',
					registro=usuario.get_full_name() or usuario.username,
					descripcion='Cuenta de usuario creada para el guardia.',
					usuario=request.user,
				)
				guardia.usuario = usuario
			else:
				guardia.usuario.username = str(guardia.cedula)
				guardia.usuario.first_name = guardia.nombre
				guardia.usuario.last_name = guardia.apellido
				guardia.usuario.is_active = form.cleaned_data.get('activo', True)
				if form.cleaned_data.get('password'):
					guardia.usuario.set_password(form.cleaned_data['password'])
				guardia.usuario.save()
			asignar_grupo_por_rol(guardia.usuario, 'guardia')
			guardia.save()
			if guardia_existente is None:
				registrar_evento_bitacora(
					modulo='Guardia',
					registro=f'{guardia.nombre} {guardia.apellido}',
					descripcion=f'Guardia registrado para el turno {guardia.turno or "sin turno"}.',
					usuario=request.user,
				)
		messages.success(request, 'Guardia actualizado correctamente.' if guardia_id else 'Guardia registrado correctamente.')
		return redirectar_a_registros('registrar_guardia')
	return render(request, 'BD/guardia.html', {
		'form': form,
		'guardias': Guardia.objects.order_by('-id_guardia'),
		'active_nav': 'guardias',
		'guardia_editando': guardia_existente,
	})


# Administra cuentas de usuario y sus roles, estados y operaciones de acceso.
@login_required(login_url='/login/')
@user_passes_test(es_administrador, login_url='/login/')
def usuarios_view(request):
	if request.method == 'POST' and request.POST.get('action') == 'toggle':
		usuario = get_object_or_404(User, pk=request.POST.get('usuario_id'))
		if usuario == request.user:
			mensaje = 'No puedes desactivar tu propia cuenta.'
			if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
				return JsonResponse({
					'success': False,
					'activo': usuario.is_active,
					'message': mensaje,
				}, status=400)
			messages.error(request, mensaje)
		else:
			usuario.is_active = not usuario.is_active
			usuario.save(update_fields=('is_active',))
			mensaje = 'Estado de la cuenta actualizado.'
			if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
				return JsonResponse({
					'success': True,
					'activo': usuario.is_active,
					'message': mensaje,
				})
			messages.success(request, mensaje)
		return redirectar_a_registros('usuarios')

	form = UsuarioForm(request.POST or None)
	if request.method == 'POST' and form.is_valid():
		data = form.cleaned_data
		with transaction.atomic():
			usuario = User.objects.create_user(
				username=data['username'],
				password=data['password'],
				first_name=data.get('first_name', ''),
				last_name=data.get('last_name', ''),
				email=data.get('correo_contacto') or data.get('propietario_correo') or '',
				is_staff=data['rol'] == 'administrador',
				is_active=data.get('activo', True),
			)
			registrar_evento_bitacora(
				modulo='Usuario',
				registro=usuario.get_full_name() or usuario.username,
				descripcion=f'Usuario registrado con rol {data["rol"]}.',
				usuario=request.user,
			)
			telefono_contacto = data.get('telefono_contacto') or data.get('telefono') or data.get('propietario_telefono') or ''
			PerfilUsuario.objects.create(usuario=usuario, telefono=telefono_contacto)
			asignar_grupo_por_rol(usuario, data['rol'])
			if data['rol'] == 'guardia':
				guardia = Guardia.objects.create(
					cedula=data['cedula'],
					nombre=data['first_name'],
					apellido=data['last_name'],
					telefono=data.get('telefono') or None,
					turno=data['turno'],
					usuario=usuario,
				)
				registrar_evento_bitacora(
					modulo='Guardia',
					registro=f'{guardia.nombre} {guardia.apellido}',
					descripcion=f'Guardia registrado para el turno {guardia.turno or "sin turno"}.',
					usuario=request.user,
				)
			elif data['rol'] == 'propietario':
				propietario = Propietario.objects.select_for_update().get(pk=data['propietario_existente'].pk)
				if propietario.usuario_id or propietario.casas.exists():
					raise ValueError('El propietario seleccionado ya tiene una cuenta o una casa asignada.')
				usuario.first_name = propietario.nombre
				usuario.last_name = propietario.apellido
				usuario.email = propietario.correo
				usuario.save(update_fields=('first_name', 'last_name', 'email'))
				PerfilUsuario.objects.filter(usuario=usuario).update(telefono=propietario.telefono)
				propietario.usuario = usuario
				propietario.save(update_fields=('usuario',))
				casas = list(Casa.objects.select_for_update().filter(pk__in=[casa.pk for casa in data['casas_propietario']]))
				if len(casas) != len(data['casas_propietario']) or any(casa.id_propietario_id for casa in casas):
					raise ValueError('Una de las casas seleccionadas ya fue asignada a otra cuenta.')
				Casa.objects.filter(pk__in=[casa.pk for casa in casas]).update(
					id_propietario=propietario,
				)
		messages.success(request, 'Cuenta de usuario creada correctamente.')
		return redirectar_a_registros('usuarios')

	estado_filtro = request.GET.get('estado', '')
	tipo_filtro = request.GET.get('tipo', '')
	usuarios = User.objects.filter(is_superuser=False).select_related('guardia').prefetch_related('groups').order_by('username')
	if estado_filtro == 'activo':
		usuarios = usuarios.filter(is_active=True)
	elif estado_filtro == 'inactivo':
		usuarios = usuarios.filter(is_active=False)
	else:
		estado_filtro = ''
	if tipo_filtro == 'administrador':
		usuarios = usuarios.filter(Q(is_staff=True) | Q(is_superuser=True))
	elif tipo_filtro == 'guardia':
		usuarios = usuarios.filter(guardia__isnull=False)
	elif tipo_filtro == 'propietario':
		usuarios = usuarios.filter(groups__name__iexact='Propietario')
	else:
		tipo_filtro = ''
	return render(request, 'BD/usuarios.html', {
		'form': form,
		'usuarios': usuarios,
		'estado_filtro': estado_filtro,
		'tipo_filtro': tipo_filtro,
		'active_nav': 'usuarios',
		'propietarios_disponibles': Propietario.objects.filter(
			usuario__isnull=True,
			casas__isnull=True,
		).distinct().order_by('apellido', 'nombre'),
	})


@login_required(login_url='/login/')
@user_passes_test(es_administrador, login_url='/login/')
def restablecer_contrasena_usuario_view(request, usuario_id):
	usuario = get_object_or_404(User, pk=usuario_id, is_superuser=False)
	form = AdminResetPasswordForm(request.user, usuario, request.POST or None)
	if request.method == 'POST' and form.is_valid():
		form.save()
		if usuario == request.user:
			update_session_auth_hash(request, usuario)
		registrar_evento_bitacora(
			modulo='Usuario',
			registro=usuario.get_full_name() or usuario.username,
			descripcion='Contrasena restablecida por un administrador.',
			usuario=request.user,
		)
		messages.success(request, f'Contraseña restablecida para {usuario.username}.')
		return redirectar_a_registros('usuarios')
	return render(request, 'BD/usuario_restablecer_contrasena.html', {
		'usuario_objetivo': usuario,
		'form': form,
		'active_nav': 'usuarios',
	})


# Registra o edita propietarios y sus cuentas asociadas, validando relaciones con viviendas.
@login_required(login_url='/login/')
@user_passes_test(es_administrador, login_url='/login/')
def registrar_propietario_view(request, propietario_id=None, residente_id=None):
	propietario = get_object_or_404(Propietario, pk=propietario_id) if propietario_id else None
	residente = get_object_or_404(Residente, pk=residente_id) if residente_id else None
	if request.method == 'POST' and request.POST.get('action') == 'delete':
		propietario = get_object_or_404(Propietario, pk=request.POST.get('propietario_id'))
		with transaction.atomic():
			if propietario.usuario_id:
				User.objects.filter(pk=propietario.usuario_id).update(is_active=False)
			propietario.delete()
		messages.success(request, 'Propietario eliminado correctamente.')
		return redirectar_a_registros('registrar_propietario')
	if request.method == 'POST' and request.POST.get('action') == 'delete_residente':
		residente = residente or get_object_or_404(Residente, pk=request.POST.get('residente_id'))
		residente.delete()
		messages.success(request, 'Residente eliminado correctamente.')
		return redirectar_a_registros('registrar_propietario')

	form_class = ResidenteDirectorioForm if residente else PropietarioForm
	form = form_class(request.POST or None, instance=residente or propietario)
	if request.method == 'POST' and form.is_valid() and residente:
		residente = form.save()
		messages.success(request, 'Residente actualizado correctamente.')
		return redirectar_a_registros('registrar_propietario')
	if request.method == 'POST' and form.is_valid() and not residente:
		if form.cleaned_data['rol'] == 'Residente' and propietario is None:
			data = form.cleaned_data
			residente = Residente.objects.create(
				cedula=data['cedula'],
				nombre=data['nombre'],
				apellido=data['apellido'],
				telefono=data.get('telefono') or None,
				correo=data.get('correo') or None,
			)
			registrar_evento_bitacora(
				modulo='Residente',
				registro=f'{residente.nombre} {residente.apellido}',
				descripcion=f'Residente registrado con cédula {residente.cedula}.',
				usuario=request.user,
			)
			messages.success(request, 'Residente registrado correctamente y disponible para asignarlo a una casa.')
			return redirectar_a_registros('registrar_propietario')
		propietario_guardado = form.save()
		if propietario is None:
			registrar_evento_bitacora(
				modulo='Propietario',
				registro=f'{propietario_guardado.nombre} {propietario_guardado.apellido}',
				descripcion=f'Propietario registrado con cédula {propietario_guardado.cedula}.',
				usuario=request.user,
			)
		messages.success(
			request,
			'Propietario actualizado correctamente.' if propietario else 'Propietario registrado correctamente.',
		)
		return redirectar_a_registros('registrar_propietario')
	rol_filtro = request.GET.get('rol', '').strip()
	cedula_filtro = request.GET.get('cedula', '').strip()
	casa_filtro = request.GET.get('casa', '').strip()
	propietarios = Propietario.objects.order_by('-id_propietario')
	if rol_filtro:
		propietarios = propietarios.filter(rol=rol_filtro)
	if cedula_filtro.isdigit():
		propietarios = propietarios.filter(cedula=int(cedula_filtro))
	if casa_filtro.isdigit():
		propietarios = propietarios.filter(casas__numero_casa=int(casa_filtro)).distinct()
	residentes = Residente.objects.order_by('apellido', 'nombre')
	if rol_filtro and rol_filtro != 'Residente':
		residentes = residentes.none()
	if cedula_filtro.isdigit():
		residentes = residentes.filter(cedula=int(cedula_filtro))
	if casa_filtro.isdigit():
		residentes = residentes.filter(
			Q(casas__numero_casa=int(casa_filtro))
			| Q(casas_secundarias__numero_casa=int(casa_filtro))
		).distinct()
	for propietario_item in propietarios:
		numeros_actuales = list(propietario_item.casas.values_list('numero_casa', flat=True))
		propietario_item.numeros_casas = sorted(set(numeros_actuales))
	for residente_item in residentes:
		numeros_actuales = list(residente_item.casas.values_list('numero_casa', flat=True))
		numeros_actuales.extend(residente_item.casas_secundarias.values_list('numero_casa', flat=True))
		residente_item.numeros_casas = sorted(set(numeros_actuales))
	return render(request, 'BD/propietario.html', {
		'form': form,
		'propietarios': propietarios,
		'residentes': residentes,
		'total_registros': propietarios.count() + residentes.count(),
		'propietario_editando': propietario,
		'residente_editando': residente,
		'rol_filtro': rol_filtro,
		'cedula_filtro': cedula_filtro,
		'casa_filtro': casa_filtro,
		'casas_filtro': Casa.objects.order_by('numero_casa'),
		'active_nav': 'propietarios',
	})
