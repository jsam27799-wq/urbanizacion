# Módulo: Coordina las solicitudes, reglas de negocio y respuestas de las pantallas de la aplicación.
import smtplib

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login as auth_login, logout
from django.contrib.auth.views import PasswordResetView
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.db.models import Case, DateTimeField, F, IntegerField, Sum, Value, When
from django.utils.timezone import make_aware
from datetime import datetime, time
from types import SimpleNamespace
from BD.forms import ResenaForm
from BD.models import Casa, Guardia, Notas, Novedad, Proceso, Paquete, Pago, Propietario, Resena, RegistroBitacora
from django.contrib.auth import update_session_auth_hash
from .forms import PerfilForm, PerfilPasswordForm, formatear_telefono_internacional
from .models import PerfilUsuario
from .permissions import puede_enviar_resena
from .manual_content import MANUAL_MODULES


class PasswordResetEmailView(PasswordResetView):
    def form_valid(self, form):
        smtp_backend = 'django.core.mail.backends.smtp.EmailBackend'
        if (
            settings.EMAIL_BACKEND == smtp_backend
            and (not settings.EMAIL_HOST_USER or not settings.EMAIL_HOST_PASSWORD)
        ):
            form.add_error(
                None,
                'El envío de correo no está configurado. Contacta al administrador del sistema.',
            )
            return self.form_invalid(form)

        try:
            return super().form_valid(form)
        except (OSError, smtplib.SMTPException):
            form.add_error(
                None,
                'No se pudo enviar el correo. Inténtalo más tarde o contacta al administrador del sistema.',
            )
            return self.form_invalid(form)


TIPOS_MOVIMIENTO = (
    'Visitante', 'Domicilio', 'Paquete', 'Pago', 'Nota',
    'Casa', 'Propietario', 'Residente', 'Guardia', 'Usuario', 'Novedad', 'Reseña',
)
# Presenta montos enteros con separador de miles local para paneles y listados.
def formatear_monto(monto):
    return f'{monto:,.0f}'.replace(',', '.')


# Reconoce administradores por sus privilegios de usuario o por pertenencia al grupo del mismo nombre.
def es_administrador(user):
    return user.is_staff or user.is_superuser or user.groups.filter(name__iexact='Administrador').exists()


# Comprueba si la cuenta pertenece al grupo de propietarios.
def es_propietario(user):
    return user.groups.filter(name__iexact='Propietario').exists()


def es_guardia(user):
    return user.groups.filter(name__iexact='Guardia').exists()


# Página principal
# Carga novedades y reseñas aprobadas y prepara el formulario público de reseñas.
def index(request):
    hoy = timezone.localdate()
    novedades = Novedad.objects.select_related('registrado_por').annotate(
        vencida=Case(
            When(fecha_suceso__date__lt=hoy, then=Value(1)),
            default=Value(0),
            output_field=IntegerField(),
        ),
        fecha_proxima=Case(
            When(fecha_suceso__date__gte=hoy, then=F('fecha_suceso')),
            output_field=DateTimeField(),
        ),
        fecha_vencida=Case(
            When(fecha_suceso__date__lt=hoy, then=F('fecha_suceso')),
            output_field=DateTimeField(),
        ),
    ).order_by('vencida', 'fecha_proxima', '-fecha_vencida', 'id_novedad')
    resenas = Resena.objects.filter(aprobada=True).order_by('-fecha_creacion', '-id_resena')
    perfil_contacto = PerfilUsuario.objects.filter(usuario=request.user).first() if request.user.is_authenticated else None
    telefono_formateado = formatear_telefono_internacional(perfil_contacto.telefono) if perfil_contacto else ''
    return render(request, "core/index.html", {
        'novedades': novedades,
        'resenas': resenas,
        'resena_form': ResenaForm(),
        'puede_enviar_resena': puede_enviar_resena(request.user),
        'perfil_contacto': perfil_contacto,
        'telefono_formateado': telefono_formateado,
    })


def manual_usuario_view(request):
    return render(request, 'core/manual_usuario.html')


@login_required(login_url='/login/')
def manual_roles_view(request):
    administrador = es_administrador(request.user)
    if administrador:
        manual_roles = ('administrador', 'guardia', 'propietario')
        manual_titulo = 'Manual de administrador'
    elif es_guardia(request.user):
        manual_roles = ('guardia',)
        manual_titulo = 'Manual de guardia'
    elif es_propietario(request.user):
        manual_roles = ('propietario',)
        manual_titulo = 'Manual de propietario'
    else:
        raise PermissionDenied

    return render(request, 'core/manual_roles.html', {
        'manual_roles': manual_roles,
        'manual_es_administrador': administrador,
        'manual_titulo': manual_titulo,
        'manual_capitulos': MANUAL_MODULES[manual_roles[0]],
    })


# Login
# Autentica las credenciales y dirige al propietario a pagos o al resto de usuarios al panel.
def login(request):
    is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest'

    if request.user.is_authenticated:
        if es_propietario(request.user):
            return redirect('registrar_pago')
        return redirect('dashboard')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')

        user = authenticate(request, username=username, password=password)

        if user is not None:
            auth_login(request, user)
            redirect_url = reverse('registrar_pago' if es_propietario(user) else 'dashboard')
            if is_ajax:
                return JsonResponse({'success': True, 'redirect_url': redirect_url})
            return redirect(redirect_url)

        if is_ajax:
            return JsonResponse({
                'success': False,
                'message': 'Usuario o contraseña incorrectos',
            }, status=400)
        messages.error(request, 'Usuario o contraseña incorrectos')

    return render(request, 'core/login.html')


# Cierra la sesión autenticada y vuelve a la pantalla de inicio de sesión.
@login_required(login_url='/login/')
def logout_view(request):
    logout(request)
    return redirect('login')


# Actualiza datos de contacto sincronizados con la ficha de personal y cambia la contraseña sin cerrar sesión.
@login_required(login_url='/login/')
def perfil_view(request):
    perfil_contacto, _ = PerfilUsuario.objects.get_or_create(usuario=request.user)
    perfil_form = PerfilForm(request.POST or None, instance=request.user, perfil=perfil_contacto)
    password_form = PerfilPasswordForm(request.user, request.POST or None)
    if request.method == 'POST':
        accion = request.POST.get('accion')
        if accion == 'perfil' and perfil_form.is_valid():
            # Sincroniza teléfono y correo con los registros de guardia o propietario vinculados a la cuenta.
            perfil_form.save()
            telefono = perfil_form.cleaned_data.get('telefono', '')
            Guardia.objects.filter(usuario=request.user).update(telefono=telefono or None)
            Propietario.objects.filter(usuario=request.user).update(
                telefono=telefono,
                correo=perfil_form.cleaned_data.get('email', ''),
            )
            messages.success(request, 'Datos personales actualizados correctamente.')
            return redirect('perfil')
        if accion == 'password' and password_form.is_valid():
            usuario = password_form.save()
            # Mantiene la sesión autenticada después de que Django cambie el hash de contraseña.
            update_session_auth_hash(request, usuario)
            messages.success(request, 'Contraseña actualizada correctamente.')
            return redirect('perfil')
    return render(request, 'core/perfil.html', {
        'perfil_form': perfil_form,
        'password_form': password_form,
    })


# Une procesos, pagos y otros registros en una estructura común para mostrar el historial cronológico.
def obtener_movimientos():
    movimientos = []

    # Se cargan las relaciones usadas por el detalle para evitar consultas repetidas al recorrer los procesos.
    procesos = Proceso.objects.select_related(
        'id_guardia', 'id_casa', 'id_visitante', 'id_domicilio', 'id_paquete',
        'id_visitante__residente_secundario', 'id_visitante__propietario_autorizador',
        'id_domicilio__residente_secundario', 'id_domicilio__propietario_autorizador',
        'id_paquete__residente_secundario', 'id_paquete__propietario_autorizador',
    ).all()
    for proceso in procesos:
        detalles = []
        if proceso.tipo == 'Visitante' and proceso.id_visitante:
            visitante = proceso.id_visitante
            autorizante = visitante.residente_secundario or visitante.propietario_autorizador
            detalles = [
                ('Cédula', visitante.cedula),
                ('Tipo de visitante', visitante.tipo_v or 'Sin especificar'),
                ('Entrada', 'Vehicular' if visitante.vehiculo_trae == 'SI' else 'Peatonal'),
                ('Conductor', visitante.conductor or 'No aplica'),
                ('Personas', visitante.cantidad_personas),
                ('Autoriza', autorizante or 'Sin autorizante'),
                ('Autorización', 'Sí' if visitante.autoriza == 'SI' else 'No'),
            ]
        elif proceso.tipo == 'Domicilio' and proceso.id_domicilio:
            domicilio = proceso.id_domicilio
            autorizante = domicilio.residente_secundario or domicilio.propietario_autorizador
            detalles = [
                ('Teléfono', domicilio.telefono_negocio),
                ('Descripción', domicilio.descripcion_negocio or 'Sin descripción'),
                ('Vehículo', domicilio.vehiculo_tipo or 'Sin vehículo'),
                ('Placa', domicilio.vehiculo_placa or 'Sin placa'),
                ('Persona autorizante', autorizante or 'Sin seleccionar'),
                ('Autoriza', 'Sí' if domicilio.autoriza == 'SI' else 'No'),
            ]
        elif proceso.tipo == 'Paquete' and proceso.id_paquete:
            paquete = proceso.id_paquete
            contacto = paquete.residente_secundario or paquete.propietario_autorizador
            detalles = [
                ('Transportadora', paquete.transportadora),
                ('Teléfono', paquete.telefono_t or 'Sin teléfono'),
                ('Guía', paquete.guia or 'Sin guía'),
                ('Tipo de paquete', paquete.desc_tipo or 'Sin descripción'),
                ('Persona de contacto', contacto or 'Sin seleccionar'),
                ('Llamada', 'Sí contestó' if paquete.llamada == 'CONTESTO' else 'No contestó'),
                ('Información adicional', paquete.informacion_adicional or 'Sin nota'),
            ]
        movimientos.append(SimpleNamespace(
            id=f'proceso-{proceso.id_proceso}',
            fecha=proceso.fecha,
            orden=proceso.fecha,
            tipo=proceso.tipo,
            accion='Registro',
            nombre=proceso.nombre,
            casa=proceso.id_casa,
            guardia=proceso.id_guardia,
            vehiculo_tipo=proceso.vehiculo_tipo,
            placa=proceso.placa,
            estado=proceso.estado,
            descripcion=proceso.descripcion,
            detalles=detalles,
        ))

    for pago in Pago.objects.select_related('id_casa').all():
        fecha_pago = make_aware(datetime.combine(pago.fecha, time.min))
        movimientos.append(SimpleNamespace(
            id=f'pago-{pago.id_pago}',
            fecha=fecha_pago,
            orden=fecha_pago,
            tipo='Pago',
            accion='Registro',
            nombre='Pago de administración',
            casa=pago.id_casa,
            guardia=None,
            vehiculo_tipo=None,
            placa=None,
            estado=pago.estado,
            descripcion=f'Valor pagado: ${formatear_monto(pago.valor)}',
            detalles=[
                ('Valor', f'${formatear_monto(pago.valor)}'),
                ('Estado', pago.estado),
                ('Comprobante', 'Disponible' if pago.evidencia else 'Sin comprobante'),
            ],
        ))

    for nota in Notas.objects.select_related('id_guardia').all():
        movimientos.append(SimpleNamespace(
            id=f'nota-{nota.id_nota}',
            fecha=nota.fecha,
            orden=nota.fecha,
            tipo='Nota',
            accion='Registro',
            nombre=f'{nota.nombre} {nota.apellido}',
            casa=None,
            guardia=nota.id_guardia,
            vehiculo_tipo=None,
            placa=None,
            estado='Registrada',
            descripcion=nota.nota,
            detalles=[
                ('Teléfono', nota.telefono or 'Sin teléfono'),
                ('Nota', nota.nota),
                ('Evidencia', 'Disponible' if nota.evidencia else 'Sin evidencia'),
            ],
        ))

    for novedad in Novedad.objects.select_related('registrado_por').all():
        responsable = novedad.registrado_por
        movimientos.append(SimpleNamespace(
            id=f'novedad-{novedad.pk}',
            fecha=novedad.fecha_creacion,
            orden=novedad.fecha_creacion,
            tipo='Novedad',
            accion='Registro',
            nombre=novedad.titulo,
            casa=None,
            guardia=(
                SimpleNamespace(nombre=responsable.first_name, apellido=responsable.last_name)
                if responsable else None
            ),
            vehiculo_tipo=None,
            placa=None,
            estado='Registrada',
            descripcion=novedad.nota,
            detalles=[
                ('Tipo de novedad', novedad.tipo),
                ('Fecha del suceso', novedad.fecha_suceso.strftime('%d/%m/%Y %H:%M')),
            ],
        ))

    for resena in Resena.objects.select_related('usuario').all():
        responsable = resena.usuario
        movimientos.append(SimpleNamespace(
            id=f'resena-{resena.pk}',
            fecha=resena.fecha_creacion,
            orden=resena.fecha_creacion,
            tipo='Reseña',
            accion='Registro',
            nombre=resena.nombre,
            casa=None,
            guardia=(
                SimpleNamespace(nombre=responsable.first_name, apellido=responsable.last_name)
                if responsable else None
            ),
            vehiculo_tipo=None,
            placa=None,
            estado='Aprobada' if resena.aprobada else 'Pendiente',
            descripcion=f'Calificación: {resena.calificacion} de 5 estrellas.',
            detalles=[
                ('Calificación', f'{resena.calificacion} de 5 estrellas'),
                ('Rol', resena.rol_usuario or 'No especificado'),
            ],
        ))

    for registro in RegistroBitacora.objects.select_related('casa', 'usuario').all():
        nombre_usuario = (
            registro.usuario.get_full_name() or registro.usuario.username
            if registro.usuario else 'No disponible'
        )
        guardia = (
            SimpleNamespace(
                nombre=registro.usuario.first_name,
                apellido=registro.usuario.last_name,
            )
            if registro.usuario else None
        )
        movimientos.append(SimpleNamespace(
            id=f'bitacora-{registro.pk}',
            fecha=registro.fecha,
            orden=registro.fecha,
            tipo=registro.modulo,
            accion=registro.accion,
            nombre=registro.registro,
            casa=registro.casa,
            guardia=guardia,
            vehiculo_tipo=None,
            placa=None,
            estado='Registrado',
            descripcion=registro.descripcion,
            detalles=[
                ('Módulo', registro.modulo),
                ('Registro', registro.registro),
                ('Registrado por', nombre_usuario),
            ],
        ))

    return sorted(movimientos, key=lambda movimiento: movimiento.fecha, reverse=True)


# Aplica filtros válidos de casa y tipo a la lista de movimientos y devuelve los valores seleccionados.
def filtrar_movimientos(movimientos, request):
    casa = request.GET.get('casa', '')
    tipo = request.GET.get('tipo', '')
    if casa.isdigit():
        movimientos = [movimiento for movimiento in movimientos if movimiento.casa and movimiento.casa.pk == int(casa)]
    if tipo in TIPOS_MOVIMIENTO:
        movimientos = [movimiento for movimiento in movimientos if movimiento.tipo == tipo]
    return movimientos, casa, tipo

#ADMINISTRADOR
# Calcula indicadores del panel y limita los movimientos visibles según el rol del usuario.
@login_required(login_url='/login/')
def dashboard_view(request):
    # Total de casas registradas
    total_casas = Casa.objects.count()

    # Movimientos / Procesos registrados el día de hoy
    hoy = timezone.now().date()
    ingresos_hoy = Proceso.objects.filter(fecha__date=hoy).count()

    # Paquetes registrados en el sistema (puedes ajustar el filtro si manejas un estado "Entregado")
    paquetes_pendientes = Paquete.objects.count()

    # Suma los pagos confirmados del mes en curso para el indicador financiero del panel.
    pagos_mes = Pago.objects.filter(
        estado__iexact='Pagado',
        fecha__year=hoy.year,
        fecha__month=hoy.month,
    ).aggregate(total=Sum('valor'))['total'] or 0.00

    movimientos = obtener_movimientos()
    if not es_administrador(request.user):
        movimientos = [movimiento for movimiento in movimientos if movimiento.tipo != 'Pago']
    movimientos, casa_filtro, tipo_filtro = filtrar_movimientos(movimientos, request)
    ultimos_procesos = movimientos[:10]

    context = {
        'total_casas': total_casas,
        'ingresos_hoy': ingresos_hoy,
        'paquetes_pendientes': paquetes_pendientes,
        'pagos_mes': pagos_mes,
        'pagos_mes_formateado': formatear_monto(pagos_mes),
        'ultimos_procesos': ultimos_procesos,
        'casas_filtro': Casa.objects.order_by('numero_casa'),
        'casa_filtro': casa_filtro,
        'tipo_filtro': tipo_filtro,
        'tipos_movimiento': TIPOS_MOVIMIENTO,
        'active_nav': 'dashboard',
        'es_administrador': es_administrador(request.user),
    }

    return render(request, 'BD/dashboard.html', context)
# Redirige el acceso del guardia al panel compartido de la aplicación.
@login_required(login_url='/login/')
def dashboard_view_guardia(request):
    return redirect('dashboard')


# Filtra el historial unificado por fechas, día, mes, año, casa y tipo antes de renderizarlo.
@login_required(login_url='/login/')
def movimientos_view(request):
    procesos = obtener_movimientos()
    if not es_administrador(request.user):
        procesos = [movimiento for movimiento in procesos if movimiento.tipo != 'Pago']
    filtros = {
        'desde': request.GET.get('desde', ''),
        'hasta': request.GET.get('hasta', ''),
        'dia': request.GET.get('dia', ''),
        'mes': request.GET.get('mes', ''),
        'ano': request.GET.get('ano', ''),
        'casa': request.GET.get('casa', ''),
        'tipo': request.GET.get('tipo', ''),
    }
    procesos, filtros['casa'], filtros['tipo'] = filtrar_movimientos(procesos, request)
    # Convierte la fecha del movimiento a date para poder aplicar los filtros.
    def fecha_del_movimiento(movimiento):
        return movimiento.fecha.date() if isinstance(movimiento.fecha, datetime) else movimiento.fecha

    if filtros['desde']:
        procesos = [movimiento for movimiento in procesos if fecha_del_movimiento(movimiento) >= datetime.strptime(filtros['desde'], '%Y-%m-%d').date()]
    if filtros['hasta']:
        procesos = [movimiento for movimiento in procesos if fecha_del_movimiento(movimiento) <= datetime.strptime(filtros['hasta'], '%Y-%m-%d').date()]
    if filtros['dia']:
        procesos = [movimiento for movimiento in procesos if fecha_del_movimiento(movimiento) == datetime.strptime(filtros['dia'], '%Y-%m-%d').date()]
    if filtros['mes'] and '-' in filtros['mes']:
        ano, mes = filtros['mes'].split('-', 1)
        procesos = [movimiento for movimiento in procesos if fecha_del_movimiento(movimiento).year == int(ano) and fecha_del_movimiento(movimiento).month == int(mes)]
    if filtros['ano']:
        procesos = [movimiento for movimiento in procesos if fecha_del_movimiento(movimiento).year == int(filtros['ano'])]
    return render(request, 'BD/movimientos.html', {'procesos': procesos, 'filtros': filtros, 'casas_filtro': Casa.objects.order_by('numero_casa'), 'tipos_movimiento': TIPOS_MOVIMIENTO, 'active_nav': 'dashboard'})