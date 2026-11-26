# Módulo: Agrupa pruebas automatizadas de los comportamientos y reglas de la aplicación.
import sqlite3
import json
import tempfile
import zipfile
from contextlib import closing
from io import BytesIO, StringIO
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from unittest import skipUnless
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.db import connection
from django.test import RequestFactory, TestCase, TransactionTestCase, override_settings
from django.contrib.auth.models import Group, User
from django.urls import reverse
from django.utils import timezone
from openpyxl import load_workbook

from BD.forms import CasaEdicionForm, CasaForm, ConfiguracionCarteraForm, ConfiguracionCopiasSeguridadForm, DomicilioForm, DomicilioIngresoForm, GuardiaEdicionForm, GuardiaForm, NotaForm, NovedadForm, PagoForm, PaqueteForm, PaqueteIngresoForm, PropietarioForm, ResenaForm, ResidenteForm, ResidenteSecundarioFormSet, UsuarioForm, VisitanteIngresoForm
from BD.models import Casa, CasaResidente, ConfiguracionCartera, ConfiguracionCopiasSeguridad, CopiaSeguridad, Domicilio, Guardia, Notas, Novedad, Paquete, Pago, Proceso, Propietario, RegistroBitacora, Resena, Residente, Visitante
from BD.cartera import aplicar_mora_vencida, saldos_actuales_por_casa
from BD.reportes import build_payment_summary, build_report_rows
from BD.views import generar_casas_en_lote


class FormularioValidacionTests(TestCase):
    def test_nota_nueva_exige_telefono_guardia_y_evidencia(self):
        formulario = NotaForm(data={})

        self.assertFalse(formulario.is_valid())
        for campo in ('nombre', 'apellido', 'telefono', 'nota', 'evidencia', 'id_guardia'):
            with self.subTest(campo=campo):
                self.assertIn(campo, formulario.errors)

    def test_nota_valida_guarda_campos_requeridos_y_evidencia(self):
        guardia = Guardia.objects.create(
            cedula=887700,
            nombre='Lucia',
            apellido='Mora',
            telefono='3001234567',
            turno='Mañana',
        )
        formulario = NotaForm(
            data={
                'nombre': 'Ana',
                'apellido': 'Perez',
                'telefono': '3007654321',
                'nota': 'Dejó un mensaje',
                'id_guardia': str(guardia.pk),
            },
            files={'evidencia': SimpleUploadedFile('nota.txt', b'evidencia')},
        )

        self.assertTrue(formulario.is_valid(), formulario.errors)

    def test_vista_notas_presenta_errores_y_guarda_un_registro_completo(self):
        administrador = User.objects.create_user(
            username='admin-notas-validacion',
            password='Clave-segura1!',
            is_staff=True,
        )
        guardia = Guardia.objects.create(
            cedula=887702,
            nombre='Lucia',
            apellido='Mora',
            telefono='3001234567',
            turno='Mañana',
        )
        self.client.force_login(administrador)
        url = reverse('registrar_nota')

        respuesta_invalida = self.client.post(url, {
            'nombre': '',
            'apellido': '',
            'telefono': '',
            'nota': '',
            'id_guardia': '',
        })

        self.assertEqual(respuesta_invalida.status_code, 200)
        self.assertIn('telefono', respuesta_invalida.context['form'].errors)
        self.assertIn('id_guardia', respuesta_invalida.context['form'].errors)

        with tempfile.TemporaryDirectory() as directorio_media:
            with override_settings(MEDIA_ROOT=directorio_media):
                respuesta_valida = self.client.post(url, {
                    'nombre': 'Ana',
                    'apellido': 'Perez',
                    'telefono': '3007654321',
                    'nota': 'Dejó un mensaje',
                    'id_guardia': str(guardia.pk),
                    'evidencia': SimpleUploadedFile('nota.txt', b'evidencia'),
                })

        self.assertRedirects(respuesta_valida, f'{url}?registros=1')
        nota = Notas.objects.get(nombre='Ana')
        self.assertEqual(nota.telefono, '3007654321')
        self.assertEqual(nota.id_guardia, guardia)
        self.assertTrue(nota.evidencia)

    def test_nota_rechaza_telefono_con_digitos_no_ascii(self):
        formulario = NotaForm(
            data={
                'nombre': 'Ana',
                'apellido': 'Perez',
                'telefono': '１２３４５６７８',
                'nota': 'Dejó un mensaje',
                'id_guardia': '1',
            },
            files={'evidencia': SimpleUploadedFile('nota.txt', b'evidencia')},
        )

        self.assertFalse(formulario.is_valid())
        self.assertIn('telefono', formulario.errors)

    def test_guardia_exige_confirmacion_de_contrasena_igual(self):
        formulario = GuardiaForm(data={
            'cedula': '887701',
            'nombre': 'Lucia',
            'apellido': 'Mora',
            'telefono': '3001234567',
            'turno': 'Mañana',
            'password': 'Clave-segura1!',
            'password_confirmacion': 'Clave-distinta1!',
        })

        self.assertFalse(formulario.is_valid())
        self.assertIn('password_confirmacion', formulario.errors)

    def test_usuario_rechaza_telefono_con_digitos_no_ascii(self):
        formulario = UsuarioForm(data={
            'username': 'admin-validacion',
            'first_name': 'Ana',
            'last_name': 'Perez',
            'rol': 'administrador',
            'correo_contacto': 'ana@gmail.com',
            'telefono_contacto': '１２３４５６７８',
            'password': 'Clave-segura1!',
            'password_confirmacion': 'Clave-segura1!',
        })

        self.assertFalse(formulario.is_valid())
        self.assertIn('telefono_contacto', formulario.errors)


class DirectorioResidentesCorreoTests(TestCase):
    def setUp(self):
        administrador = User.objects.create_user(
            username='admin-residente-correo',
            password='Clave-segura1!',
            is_staff=True,
        )
        self.client.force_login(administrador)

    def test_correo_residente_se_guarda_edita_y_se_muestra_en_registros(self):
        url = reverse('registrar_propietario')
        response = self.client.post(url, {
            'cedula': '880101',
            'nombre': 'Ana',
            'apellido': 'Rios',
            'telefono': '3001234501',
            'correo': 'ANA.RIOS@outlook.com',
            'rol': 'Residente',
            'rol_otro': '',
        })

        self.assertRedirects(response, f'{url}?registros=1')
        residente = Residente.objects.get(cedula=880101)
        self.assertEqual(residente.correo, 'ana.rios@outlook.com')
        pagina_registros = self.client.get(url)
        self.assertContains(pagina_registros, 'ana.rios@outlook.com')
        self.assertContains(pagina_registros, 'lang="es"')
        self.assertContains(pagina_registros, 'Este campo es obligatorio.')

        url_edicion = reverse('editar_residente_directorio', args=[residente.pk])
        self.assertContains(self.client.get(url_edicion), 'value="ana.rios@outlook.com"')
        response = self.client.post(url_edicion, {
            'cedula': '880101',
            'nombre': 'Ana',
            'apellido': 'Rios',
            'telefono': '3001234501',
            'correo': 'ana.nuevo@outlook.com',
        })

        self.assertRedirects(response, f'{url}?registros=1')
        residente.refresh_from_db()
        self.assertEqual(residente.correo, 'ana.nuevo@outlook.com')
        self.assertContains(self.client.get(url), 'ana.nuevo@outlook.com')


# Agrupa pruebas automatizadas relacionadas con casa lote pruebas.
class FiltrosListadoTests(TestCase):
    def setUp(self):
        administrador = User.objects.create_user(username='admin-filtros', password='Clave-segura1!', is_staff=True)
        self.client.force_login(administrador)

    def test_filtro_visitantes_por_documento_entrada_y_casa(self):
        guardia = Guardia.objects.create(cedula=880101, nombre='Ana', apellido='Rios', telefono='3001234501')
        casa_filtrada = Casa.objects.create(numero_casa=901, cantidad_personas=2, cantidad_residentes=1, estado='Ocupada')
        otra_casa = Casa.objects.create(numero_casa=902, cantidad_personas=2, cantidad_residentes=1, estado='Ocupada')
        visitante = Visitante.objects.create(nombre='Luis', apellido='Perez', cedula='123456', vehiculo_trae='SI')
        Visitante.objects.create(nombre='Marta', apellido='Gil', cedula='789012', vehiculo_trae='NO')
        Proceso.objects.create(
            tipo='Visitante', nombre='Luis Perez', fecha=timezone.now(),
            id_guardia=guardia, id_casa=casa_filtrada, id_visitante=visitante,
        )
        response = self.client.get(reverse('registrar_visitante'), {
            'registros': '1', 'documento': '123', 'entrada': 'SI', 'casa': str(casa_filtrada.pk),
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context['visitantes'].values_list('pk', flat=True)), [visitante.pk])

    def test_formulario_visitante_incluye_validacion_en_espanol(self):
        response = self.client.get(reverse('registrar_visitante'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<html lang="es">')
        self.assertContains(response, 'Selecciona una opción.')
        self.assertContains(response, 'Este campo es obligatorio.')

    def test_visitante_solo_edita_estado_y_registra_hora_de_salida(self):
        guardia = Guardia.objects.create(
            cedula=880111,
            nombre='Lucia',
            apellido='Mora',
            telefono='3001234511',
            turno='Mañana',
        )
        casa = Casa.objects.create(
            numero_casa=911,
            cantidad_personas=2,
            cantidad_residentes=1,
            estado='Ocupada',
        )
        visitante = Visitante.objects.create(
            nombre='Luis',
            apellido='Perez',
            cedula='123456',
            vehiculo_trae='NO',
            tipo_v='Familiar',
        )
        proceso = Proceso.objects.create(
            tipo='Visitante',
            nombre='Luis Perez',
            fecha=timezone.now(),
            id_guardia=guardia,
            id_casa=casa,
            id_visitante=visitante,
        )
        url_edicion = reverse('editar_visitante', args=[visitante.pk])

        respuesta_edicion = self.client.get(url_edicion)
        self.assertEqual(respuesta_edicion.status_code, 200)
        self.assertEqual(list(respuesta_edicion.context['form'].fields), ['estado'])
        self.assertContains(respuesta_edicion, 'Ingresado')
        self.assertContains(respuesta_edicion, 'Salido')

        respuesta_guardado = self.client.post(url_edicion, {
            'estado': 'SALIDO',
            'nombre': 'Nombre alterado',
            'cedula': '999999',
        })

        self.assertRedirects(
            respuesta_guardado,
            f"{reverse('registrar_visitante')}?registros=1",
        )
        proceso.refresh_from_db()
        visitante.refresh_from_db()
        self.assertEqual(proceso.estado, 'SALIDO')
        self.assertIsNotNone(proceso.fecha_salida)
        self.assertEqual(visitante.nombre, 'Luis')
        self.assertEqual(visitante.cedula, '123456')

        respuesta_registros = self.client.get(reverse('registrar_visitante'))
        self.assertContains(respuesta_registros, 'Hora de salida')
        self.assertContains(
            respuesta_registros,
            timezone.localtime(proceso.fecha_salida).strftime('%d/%m/%Y %H:%M'),
        )

    def test_eliminar_visitante_desde_el_listado(self):
        visitante = Visitante.objects.create(
            nombre='Prueba',
            apellido='Temporal',
            cedula='9990000002',
            vehiculo_trae='NO',
        )

        response = self.client.post(reverse('registrar_visitante'), {
            'action': 'delete',
            'visitante_id': visitante.pk,
        })

        self.assertRedirects(response, f"{reverse('registrar_visitante')}?registros=1")
        self.assertFalse(Visitante.objects.filter(pk=visitante.pk).exists())

    def test_filtro_usuarios_por_estado_y_tipo(self):
        guardia = User.objects.create_user(username='guardia-filtro', password='clave', is_active=True)
        Guardia.objects.create(cedula=880102, nombre='Eva', apellido='Rios', usuario=guardia)
        User.objects.create_user(username='propietario-filtro', password='clave', is_active=False).groups.add(
            Group.objects.get_or_create(name='Propietario')[0]
        )

        response = self.client.get(reverse('usuarios'), {
            'registros': '1', 'tipo': 'guardia', 'estado': 'activo',
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context['usuarios'].values_list('username', flat=True)), ['guardia-filtro'])

    def test_filtro_notas_por_fecha(self):
        guardia = Guardia.objects.create(cedula=880103, nombre='Ana', apellido='Rios', telefono='3001234503')
        fecha_filtrada = timezone.make_aware(datetime(2026, 5, 10, 12))
        nota = Notas.objects.create(nombre='Luis', apellido='Perez', nota='Llamar', fecha=fecha_filtrada, id_guardia=guardia)
        Notas.objects.create(
            nombre='Marta', apellido='Gil', nota='Otra nota',
            fecha=timezone.make_aware(datetime(2026, 5, 11, 12)), id_guardia=guardia,
        )

        response = self.client.get(reverse('registrar_nota'), {'registros': '1', 'fecha': '2026-05-10'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context['notas'].values_list('pk', flat=True)), [nota.pk])

    def test_filtro_resenas_por_estado_y_calificacion(self):
        aprobada = Resena.objects.create(nombre='Ana', comentario='Excelente', calificacion=5, aprobada=True)
        Resena.objects.create(nombre='Luis', comentario='Buena', calificacion=5, aprobada=False)
        Resena.objects.create(nombre='Eva', comentario='Regular', calificacion=3, aprobada=True)

        response = self.client.get(reverse('resenas'), {'estado': 'aprobada', 'calificacion': '5'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context['resenas'].values_list('pk', flat=True)), [aprobada.pk])


class ResenaAjaxTests(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user(username='residente-resena', password='Clave-segura1!')
        grupo, _ = Group.objects.get_or_create(name='Residente')
        self.usuario.groups.add(grupo)
        self.client.force_login(self.usuario)

    def test_resena_ajax_valida_se_guarda_sin_redireccion(self):
        response = self.client.post(
            reverse('enviar_resena'),
            {'nombre': 'Ana', 'calificacion': '5', 'comentario': 'Excelente servicio.'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            'success': True,
            'message': 'Tu reseña fue enviada para revisión.',
        })
        self.assertTrue(Resena.objects.filter(usuario=self.usuario, aprobada=False).exists())

    def test_resena_ajax_invalida_devuelve_error_sin_redireccion(self):
        response = self.client.post(
            reverse('enviar_resena'),
            {'nombre': '', 'calificacion': '', 'comentario': ''},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()['success'])
        self.assertTrue(response.json()['message'])
        self.assertFalse(Resena.objects.filter(usuario=self.usuario).exists())


class CasaLoteTests(TestCase):
    # Verifica el comportamiento de nombres personalizados de estado aparecen en selectores sin cambiar valores y sus condiciones relevantes.
    def test_nombres_personalizados_de_estado_aparecen_en_selectores_sin_cambiar_valores(self):
        configuracion = ConfiguracionCartera.objects.get(pk=1)
        configuracion.estados_visualizacion = {
            'casa': {
                'Para Arrendar': {'nombre': 'Para Arrendarr', 'color': '#123456'},
            },
            'paquete': {
                'PENDIENTE': {'nombre': 'En recepción', 'color': '#123456'},
            },
            'pago': {
                'Pendiente': {'nombre': 'Por confirmar', 'color': '#123456'},
            },
        }
        configuracion.save(update_fields=('estados_visualizacion',))

        formulario_casa = CasaForm()
        formulario_paquete = PaqueteIngresoForm()
        formulario_pago = PagoForm()
        formulario_casa_post = CasaForm(data={
            'numero_casa': '990',
            'cantidad_personas': '2',
            'cantidad_residentes': '1',
            'estado': 'Para Arrendar',
            'estado_otro': '',
            'cartera': '0',
            'id_residente': '',
        })

        self.assertIn(('Para Arrendar', 'Para Arrendarr'), formulario_casa.fields['estado'].choices)
        self.assertIn(('PENDIENTE', 'En recepción'), formulario_paquete.fields['estado_paquete'].choices)
        self.assertIn(('Pendiente', 'Por confirmar'), formulario_pago.fields['estado'].choices)
        self.assertTrue(formulario_casa_post.is_valid(), formulario_casa_post.errors)
        self.assertEqual(formulario_casa_post.cleaned_data['estado'], 'Para Arrendar')

    # Verifica el comportamiento de formulario casa no permite asignar propietario y sus condiciones relevantes.
    def test_formulario_casa_no_permite_asignar_propietario(self):
        self.assertNotIn('id_propietario', CasaForm().fields)

    # Verifica el comportamiento de edición casa conserva propietario asignado y sus condiciones relevantes.
    def test_editar_casa_conserva_propietario_asignado(self):
        propietario = Propietario.objects.create(
            cedula=990001,
            nombre='Ana',
            apellido='Perez',
            telefono='3000000001',
            correo='ana.perez@gmail.com',
            rol='Propietario',
        )
        casa = Casa.objects.create(
            numero_casa=503,
            cantidad_personas=2,
            cantidad_residentes=1,
            estado='Activa',
            id_propietario=propietario,
        )

        formulario = CasaEdicionForm(data={
            'numero_casa': '503',
            'cantidad_personas': '3',
            'cantidad_residentes': '1',
            'estado': 'Ocupada',
            'estado_otro': '',
            'cartera': '0',
            'id_residente': '',
        }, instance=casa)

        self.assertTrue(formulario.is_valid(), formulario.errors)
        casa_editada = formulario.save()
        self.assertEqual(casa_editada.id_propietario_id, propietario.pk)


    # Verifica el comportamiento de casas se pueden filtrado por numero y sus condiciones relevantes.
    def test_casas_se_pueden_filtrar_por_numero(self):
        administrador = User.objects.create_user(
            username='admin-filtro-casas',
            password='Admin-seguro1!',
            is_staff=True,
        )
        Casa.objects.create(numero_casa=501, cantidad_personas=2, cantidad_residentes=1, estado='Activa')
        Casa.objects.create(numero_casa=502, cantidad_personas=2, cantidad_residentes=1, estado='Activa')
        self.client.force_login(administrador)

        response = self.client.get(reverse('registrar_casa'), {'casa': '501'})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<option value="501" selected>Casa 501</option>', html=True)
        self.assertContains(response, '<td>501</td>', html=True)
        self.assertNotContains(response, '<td>502</td>', html=True)

    def test_casas_sin_residente_ni_propietario_muestran_guiones(self):
        administrador = User.objects.create_user(
            username='admin-casas-sin-asignacion',
            password='Clave-segura1!',
            is_staff=True,
        )
        self.client.force_login(administrador)
        Casa.objects.create(numero_casa=510, cantidad_personas=2, cantidad_residentes=1, estado='Activa')
        generar_casas_en_lote(cantidad=2, numero_inicial=511)

        respuesta = self.client.get(reverse('registrar_casa'))

        self.assertEqual(respuesta.status_code, 200)
        for numero in (510, 511, 512):
            with self.subTest(numero=numero):
                self.assertContains(
                    respuesta,
                    f'<td>{numero}</td><td>--</td><td>--</td>',
                    html=True,
                )
        self.assertNotContains(respuesta, '<td>None</td>', html=True)

    # Verifica el comportamiento de casa vacia solo requiere numero inicial y sus condiciones relevantes.
    def test_casa_vacia_solo_requiere_numero_inicial(self):
        formulario = CasaForm(data={
            'crear_en_lote': 'on',
            'cantidad_casas': '1',
            'numero_inicial': '150',
            'secundarios-TOTAL_FORMS': '2',
            'secundarios-INITIAL_FORMS': '0',
            'secundarios-MIN_NUM_FORMS': '0',
            'secundarios-MAX_NUM_FORMS': '1000',
        })

        self.assertTrue(formulario.is_valid(), formulario.errors)
        self.assertEqual(formulario.cleaned_data['cantidad_casas'], 1)
        self.assertEqual(formulario.cleaned_data['cantidad_personas'], 1)
        self.assertEqual(formulario.cleaned_data['estado'], 'Activa')

    # Permite omitir el formulario secundario, pero exige todos sus datos si se empieza a llenar.
    def test_residente_secundario_vacio_es_opcional_y_el_incompleto_no_es_valido(self):
        datos_formset = {
            'secundarios-TOTAL_FORMS': '1',
            'secundarios-INITIAL_FORMS': '0',
            'secundarios-MIN_NUM_FORMS': '0',
            'secundarios-MAX_NUM_FORMS': '1000',
        }
        formset_vacio = ResidenteSecundarioFormSet(datos_formset, prefix='secundarios')

        self.assertTrue(formset_vacio.is_valid(), formset_vacio.errors)

        datos_incompletos = {
            **datos_formset,
            'secundarios-0-cedula': '880010',
            'secundarios-0-nombre': 'Ana',
            'secundarios-0-apellido': 'Lopez',
        }
        formset_incompleto = ResidenteSecundarioFormSet(datos_incompletos, prefix='secundarios')

        self.assertFalse(formset_incompleto.is_valid())
        self.assertIn('telefono', formset_incompleto.errors[0])

    # Acepta la ficha secundaria cuando están completos identificación, nombre, apellido y teléfono.
    def test_residente_secundario_completo_es_valido(self):
        formset = ResidenteSecundarioFormSet({
            'secundarios-TOTAL_FORMS': '1',
            'secundarios-INITIAL_FORMS': '0',
            'secundarios-MIN_NUM_FORMS': '0',
            'secundarios-MAX_NUM_FORMS': '1000',
            'secundarios-0-cedula': '880011',
            'secundarios-0-nombre': 'Ana',
            'secundarios-0-apellido': 'Lopez',
            'secundarios-0-telefono': '3001234567',
        }, prefix='secundarios')

        self.assertTrue(formset.is_valid(), formset.errors)

    # Verifica el comportamiento de generación casas en lote crea lotes consecutivos y sus condiciones relevantes.
    def test_generar_casas_en_lote_crea_lotes_consecutivos(self):
        casas = generar_casas_en_lote(
            cantidad=3,
            numero_inicial=100,
            cantidad_personas=4,
            cantidad_residentes=2,
            estado='Activa',
            cartera=0,
        )

        self.assertEqual(len(casas), 3)
        self.assertEqual([c.numero_casa for c in casas], [100, 101, 102])
        self.assertEqual(Casa.objects.count(), 3)
        self.assertTrue(all(c.id_residente_id is None for c in casas))
        self.assertTrue(all(c.id_propietario_id is None for c in casas))

    # Verifica el comportamiento de creación casa y residente nuevo en el mismo envio y sus condiciones relevantes.
    def test_crear_casa_y_residente_nuevo_en_el_mismo_envio(self):
        administrador = User.objects.create_user(username='admin-casa-residente', password='clave', is_staff=True)
        self.client.force_login(administrador)

        response = self.client.post(reverse('registrar_casa'), {
            'numero_casa': '801',
            'cantidad_personas': '3',
            'cantidad_residentes': '1',
            'estado': 'Ocupada',
            'estado_otro': '',
            'cartera': '0',
            'id_residente': '',
            'crear_en_lote': '',
            'secundarios-TOTAL_FORMS': '2',
            'secundarios-INITIAL_FORMS': '0',
            'secundarios-MIN_NUM_FORMS': '0',
            'secundarios-MAX_NUM_FORMS': '1000',
            'secundarios-0-cedula': '880001',
            'secundarios-0-nombre': 'Camila',
            'secundarios-0-apellido': 'Gomez',
            'secundarios-0-telefono': '3001234567',
            'secundarios-1-cedula': '880002',
            'secundarios-1-nombre': 'Andres',
            'secundarios-1-apellido': 'Gomez',
            'secundarios-1-telefono': '3001234568',
        })

        self.assertRedirects(response, f"{reverse('registrar_casa')}?registros=1")
        casa = Casa.objects.get(numero_casa=801)
        principal = Residente.objects.get(cedula=880001)
        secundario = Residente.objects.get(cedula=880002)
        self.assertEqual(casa.id_residente, principal)
        self.assertTrue(CasaResidente.objects.filter(casa=casa, residente=secundario).exists())
        self.assertEqual(casa.cantidad_residentes, 2)
        self.assertTrue(RegistroBitacora.objects.filter(modulo='Casa', casa=casa).exists())
        self.assertTrue(RegistroBitacora.objects.filter(modulo='Residente', registro='Camila Gomez').exists())
        self.assertTrue(RegistroBitacora.objects.filter(modulo='Residente', registro='Andres Gomez', casa=casa).exists())

    # Verifica el comportamiento de residente del directorio se asigna a casa nueva y sus condiciones relevantes.
    def test_residente_del_directorio_se_asigna_a_casa_nueva(self):
        administrador = User.objects.create_user(username='admin-directorio-residente', password='clave', is_staff=True)
        self.client.force_login(administrador)

        registro = self.client.post(reverse('registrar_propietario'), {
            'cedula': '880010',
            'nombre': 'Sofia',
            'apellido': 'Ramos',
            'telefono': '3001234570',
            'correo': '',
            'rol': 'Residente',
            'rol_otro': '',
        })

        self.assertRedirects(registro, f"{reverse('registrar_propietario')}?registros=1")
        residente = Residente.objects.get(cedula=880010)
        self.assertFalse(Propietario.objects.filter(cedula=880010).exists())
        self.assertContains(self.client.get(reverse('registrar_propietario')), 'Sofia Ramos')

        alta_casa = self.client.post(reverse('registrar_casa'), {
            'numero_casa': '802',
            'cantidad_personas': '2',
            'cantidad_residentes': '1',
            'estado': 'Ocupada',
            'estado_otro': '',
            'cartera': '0',
            'id_residente': str(residente.pk),
            'crear_en_lote': '',
            'secundarios-TOTAL_FORMS': '1',
            'secundarios-INITIAL_FORMS': '0',
            'secundarios-MIN_NUM_FORMS': '0',
            'secundarios-MAX_NUM_FORMS': '1000',
        })

        self.assertRedirects(alta_casa, f"{reverse('registrar_casa')}?registros=1")
        self.assertEqual(Casa.objects.get(numero_casa=802).id_residente, residente)

    def test_asignar_residente_existente_a_otra_casa_requiere_confirmacion(self):
        administrador = User.objects.create_user(
            username='admin-asignar-residente',
            password='Clave-segura1!',
            is_staff=True,
        )
        residente = Residente.objects.create(
            cedula=880020,
            nombre='Laura',
            apellido='Rojas',
            telefono='3001234580',
        )
        residente_actual = Residente.objects.create(
            cedula=880021,
            nombre='Mario',
            apellido='Lopez',
            telefono='3001234581',
        )
        casa_origen = Casa.objects.create(
            numero_casa=803,
            cantidad_personas=2,
            cantidad_residentes=1,
            estado='Ocupada',
            id_residente=residente,
        )
        casa_destino = Casa.objects.create(
            numero_casa=804,
            cantidad_personas=3,
            cantidad_residentes=1,
            estado='Ocupada',
            id_residente=residente_actual,
        )
        self.client.force_login(administrador)
        datos = {
            'numero_casa': '804',
            'cantidad_personas': '3',
            'cantidad_residentes': '1',
            'estado': 'Ocupada',
            'estado_otro': '',
            'cartera': '0',
            'id_residente': str(residente_actual.pk),
            'crear_en_lote': '',
            'secundarios-TOTAL_FORMS': '1',
            'secundarios-INITIAL_FORMS': '0',
            'secundarios-MIN_NUM_FORMS': '0',
            'secundarios-MAX_NUM_FORMS': '1000',
            'secundarios-0-residente_existente': str(residente.pk),
            'secundarios-0-cedula': '',
            'secundarios-0-nombre': '',
            'secundarios-0-apellido': '',
            'secundarios-0-telefono': '',
        }

        respuesta = self.client.post(reverse('editar_casa', args=[casa_destino.pk]), datos)

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Estas personas ya están asociadas a otras casas')
        self.assertContains(respuesta, '803')
        self.assertFalse(CasaResidente.objects.filter(casa=casa_destino, residente=residente).exists())

        respuesta = self.client.post(
            reverse('editar_casa', args=[casa_destino.pk]),
            {**datos, 'confirmar_residentes_otra_casa': '1'},
        )

        self.assertRedirects(respuesta, f"{reverse('registrar_casa')}?registros=1")
        self.assertTrue(CasaResidente.objects.filter(casa=casa_destino, residente=residente).exists())
        self.assertTrue(Casa.objects.filter(pk=casa_origen.pk, id_residente=residente).exists())
        self.assertEqual(Residente.objects.filter(cedula=880020).count(), 1)


# Agrupa pruebas automatizadas relacionadas con cuenta usuario pruebas.
class CuentaUsuarioTests(TestCase):
    def test_administrador_restablece_contrasena_de_usuario(self):
        administrador = User.objects.create_user(
            username='admin-reset',
            password='Admin-seguro1!',
            is_staff=True,
        )
        usuario = User.objects.create_user(
            username='usuario-reset',
            password='Clave-anterior1!',
        )
        self.client.force_login(administrador)
        url = reverse('restablecer_contrasena_usuario', args=[usuario.pk])

        response = self.client.post(url, {
            'admin_password': 'Admin-seguro1!',
            'new_password1': 'Clave-nueva2!',
            'new_password2': 'Clave-nueva2!',
        }, follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertRedirects(response, f"{reverse('usuarios')}?registros=1")
        self.assertContains(response, 'Contraseña restablecida para usuario-reset.')
        usuario.refresh_from_db()
        self.assertTrue(usuario.check_password('Clave-nueva2!'))

    def test_administrador_no_puede_restablecer_sin_validar_su_contrasena(self):
        administrador = User.objects.create_user(
            username='admin-reset-invalid',
            password='Admin-seguro1!',
            is_staff=True,
        )
        usuario = User.objects.create_user(
            username='usuario-reset-invalid',
            password='Clave-anterior1!',
        )
        self.client.force_login(administrador)
        url = reverse('restablecer_contrasena_usuario', args=[usuario.pk])

        response = self.client.post(url, {
            'admin_password': 'incorrecta',
            'new_password1': 'Clave-nueva2!',
            'new_password2': 'Clave-nueva2!',
        })

        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context['form'], 'admin_password', 'La contraseña del administrador no es correcta.')
        usuario.refresh_from_db()
        self.assertTrue(usuario.check_password('Clave-anterior1!'))

    def test_administrador_no_puede_abrir_restauracion_de_superusuario(self):
        administrador = User.objects.create_user(
            username='admin-reset-superuser',
            password='Admin-seguro1!',
            is_staff=True,
        )
        superusuario = User.objects.create_superuser(
            username='superusuario-protegido',
            email='superusuario@example.com',
            password='Admin-seguro1!',
        )
        self.client.force_login(administrador)

        response = self.client.get(reverse(
            'restablecer_contrasena_usuario',
            args=[superusuario.pk],
        ))

        self.assertEqual(response.status_code, 404)

    def test_eliminar_guardia_desactiva_y_conserva_su_cuenta(self):
        administrador = User.objects.create_user(
            username='admin-eliminar-guardia',
            password='Admin-seguro1!',
            is_staff=True,
        )
        usuario = User.objects.create_user(username='guardia-eliminado', password='Clave-segura1!')
        guardia = Guardia.objects.create(
            cedula=3001234567,
            nombre='Guardia',
            apellido='Prueba',
            usuario=usuario,
        )
        self.client.force_login(administrador)

        respuesta = self.client.post(
            reverse('registrar_guardia'),
            {'action': 'delete', 'guardia_id': guardia.pk},
        )

        self.assertRedirects(respuesta, f"{reverse('registrar_guardia')}?registros=1")
        self.assertFalse(Guardia.objects.filter(pk=guardia.pk).exists())
        usuario.refresh_from_db()
        self.assertFalse(usuario.is_active)

    def test_eliminar_propietario_desactiva_y_conserva_su_cuenta(self):
        administrador = User.objects.create_user(
            username='admin-eliminar-propietario',
            password='Admin-seguro1!',
            is_staff=True,
        )
        usuario = User.objects.create_user(username='propietario-eliminado', password='Clave-segura1!')
        propietario = Propietario.objects.create(
            cedula=3001234568,
            nombre='Propietario',
            apellido='Prueba',
            telefono='3001234568',
            correo='propietario@gmail.com',
            rol='Propietario',
            usuario=usuario,
        )
        self.client.force_login(administrador)

        respuesta = self.client.post(
            reverse('registrar_propietario'),
            {'action': 'delete', 'propietario_id': propietario.pk},
        )

        self.assertRedirects(respuesta, f"{reverse('registrar_propietario')}?registros=1")
        self.assertFalse(Propietario.objects.filter(pk=propietario.pk).exists())
        usuario.refresh_from_db()
        self.assertFalse(usuario.is_active)

    # Verifica el comportamiento de usuario solo acepta letras y espacios en nombre y apellido y sus condiciones relevantes.
    def test_usuario_solo_acepta_letras_y_espacios_en_nombre_y_apellido(self):
        datos = {
            'username': 'usuario-texto',
            'first_name': 'Ana3',
            'last_name': 'Rojas!',
            'rol': 'administrador',
            'correo_contacto': 'ana.rojas@gmail.com',
            'password': 'Clave-segura1!',
            'password_confirmacion': 'Clave-segura1!',
        }
        formulario = UsuarioForm(data=datos)

        self.assertFalse(formulario.is_valid())
        self.assertIn('first_name', formulario.errors)
        self.assertIn('last_name', formulario.errors)

        datos.update(first_name='Ana María', last_name='O\'Connor')
        formulario = UsuarioForm(data=datos)
        self.assertFalse(formulario.is_valid())
        self.assertIn('last_name', formulario.errors)

        datos['last_name'] = 'Rojas Pérez'
        self.assertTrue(UsuarioForm(data=datos).is_valid())

    def test_toggle_usuario_ajax_actualiza_estado_sin_redireccion(self):
        administrador = User.objects.create_user(
            username='admin-toggle',
            password='Admin-seguro1!',
            is_staff=True,
        )
        usuario = User.objects.create_user(username='usuario-toggle', password='Clave-segura1!')
        self.client.force_login(administrador)

        response = self.client.post(
            reverse('usuarios'),
            {'action': 'toggle', 'usuario_id': usuario.pk},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            'success': True,
            'activo': False,
            'message': 'Estado de la cuenta actualizado.',
        })
        usuario.refresh_from_db()
        self.assertFalse(usuario.is_active)

    def test_toggle_ajax_no_permite_desactivar_la_propia_cuenta(self):
        administrador = User.objects.create_user(
            username='admin-toggle-propio',
            password='Admin-seguro1!',
            is_staff=True,
        )
        self.client.force_login(administrador)

        response = self.client.post(
            reverse('usuarios'),
            {'action': 'toggle', 'usuario_id': administrador.pk},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()['success'])
        administrador.refresh_from_db()
        self.assertTrue(administrador.is_active)

    # Verifica el comportamiento de administrador ignora datos de guardia que quedaron en el formulario y sus condiciones relevantes.
    def test_administrador_ignora_datos_de_guardia_que_quedaron_en_el_formulario(self):
        formulario = UsuarioForm(data={
            'username': 'admin-con-datos-guardia',
            'first_name': 'Ana',
            'last_name': 'Rojas',
            'rol': 'administrador',
            'cedula': '3001234500',
            'telefono': '3001234500',
            'turno': 'Mañana',
            'correo_contacto': 'ana.guardian@gmail.com',
            'password': 'Clave-segura1!',
            'password_confirmacion': 'Clave-segura1!',
        })

        self.assertTrue(formulario.is_valid(), formulario.errors)
        self.assertIsNone(formulario.cleaned_data['cedula'])
        self.assertEqual(formulario.cleaned_data['telefono'], '')
        self.assertEqual(formulario.cleaned_data['turno'], '')

    # Verifica el comportamiento de cuenta de administrador creada desde usuarios puede inicio sesion y sus condiciones relevantes.
    def test_cuenta_de_administrador_creada_desde_usuarios_puede_iniciar_sesion(self):
        administrador = User.objects.create_user(
            username='admin-cuenta',
            password='Admin-seguro1!',
            is_staff=True,
        )
        self.client.force_login(administrador)

        response = self.client.post(reverse('usuarios'), {
            'username': 'admin-nuevo',
            'first_name': 'Ana',
            'last_name': 'Rojas',
            'rol': 'administrador',
            'correo_contacto': 'ana.admin@gmail.com',
            'password': 'Clave-segura1!',
            'password_confirmacion': 'Clave-segura1!',
            'activo': 'on',
        })

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], f"{reverse('usuarios')}?registros=1")
        response = self.client.get(reverse('usuarios'))
        self.assertContains(response, 'Cuenta de usuario creada correctamente.')
        self.assertContains(response, 'admin-nuevo')
        usuario = User.objects.get(username='admin-nuevo')
        self.assertTrue(usuario.groups.filter(name='Administrador').exists())
        self.assertTrue(usuario.has_perm('BD.delete_visitante'))
        self.assertTrue(usuario.has_perm('auth.change_user'))
        self.client.logout()
        self.assertTrue(self.client.login(username='admin-nuevo', password='Clave-segura1!'))
        self.assertRedirects(self.client.get(reverse('login')), reverse('dashboard'))

    def test_cuenta_administrador_acepta_correo_de_otro_proveedor(self):
        administrador = User.objects.create_user(
            username='admin-error-cuenta',
            password='Admin-seguro1!',
            is_staff=True,
        )
        self.client.force_login(administrador)

        response = self.client.post(reverse('usuarios'), {
            'username': 'admin-correo-invalido',
            'first_name': 'Ana',
            'last_name': 'Rojas',
            'rol': 'administrador',
            'correo_contacto': 'ana@example.com',
            'password': 'Clave-segura1!',
            'password_confirmacion': 'Clave-segura1!',
            'activo': 'on',
        })

        self.assertRedirects(response, f"{reverse('usuarios')}?registros=1")
        self.assertEqual(
            User.objects.get(username='admin-correo-invalido').email,
            'ana@example.com',
        )

    # Verifica el comportamiento de grupo administrador funciona sin is staff y sus condiciones relevantes.
    def test_grupo_administrador_funciona_sin_is_staff(self):
        usuario = User.objects.create_user(username='admin-solo-grupo', password='Clave-segura1!')
        usuario.groups.add(Group.objects.get(name='Administrador'))
        self.client.force_login(usuario)

        self.assertEqual(self.client.get(reverse('usuarios')).status_code, 200)
        dashboard = self.client.get(reverse('dashboard'))
        self.assertContains(dashboard, 'TOTAL CASAS')
        self.assertContains(dashboard, 'PAGOS ESTE MES')

    # Verifica el comportamiento de propietario se puede filtrado por numero de casa y sus condiciones relevantes.
    def test_propietario_se_puede_filtrar_por_numero_de_casa(self):
        administrador = User.objects.create_user(
            username='admin-filtro-casa',
            password='Admin-seguro1!',
            is_staff=True,
        )
        propietario = Propietario.objects.create(
            cedula=889900,
            nombre='Marta',
            apellido='Rojas',
            telefono='3001234501',
            correo='marta@gmail.com',
            rol='Propietario',
        )
        Casa.objects.create(
            numero_casa=321,
            cantidad_personas=3,
            cantidad_residentes=1,
            estado='Ocupada',
            id_propietario=propietario,
        )
        self.client.force_login(administrador)

        response = self.client.get(reverse('registrar_propietario'), {'casa': '321'})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Marta Rojas')
        self.assertContains(response, '<option value="321" selected>Casa 321</option>', html=True)
        self.assertEqual(response.context['casa_filtro'], '321')

    # Verifica el comportamiento de propietario muestra solo sus casas actuales y sus condiciones relevantes.
    def test_propietario_muestra_solo_sus_casas_actuales(self):
        administrador = User.objects.create_user(
            username='admin-casa-actual',
            password='Admin-seguro1!',
            is_staff=True,
        )
        propietario = Propietario.objects.create(
            cedula=889902,
            nombre='Carlos',
            apellido='Diaz',
            telefono='3001234503',
            correo='carlos.diaz@gmail.com',
            rol='Propietario',
            casas_historicas=[101],
        )
        Casa.objects.create(
            numero_casa=202,
            cantidad_personas=2,
            cantidad_residentes=1,
            estado='Ocupada',
            id_propietario=propietario,
        )
        self.client.force_login(administrador)

        response = self.client.get(reverse('registrar_propietario'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Casa 202')
        self.assertNotContains(response, 'Casa 101')

    # Verifica el comportamiento de novedades filtran por tipo y fecha y sus condiciones relevantes.
    def test_novedades_filtran_por_tipo_y_fecha(self):
        administrador = User.objects.create_user(
            username='admin-filtro-novedades',
            password='Admin-seguro1!',
            is_staff=True,
        )
        hoy = timezone.localtime()
        Novedad.objects.create(titulo='Agua', tipo='Corte de agua', nota='Servicio', fecha_suceso=hoy)
        Novedad.objects.create(titulo='Pintura', tipo='Mantenimiento', nota='Zonas comunes', fecha_suceso=hoy)
        self.client.force_login(administrador)

        response = self.client.get(reverse('registrar_novedad'), {'tipo': 'Otros', 'fecha': hoy.date().isoformat()})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Pintura')
        self.assertNotContains(response, 'Agua')
        self.assertContains(response, 'value="Otros"')
        self.assertContains(response, 'Otro')
        self.assertEqual(response.context['fecha_filtro'], hoy.date().isoformat())

    # Verifica el comportamiento de cuenta de guardia creada desde usuarios puede inicio sesion y sus condiciones relevantes.
    def test_cuenta_de_guardia_creada_desde_usuarios_puede_iniciar_sesion(self):
        administrador = User.objects.create_user(
            username='admin-cuenta-guardia',
            password='Admin-seguro1!',
            is_staff=True,
        )
        self.client.force_login(administrador)

        response = self.client.post(reverse('usuarios'), {
            'username': 'guardia-nuevo',
            'first_name': 'Laura',
            'last_name': 'Mora',
            'rol': 'guardia',
            'cedula': '3001234599',
            'telefono': '3001234599',
            'turno': 'Mañana',
            'correo_contacto': 'laura.guardian@gmail.com',
            'password': 'Clave-segura1!',
            'password_confirmacion': 'Clave-segura1!',
            'activo': 'on',
        })

        self.assertRedirects(response, f"{reverse('usuarios')}?registros=1")
        usuario = User.objects.get(username='guardia-nuevo')
        self.assertTrue(usuario.groups.filter(name='Guardia').exists())
        self.assertTrue(usuario.has_perm('BD.add_visitante'))
        self.assertTrue(usuario.has_perm('BD.change_visitante'))
        self.assertFalse(usuario.has_perm('BD.delete_visitante'))
        self.client.logout()
        self.assertTrue(self.client.login(username='guardia-nuevo', password='Clave-segura1!'))
        self.assertRedirects(self.client.get(reverse('login')), reverse('dashboard'))

    # Verifica el comportamiento de cuenta de propietario se asigna al grupo y solo accede a pagos y sus condiciones relevantes.
    def test_cuenta_de_propietario_se_asigna_al_grupo_y_solo_accede_a_pagos(self):
        administrador = User.objects.create_user(
            username='admin-cuenta-propietario',
            password='Admin-seguro1!',
            is_staff=True,
        )
        self.client.force_login(administrador)
        casa = Casa.objects.create(
            numero_casa=404,
            cantidad_personas=3,
            cantidad_residentes=1,
            estado='Ocupada',
        )
        propietario = Propietario.objects.create(
            cedula=889901,
            nombre='Marta',
            apellido='Rojas',
            telefono='3001234502',
            correo='marta.propietaria@gmail.com',
            rol='Propietario',
        )

        response = self.client.post(reverse('usuarios'), {
            'username': 'propietario-nuevo',
            'first_name': 'Marta',
            'last_name': 'Rojas',
            'rol': 'propietario',
            'propietario_existente': str(propietario.pk),
            'casas_propietario': [str(casa.pk)],
            'password': 'Clave-segura1!',
            'password_confirmacion': 'Clave-segura1!',
            'activo': 'on',
        })

        self.assertRedirects(response, f"{reverse('usuarios')}?registros=1")
        usuario = User.objects.get(username='propietario-nuevo')
        self.assertTrue(usuario.groups.filter(name='Propietario').exists())
        self.assertTrue(usuario.has_perm('BD.view_pago'))
        self.assertTrue(usuario.has_perm('BD.add_pago'))
        self.assertFalse(usuario.has_perm('BD.delete_pago'))
        casa.refresh_from_db()
        self.assertEqual(casa.id_propietario.usuario_id, usuario.pk)
        self.client.logout()

        self.assertTrue(self.client.login(username='propietario-nuevo', password='Clave-segura1!'))
        self.assertRedirects(self.client.get(reverse('login')), reverse('registrar_pago'))
        self.assertEqual(self.client.get(reverse('registrar_pago')).status_code, 200)
        self.assertEqual(self.client.get(reverse('registrar_casa')).status_code, 302)

    # Verifica el comportamiento de propietario con casa existente no esta disponible para nueva cuenta y sus condiciones relevantes.
    def test_propietario_con_casa_existente_no_esta_disponible_para_nueva_cuenta(self):
        administrador = User.objects.create_user(
            username='admin-casas-propietario',
            password='Admin-seguro1!',
            is_staff=True,
        )
        self.client.force_login(administrador)
        propietario = Propietario.objects.create(
            cedula=889902,
            nombre='Carlos',
            apellido='Mora',
            telefono='3001234503',
            correo='carlos.propietario@gmail.com',
            rol='Propietario',
        )
        Casa.objects.create(numero_casa=405, cantidad_personas=3, cantidad_residentes=1, estado='Ocupada', id_propietario=propietario)
        casa_libre = Casa.objects.create(numero_casa=406, cantidad_personas=3, cantidad_residentes=1, estado='Ocupada')
        casa_tomada = Casa.objects.create(numero_casa=407, cantidad_personas=3, cantidad_residentes=1, estado='Ocupada', id_propietario=propietario)

        formulario = self.client.get(reverse('usuarios'))
        self.assertNotContains(formulario, 'Carlos Mora')
        self.assertContains(formulario, f'value="{casa_libre.pk}"')
        self.assertNotContains(formulario, f'value="{casa_tomada.pk}"')

        response = self.client.post(reverse('usuarios'), {
            'username': 'propietario-multiple',
            'rol': 'propietario',
            'propietario_existente': str(propietario.pk),
            'casas_propietario': [str(casa_libre.pk)],
            'password': 'Clave-segura1!',
            'password_confirmacion': 'Clave-segura1!',
            'activo': 'on',
        })

        self.assertEqual(response.status_code, 200)
        self.assertIn('propietario_existente', response.context['form'].errors)
        self.assertFalse(User.objects.filter(username='propietario-multiple').exists())
        casa_libre.refresh_from_db()
        self.assertIsNone(casa_libre.id_propietario_id)

    def test_correo_de_cuenta_acepta_otro_proveedor(self):
        formulario = UsuarioForm(data={
            'username': 'usuario-correo-invalido',
            'first_name': 'Ana',
            'last_name': 'Rojas',
            'rol': 'administrador',
            'correo_contacto': 'ana@outlook.com',
            'password': 'Clave-segura1!',
            'password_confirmacion': 'Clave-segura1!',
        })

        self.assertTrue(formulario.is_valid(), formulario.errors)

    # Verifica el comportamiento de correo de cuenta es obligatorio y sus condiciones relevantes.
    def test_correo_de_cuenta_es_obligatorio(self):
        formulario = UsuarioForm(data={
            'username': 'usuario-sin-correo',
            'first_name': 'Ana',
            'last_name': 'Rojas',
            'rol': 'guardia',
            'cedula': '3001234999',
            'telefono': '3001234999',
            'turno': 'Mañana',
            'password': 'Clave-segura1!',
            'password_confirmacion': 'Clave-segura1!',
        })

        self.assertFalse(formulario.is_valid())
        self.assertIn('correo_contacto', formulario.errors)

    # Verifica el comportamiento de guardia no ve ni puede abrir modulos administrativos y sus condiciones relevantes.
    def test_guardia_no_ve_ni_puede_abrir_modulos_administrativos(self):
        usuario = User.objects.create_user(username='guardia-permisos', password='Clave-segura1!')
        usuario.groups.add(Group.objects.get(name='Guardia'))
        Guardia.objects.create(
            cedula=3001234598,
            nombre='Laura',
            apellido='Mora',
            turno='Mañana',
            usuario=usuario,
        )
        self.client.force_login(usuario)

        dashboard = self.client.get(reverse('dashboard'))
        self.assertEqual(dashboard.status_code, 200)
        self.assertNotContains(dashboard, 'TOTAL CASAS')
        self.assertNotContains(dashboard, 'PAGOS ESTE MES')
        self.assertNotContains(dashboard, 'Propietario / Residente')

        for ruta in ('registrar_casa', 'registrar_propietario', 'registrar_pago', 'resenas', 'reportes'):
            response = self.client.get(reverse(ruta))
            self.assertEqual(response.status_code, 302, ruta)
            self.assertTrue(response.url.startswith('/login/'), ruta)

    # Verifica el comportamiento de edición casa guarda cambios sin cambiar numero y sus condiciones relevantes.
    def test_editar_casa_guarda_cambios_sin_cambiar_numero(self):
        casa = Casa.objects.create(
            numero_casa=200,
            cantidad_personas=2,
            cantidad_residentes=1,
            estado='Ocupada',
            cartera=0,
        )

        form = CasaEdicionForm(
            data={
                'numero_casa': 999,
                'cantidad_personas': 4,
                'cantidad_residentes': 3,
                'estado': 'Para Arrendar',
                'estado_otro': '',
                'cartera': '10.00',
            },
            instance=casa,
        )

        self.assertTrue(form.is_valid(), form.errors)
        casa_actualizada = form.save()
        self.assertEqual(casa_actualizada.numero_casa, 200)
        self.assertEqual(casa_actualizada.cantidad_personas, 4)
        self.assertEqual(casa_actualizada.cantidad_residentes, 3)
        self.assertEqual(casa_actualizada.estado, 'Para Arrendar')

    # Verifica el comportamiento de casa con pago no se puede eliminación y sus condiciones relevantes.
    def test_casa_con_pago_no_se_puede_eliminar(self):
        administrador = User.objects.create_user(username='admin-casas', password='Admin-seguro1!', is_staff=True)
        casa = Casa.objects.create(numero_casa=201, cantidad_personas=2, cantidad_residentes=1, estado='Ocupada')
        Pago.objects.create(valor='100.00', fecha='2026-09-18', estado='Pagado', id_casa=casa)
        self.client.force_login(administrador)

        response = self.client.post(
            reverse('registrar_casa'),
            {'action': 'delete', 'casa_id': casa.pk},
            follow=True,
        )

        self.assertRedirects(response, f"{reverse('registrar_casa')}?registros=1")
        self.assertContains(response, 'id="siteNotificationModal"')
        self.assertContains(response, 'Casa protegida')
        self.assertContains(response, 'No se puede eliminar esta casa porque tiene pagos registrados.')
        self.assertTrue(Casa.objects.filter(pk=casa.pk).exists())

    # Verifica el comportamiento de casa sin pago se puede eliminación y sus condiciones relevantes.
    def test_casa_sin_pago_se_puede_eliminar(self):
        administrador = User.objects.create_user(username='admin-casas-libres', password='Admin-seguro1!', is_staff=True)
        casa = Casa.objects.create(numero_casa=202, cantidad_personas=2, cantidad_residentes=1, estado='Ocupada')
        self.client.force_login(administrador)

        pagina = self.client.get(reverse('registrar_casa'))
        self.assertContains(pagina, 'id="confirmarEliminacionGlobal"')

        response = self.client.post(reverse('registrar_casa'), {'action': 'delete', 'casa_id': casa.pk})

        self.assertRedirects(response, f"{reverse('registrar_casa')}?registros=1")
        self.assertFalse(Casa.objects.filter(pk=casa.pk).exists())

    # Verifica el comportamiento de propietario conserva numero de casa eliminada y sus condiciones relevantes.
    def test_propietario_conserva_numero_de_casa_eliminada(self):
        administrador = User.objects.create_user(username='admin-historial', password='Admin-seguro1!', is_staff=True)
        propietario = Propietario.objects.create(
            cedula=778899,
            nombre='Marta',
            apellido='Lopez',
            telefono='3001234567',
            correo='marta@gmail.com',
            rol='Propietario',
        )
        casa = Casa.objects.create(numero_casa=203, cantidad_personas=2, cantidad_residentes=1, estado='Ocupada', id_propietario=propietario)
        self.client.force_login(administrador)

        self.client.post(reverse('registrar_casa'), {'action': 'delete', 'casa_id': casa.pk})

        propietario.refresh_from_db()
        self.assertIn(203, propietario.casas_historicas)

    # Verifica el comportamiento de propietario no permite cédula repetida y sus condiciones relevantes.
    def test_propietario_no_permite_cedula_repetida(self):
        Propietario.objects.create(
            cedula=123456,
            nombre='Ana',
            apellido='Gomez',
            telefono='0000000000',
            correo='ana@gmail.com',
            rol='Propietario',
        )
        form = PropietarioForm(data={
            'cedula': 123456,
            'nombre': 'Luis',
            'apellido': 'Perez',
            'telefono': '1111111111',
            'correo': 'luis@gmail.com',
            'rol': 'Residente',
            'rol_otro': '',
        })

        self.assertFalse(form.is_valid())
        self.assertIn('cedula', form.errors)

    def test_cedula_acepta_hasta_9999999999_y_rechaza_el_siguiente(self):
        for modelo, maximo, excedido in (
            (Propietario, 9_999_999_999, 10_000_000_000),
            (Residente, 9_999_999_999, 10_000_000_000),
            (Guardia, 9_999_999_999, 10_000_000_000),
            (Visitante, '9999999999', '10000000000'),
        ):
            campo = modelo._meta.get_field('cedula')
            with self.subTest(modelo=modelo.__name__):
                self.assertEqual(campo.clean(maximo, None), maximo)
                with self.assertRaises(ValidationError):
                    campo.clean(excedido, None)

        datos = {
            'cedula': '9999999999',
            'nombre': 'Ana',
            'apellido': 'Gomez',
            'telefono': '3001234567',
            'correo': '',
            'rol': 'Residente',
            'rol_otro': '',
        }
        formulario = PropietarioForm(data=datos)
        self.assertTrue(formulario.is_valid(), formulario.errors)

        datos['cedula'] = '10000000000'
        formulario = PropietarioForm(data=datos)
        self.assertFalse(formulario.is_valid())
        self.assertIn('cedula', formulario.errors)

    # Verifica el comportamiento de cédula no se repite entre modulos y sus condiciones relevantes.
    def test_cedula_no_se_repite_entre_modulos(self):
        Residente.objects.create(
            cedula=123456,
            nombre='Ana',
            apellido='Gomez',
            telefono='0000000000',
        )
        propietario_form = PropietarioForm(data={
            'cedula': 123456,
            'nombre': 'Luis',
            'apellido': 'Perez',
            'telefono': '1111111111',
            'correo': 'luis@gmail.com',
            'rol': 'Residente',
            'rol_otro': '',
        })
        self.assertFalse(propietario_form.is_valid())
        self.assertIn('cedula', propietario_form.errors)

        Guardia.objects.create(
            cedula=654321,
            nombre='Carlos',
            apellido='Diaz',
            telefono='2222222222',
            turno='Día',
        )
        guardia_form = GuardiaForm(data={
            'cedula': 654321,
            'nombre': 'Maria',
            'apellido': 'Lopez',
            'telefono': '3333333333',
            'turno': 'Noche',
            'password': 'Clave-segura1',
            'password_confirmacion': 'Clave-segura1',
        })
        self.assertFalse(guardia_form.is_valid())
        self.assertIn('cedula', guardia_form.errors)

        casa = Casa.objects.create(numero_casa=100, cantidad_personas=2, cantidad_residentes=1, estado='Ocupada')
        guardia = Guardia.objects.create(cedula=777888, nombre='Elena', apellido='Rojas', turno='Día')
        Visitante.objects.create(
            cedula='999999',
            nombre='Pedro',
            apellido='Ruiz',
            vehiculo_trae='NO',
            cantidad_personas=1,
        )
        visitante_form = VisitanteIngresoForm(data={
            'nombre': 'Laura',
            'apellido': 'Mora',
            'cedula': '999999',
            'tipo_v': 'Familiar',
            'tipo_residente': 'Otro',
            'vehiculo_trae': 'NO',
            'cantidad_personas': 1,
            'vivienda': casa.pk,
            'guardia': guardia.pk,
        })
        self.assertFalse(visitante_form.is_valid())
        self.assertIn('cedula', visitante_form.errors)

    # Verifica el comportamiento de propietario guarda rol personalizado y sus condiciones relevantes.
    def test_propietario_guarda_rol_personalizado(self):
        form = PropietarioForm(data={
            'cedula': 654321,
            'nombre': 'Maria',
            'apellido': 'Lopez',
            'telefono': '2222222222',
            'correo': 'maria@gmail.com',
            'rol': 'Otros',
            'rol_otro': 'Comerciante',
        })

        self.assertTrue(form.is_valid(), form.errors)
        propietario = form.save()
        self.assertEqual(propietario.rol, 'Comerciante')

    def test_propietario_acepta_correo_de_otro_proveedor(self):
        form = PropietarioForm(data={
            'cedula': 654321,
            'nombre': 'Maria',
            'apellido': 'Lopez',
            'telefono': '2222222222',
            'correo': 'maria@hotmail.com',
            'rol': 'Residente',
            'rol_otro': '',
        })

        self.assertTrue(form.is_valid(), form.errors)

    # Verifica el comportamiento de telefono solo acepta numeros y sus condiciones relevantes.
    def test_telefono_solo_acepta_numeros(self):
        form = ResidenteForm(data={
            'cedula': '777888',
            'nombre': 'Carlos',
            'apellido': 'Diaz',
            'telefono': '300ABC123',
        })

        self.assertFalse(form.is_valid())
        self.assertIn('telefono', form.errors)
        self.assertEqual(form.fields['telefono'].widget.attrs['inputmode'], 'numeric')
        self.assertEqual(form.fields['telefono'].widget.attrs['pattern'], '[0-9]*')
        self.assertIn("replace(/[^0-9]/g, '')", form.fields['telefono'].widget.attrs['oninput'])

    # Verifica el comportamiento de nombre y apellido solo aceptan texto y sus condiciones relevantes.
    def test_nombre_y_apellido_solo_aceptan_texto(self):
        form = ResidenteForm(data={
            'cedula': '777888',
            'nombre': 'Carlos2',
            'apellido': 'Diaz!',
            'telefono': '3001234567',
        })

        self.assertFalse(form.is_valid())
        self.assertIn('nombre', form.errors)
        self.assertIn('apellido', form.errors)

    # Verifica el comportamiento de nombre con tilde es valido y sus condiciones relevantes.
    def test_nombre_con_tilde_es_valido(self):
        form = ResenaForm(data={
            'nombre': 'José María',
            'calificacion': 5,
            'comentario': 'Excelente servicio.',
        })

        self.assertTrue(form.is_valid(), form.errors)

    # Verifica el comportamiento de cédula de visitante solo acepta numeros y sus condiciones relevantes.
    def test_cedula_de_visitante_solo_acepta_numeros(self):
        form = VisitanteIngresoForm(data={
            'nombre': 'Laura',
            'apellido': 'Rojas',
            'cedula': '12-ABC',
            'tipo_v': 'Familiar',
            'tipo_residente': 'Otro',
            'vehiculo_trae': 'NO',
            'cantidad_personas': 1,
            'vivienda': '',
            'guardia': '',
        })

        self.assertFalse(form.is_valid())
        self.assertIn('cedula', form.errors)

    # Verifica el comportamiento de visitante muestra solo residentes secundarios de la casa y sus condiciones relevantes.
    def test_visitante_muestra_solo_residentes_secundarios_de_la_casa(self):
        casa = Casa.objects.create(numero_casa=101, cantidad_personas=2, cantidad_residentes=2, estado='Ocupada')
        residente = Residente.objects.create(cedula=888999, nombre='Ana', apellido='Gomez', telefono='3001234567')
        CasaResidente.objects.create(casa=casa, residente=residente)

        form = VisitanteIngresoForm(casa_id=casa.pk)

        opciones = dict(form.fields['persona_autorizante'].choices)
        self.assertIn('residente:{}'.format(residente.pk), opciones)
        self.assertIn('Ana Gomez - Tel: 3001234567', opciones.values())

    # Verifica el comportamiento de visitante muestra propietario como persona autorizante y sus condiciones relevantes.
    def test_visitante_muestra_propietario_como_persona_autorizante(self):
        propietario = Propietario.objects.create(
            cedula=445566,
            nombre='Luis',
            apellido='Perez',
            telefono='3112223344',
            correo='luis@gmail.com',
            rol='Propietario',
        )
        casa = Casa.objects.create(
            numero_casa=102,
            cantidad_personas=2,
            cantidad_residentes=1,
            estado='Ocupada',
            id_propietario=propietario,
        )

        form = VisitanteIngresoForm(casa_id=casa.pk)

        opciones = dict(form.fields['persona_autorizante'].choices)
        self.assertIn('propietario:{}'.format(propietario.pk), opciones)
        self.assertIn('Luis Perez - Tel: 3112223344', opciones.values())
        self.assertNotIn('tipo_residente', form.fields)

    # Verifica el comportamiento de domicilio muestra personas autorizantes de la casa y sus condiciones relevantes.
    def test_domicilio_muestra_personas_autorizantes_de_la_casa(self):
        casa = Casa.objects.create(numero_casa=103, cantidad_personas=2, cantidad_residentes=1, estado='Ocupada')
        residente = Residente.objects.create(cedula=889900, nombre='Marta', apellido='Lopez', telefono='3009876543')
        CasaResidente.objects.create(casa=casa, residente=residente)

        form = DomicilioIngresoForm(casa_id=casa.pk)

        opciones = dict(form.fields['persona_autorizante'].choices)
        self.assertIn('residente:{}'.format(residente.pk), opciones)
        self.assertIn('Marta Lopez - Tel: 3009876543', opciones.values())

    # Verifica el comportamiento de edición domicilio conserva la casa inicial del proceso y sus condiciones relevantes.
    def test_editar_domicilio_conserva_la_casa_inicial_del_proceso(self):
        casa = Casa.objects.create(numero_casa=104, cantidad_personas=2, cantidad_residentes=1, estado='Ocupada')
        domicilio = Domicilio.objects.create(
            nombre='Jorge',
            apellido='Mora',
            telefono_negocio='3151234567',
            autoriza='SI',
        )

        form = DomicilioForm(data={}, instance=domicilio, casa_id=casa.pk)

        self.assertEqual(form.initial['vivienda'], casa.pk)
        self.assertTrue(form.is_valid(), form.errors)

    # Verifica el comportamiento de edición novedad conserva fecha historica y sus condiciones relevantes.
    def test_editar_novedad_conserva_fecha_historica(self):
        fecha_suceso = timezone.now() - timedelta(days=2)
        novedad = Novedad.objects.create(
            titulo='Revisión de acceso',
            tipo='Corte de agua',
            nota='Se revisó la válvula principal.',
            evidencia='evidencias_novedades/revision-acceso.jpg',
            fecha_suceso=fecha_suceso,
        )
        fecha_formulario = timezone.localtime(fecha_suceso).strftime('%Y-%m-%dT%H:%M')
        form = NovedadForm(data={
            'titulo': novedad.titulo,
            'tipo': novedad.tipo,
            'tipo_personalizado': '',
            'nota': novedad.nota,
            'fecha_suceso': fecha_formulario,
        }, instance=novedad)

        self.assertEqual(
            form.fields['fecha_suceso'].widget.attrs['min'],
            f'{timezone.localdate(fecha_suceso).isoformat()}T00:00',
        )
        self.assertTrue(form.is_valid(), form.errors)

    # Verifica el comportamiento de novedad nueva no acepta fecha historica y sus condiciones relevantes.
    def test_novedad_nueva_no_acepta_fecha_historica(self):
        form = NovedadForm(data={
            'titulo': 'Revisión de acceso',
            'tipo': 'Corte de agua',
            'tipo_personalizado': '',
            'nota': 'Se revisó la válvula principal.',
            'fecha_suceso': (timezone.localdate() - timedelta(days=1)).strftime('%Y-%m-%dT10:00'),
        })

        self.assertFalse(form.is_valid())
        self.assertIn('fecha_suceso', form.errors)

    # Verifica el comportamiento de guardia se asigna automaticamente a los formularios y sus condiciones relevantes.
    def test_guardia_se_asigna_automaticamente_a_los_formularios(self):
        usuario = User.objects.create_user(username='3001234567', password='Clave-segura1')
        guardia = Guardia.objects.create(cedula=3001234567, nombre='Elena', apellido='Rojas', usuario=usuario)

        for formulario in (
            VisitanteIngresoForm(guardia=guardia),
            DomicilioIngresoForm(guardia=guardia),
            PaqueteIngresoForm(guardia=guardia),
            NotaForm(guardia=guardia),
        ):
            nombre_campo = 'guardia' if 'guardia' in formulario.fields else 'id_guardia'
            self.assertTrue(formulario.fields[nombre_campo].disabled)
            self.assertEqual(formulario.fields[nombre_campo].initial, guardia)

    # Verifica el comportamiento de guardia edicion incluye cuenta y permite cambiar contrasena y sus condiciones relevantes.
    def test_guardia_edicion_incluye_cuenta_y_permite_cambiar_contrasena(self):
        usuario = User.objects.create_user(username='3001234567', password='clave-anterior')
        guardia = Guardia.objects.create(
            cedula=3001234567,
            nombre='Elena',
            apellido='Rojas',
            usuario=usuario,
        )

        form = GuardiaEdicionForm(
            data={
                'cedula': '3001234567',
                'nombre': 'Elena',
                'apellido': 'Rojas',
                'telefono': '3001234567',
                'turno': 'Tarde',
                'password': 'Clave-nueva1',
                'password_confirmacion': 'Clave-nueva1',
            },
            instance=guardia,
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertIn('password', form.fields)

    # Verifica el comportamiento de contrasena de guardia exige mayuscula y caracter especial y sus condiciones relevantes.
    def test_contrasena_de_guardia_exige_mayuscula_y_caracter_especial(self):
        datos = {
            'cedula': '3001234568',
            'nombre': 'Laura',
            'apellido': 'Mora',
            'telefono': '3001234568',
            'turno': 'Mañana',
            'password_confirmacion': 'abcdefgh',
        }
        for password in ('abcdefgh', 'abcdefgh1', 'Abcdefg1'):
            datos['password'] = password
            form = GuardiaForm(data=datos)
            self.assertFalse(form.is_valid())
            self.assertIn('password', form.errors)

        datos['password'] = 'Abcdefg1!'
        datos['password_confirmacion'] = 'Abcdefg1!'
        self.assertTrue(GuardiaForm(data=datos).is_valid())

    # Verifica el comportamiento de guardia creado por administración puede inicio sesion y sus condiciones relevantes.
    def test_guardia_creado_por_admin_puede_iniciar_sesion(self):
        administrador = User.objects.create_user(
            username='administrador',
            password='Admin-seguro1!',
            is_staff=True,
        )
        self.client.force_login(administrador)

        response = self.client.post(reverse('registrar_guardia'), {
            'cedula': '3001234569',
            'nombre': 'Laura',
            'apellido': 'Mora',
            'telefono': '3001234569',
            'turno': 'Mañana',
            'activo': 'on',
            'password': 'Clave-segura1!',
            'password_confirmacion': 'Clave-segura1!',
        })

        self.assertRedirects(response, f"{reverse('registrar_guardia')}?registros=1")
        self.client.logout()
        self.assertTrue(self.client.login(username='3001234569', password='Clave-segura1!'))

    # Verifica el comportamiento de boton edición guardia abre y guarda cambios y sus condiciones relevantes.
    def test_boton_editar_guardia_abre_y_guarda_cambios(self):
        administrador = User.objects.create_user(
            username='administrador-edicion',
            password='Admin-seguro1!',
            is_staff=True,
        )
        usuario_guardia = User.objects.create_user(
            username='3001234570',
            password='Clave-segura1!',
        )
        guardia = Guardia.objects.create(
            cedula=3001234570,
            nombre='Laura',
            apellido='Mora',
            telefono='3001234570',
            turno='Mañana',
            usuario=usuario_guardia,
        )
        self.client.force_login(administrador)

        pagina = self.client.get(reverse('editar_guardia', args=[guardia.pk]))
        self.assertEqual(pagina.status_code, 200)
        self.assertContains(pagina, 'value="3001234570"')
        self.assertContains(pagina, 'value="Laura"')
        self.assertContains(pagina, 'value="3001234570"')
        self.assertContains(pagina, 'value="Mañana"')

        respuesta = self.client.post(reverse('editar_guardia', args=[guardia.pk]), {
            'cedula': '3001234570',
            'nombre': 'Laura Actualizada',
            'apellido': 'Mora',
            'telefono': '3110000000',
            'turno': 'Tarde',
            'activo': 'on',
            'password': '',
            'password_confirmacion': '',
        })

        self.assertRedirects(respuesta, f"{reverse('registrar_guardia')}?registros=1")
        guardia.refresh_from_db()
        self.assertEqual(guardia.nombre, 'Laura Actualizada')
        self.assertEqual(guardia.turno, 'Tarde')
        self.assertEqual(guardia.telefono, '3110000000')

    # Verifica el comportamiento de administración puede activar y desactivar cuenta desde edicion y sus condiciones relevantes.
    def test_admin_puede_activar_y_desactivar_cuenta_desde_edicion(self):
        administrador = User.objects.create_user(
            username='administrador-estado',
            password='Admin-seguro1!',
            is_staff=True,
        )
        usuario_guardia = User.objects.create_user(
            username='3001234571',
            password='Clave-segura1!',
            is_active=True,
        )
        guardia = Guardia.objects.create(
            cedula=3001234571,
            nombre='Pedro',
            apellido='Rojas',
            turno='Mañana',
            usuario=usuario_guardia,
        )
        self.client.force_login(administrador)

        pagina_activa = self.client.get(reverse('editar_guardia', args=[guardia.pk]))
        self.assertTrue(pagina_activa.context['form'].fields['activo'].initial)
        self.assertContains(pagina_activa, 'name="activo"')

        self.client.post(reverse('editar_guardia', args=[guardia.pk]), {
            'cedula': '3001234571',
            'nombre': 'Pedro',
            'apellido': 'Rojas',
            'telefono': '',
            'turno': 'Mañana',
            'password': '',
            'password_confirmacion': '',
        })
        usuario_guardia.refresh_from_db()
        self.assertFalse(usuario_guardia.is_active)

        pagina_inactiva = self.client.get(reverse('editar_guardia', args=[guardia.pk]))
        self.assertFalse(pagina_inactiva.context['form'].fields['activo'].initial)

        self.client.post(reverse('editar_guardia', args=[guardia.pk]), {
            'cedula': '3001234571',
            'nombre': 'Pedro',
            'apellido': 'Rojas',
            'telefono': '',
            'turno': 'Tarde',
            'activo': 'on',
            'password': '',
            'password_confirmacion': '',
        })
        usuario_guardia.refresh_from_db()
        self.assertTrue(usuario_guardia.is_active)

    # Verifica el comportamiento de edicion acepta turno antiguo para poder guardar y sus condiciones relevantes.
    def test_edicion_acepta_turno_antiguo_para_poder_guardar(self):
        guardia = Guardia.objects.create(
            cedula=3001234572,
            nombre='Carlos',
            apellido='Diaz',
            turno='Noche',
        )

        form = GuardiaEdicionForm(
            data={
                'cedula': '3001234572',
                'nombre': 'Carlos',
                'apellido': 'Diaz',
                'telefono': '',
                'turno': 'Noche',
                'activo': 'on',
                'password': 'Clave-segura1!',
                'password_confirmacion': 'Clave-segura1!',
            },
            instance=guardia,
        )

        self.assertTrue(form.is_valid(), form.errors)

    # Verifica el comportamiento de edicion de paquete solo permite cambiar estado y sus condiciones relevantes.
    def test_edicion_de_paquete_solo_permite_cambiar_estado(self):
        form = PaqueteForm()

        for nombre, campo in form.fields.items():
            if nombre == 'estado_paquete':
                self.assertFalse(campo.disabled)
            else:
                self.assertTrue(campo.disabled)

    # Verifica el comportamiento de turno de guardia es seleccionable y sus condiciones relevantes.
    def test_turno_de_guardia_es_seleccionable(self):
        self.assertEqual(
            GuardiaForm().fields['turno'].choices,
            [('Mañana', 'Mañana'), ('Tarde', 'Tarde')],
        )
        self.assertEqual(
            GuardiaEdicionForm().fields['turno'].choices,
            [('Mañana', 'Mañana'), ('Tarde', 'Tarde')],
        )


# Agrupa pruebas automatizadas relacionadas con pago estado pruebas.
class PagoEstadoTests(TestCase):
    # Organiza el flujo de asignación up dentro de este módulo.
    def setUp(self):
        propietario = Propietario.objects.create(
            cedula=770600,
            nombre='Carlos',
            apellido='Vega',
            telefono='3001234600',
            correo='carlos.vega@gmail.com',
            rol='Propietario',
        )
        self.casa = Casa.objects.create(
            numero_casa=601,
            cantidad_personas=2,
            cantidad_residentes=1,
            estado='Ocupada',
            id_propietario=propietario,
        )

    # Verifica el comportamiento de pago tiene estado pendiente por defecto y sus condiciones relevantes.
    def test_pago_tiene_estado_pendiente_por_defecto(self):
        pago = Pago.objects.create(valor='100.00', fecha='2026-09-23', id_casa=self.casa)

        self.assertEqual(pago.estado, 'Pendiente')

    # Verifica el comportamiento de propietario no puede cambiar estado en formulario y sus condiciones relevantes.
    def test_propietario_no_puede_cambiar_estado_en_formulario(self):
        pago = Pago.objects.create(
            valor='100.00',
            fecha='2026-09-23',
            evidencia='comprobante.pdf',
            id_casa=self.casa,
        )
        formulario = PagoForm(
            data={'id_casa': self.casa.pk, 'valor': '100.00', 'fecha': '2026-09-23', 'estado': 'Pagado'},
            instance=pago,
            propietario=True,
        )

        self.assertTrue(formulario.fields['estado'].disabled)
        self.assertTrue(formulario.is_valid(), formulario.errors)
        self.assertEqual(formulario.cleaned_data['estado'], 'Pendiente')

    # Verifica el comportamiento de edicion administrativa solo expone estado y sus condiciones relevantes.
    def test_edicion_administrativa_solo_expone_estado(self):
        pago = Pago.objects.create(valor='100.00', fecha='2026-09-23', id_casa=self.casa)
        formulario = PagoForm(instance=pago, solo_estado=True)

        self.assertEqual(tuple(formulario.fields), ('estado',))

    # Verifica el comportamiento de saldo solo descuenta pagos confirmados en vista y reporte y sus condiciones relevantes.
    def test_saldo_solo_descuenta_pagos_confirmados_en_vista_y_reporte(self):
        self.casa.cartera = 400
        self.casa.saldo_mora = 25
        self.casa.save(update_fields=('cartera', 'saldo_mora'))
        Pago.objects.create(valor='100.00', fecha='2026-09-23', estado='Pagado', id_casa=self.casa)
        Pago.objects.create(valor='75.00', fecha='2026-09-24', estado='Pendiente', id_casa=self.casa)
        administrador = User.objects.create_user(username='admin-pagos-saldo', password='clave', is_staff=True)
        self.client.force_login(administrador)

        respuesta = self.client.get(reverse('registrar_pago'))
        pagos = list(respuesta.context['pagos'])
        _, _, filas_reporte = build_report_rows(RequestFactory().get('/reportes/'), 'pagos')

        self.assertEqual(pagos[0].saldo_restante, 425)
        self.assertEqual(filas_reporte[0][-1], '$ 425')
        self.assertEqual(respuesta.context['saldos_actuales_casas'], [{'casa': self.casa, 'saldo': 425, 'saldo_favor': Decimal('0.00'), 'pendiente': True}])
        self.assertContains(respuesta, 'Saldo actual por casa')
        self.assertEqual(Pago.objects.get(estado='Pagado').estado, 'Pagado')

    def test_saldo_a_favor_se_aplica_al_acumulado_y_solo_muestra_excedente(self):
        self.casa.cartera = Decimal('500.00')
        self.casa.saldo_favor = Decimal('200.00')
        self.casa.save(update_fields=('cartera', 'saldo_favor'))
        Pago.objects.create(valor='100.00', fecha='2026-09-23', estado='Pagado', id_casa=self.casa)
        administrador = User.objects.create_user(username='admin-saldo-neto', password='clave', is_staff=True)
        self.client.force_login(administrador)

        respuesta = self.client.get(reverse('registrar_pago'))
        saldo_casa = respuesta.context['saldos_actuales_casas'][0]
        self.assertEqual(saldo_casa['saldo'], Decimal('300.00'))
        self.assertEqual(saldo_casa['saldo_favor'], 0)

        self.casa.saldo_favor = Decimal('700.00')
        self.casa.save(update_fields=('saldo_favor',))
        respuesta = self.client.get(reverse('registrar_pago'))
        saldo_casa = respuesta.context['saldos_actuales_casas'][0]
        self.assertEqual(saldo_casa['saldo'], 0)
        self.assertEqual(saldo_casa['saldo_favor'], Decimal('200.00'))

    def test_saldo_del_pago_confirmado_se_conserva_como_snapshot(self):
        self.casa.cartera = Decimal('500.00')
        self.casa.save(update_fields=('cartera',))
        pago = Pago.objects.create(valor='200.00', fecha='2026-09-23', id_casa=self.casa)
        administrador = User.objects.create_user(username='admin-saldo-snapshot', password='clave', is_staff=True)
        self.client.force_login(administrador)

        self.client.post(reverse('editar_pago', args=(pago.pk,)), {'estado': 'Pagado'})
        pago.refresh_from_db()
        self.assertEqual(pago.saldo_pendiente_despues, Decimal('300.00'))

        self.casa.refresh_from_db()
        self.casa.cartera += Decimal('500.00')
        self.casa.save(update_fields=('cartera',))
        respuesta = self.client.get(reverse('registrar_pago'))
        pago_mostrado = next(item for item in respuesta.context['pagos'] if item.pk == pago.pk)
        self.assertEqual(pago_mostrado.saldo_restante, Decimal('300.00'))
        self.assertEqual(respuesta.context['saldos_actuales_casas'][0]['saldo'], Decimal('800.00'))
        self.assertContains(respuesta, '$300')

        self.client.post(reverse('editar_pago', args=(pago.pk,)), {'estado': 'Pendiente'})
        pago.refresh_from_db()
        self.assertIsNone(pago.saldo_pendiente_despues)

    # Verifica el comportamiento de pago confirmado reduce cartera y propietario descarga recibo y sus condiciones relevantes.
    def test_pago_confirmado_reduce_cartera_y_propietario_descarga_recibo(self):
        self.casa.cartera = Decimal('500000.00')
        self.casa.save(update_fields=('cartera',))
        pago = Pago.objects.create(valor='200000.00', fecha='2026-09-23', estado='Pendiente', id_casa=self.casa)
        administrador = User.objects.create_user(username='admin-confirmar-recibo', password='clave', is_staff=True)
        self.client.force_login(administrador)

        respuesta = self.client.post(reverse('editar_pago', args=(pago.pk,)), {'estado': 'Pagado'})

        self.assertRedirects(respuesta, f"{reverse('registrar_pago')}?registros=1")
        pago.refresh_from_db()
        self.casa.refresh_from_db()
        self.assertEqual(pago.estado, 'Pagado')
        self.assertEqual(self.casa.cartera, Decimal('300000.00'))
        self.assertContains(self.client.get(reverse('registrar_pago')), 'Descargar recibo PDF')

        propietario_usuario = User.objects.create_user(username='propietario-recibo', password='clave')
        propietario_usuario.groups.add(Group.objects.get_or_create(name='Propietario')[0])
        self.casa.id_propietario.usuario = propietario_usuario
        self.casa.id_propietario.save(update_fields=('usuario',))
        self.client.force_login(propietario_usuario)
        recibo = self.client.get(reverse('recibo_pago', args=(pago.pk,)))

        self.assertEqual(recibo.status_code, 200)
        self.assertEqual(recibo['Content-Type'], 'application/pdf')
        self.assertIn('attachment;', recibo['Content-Disposition'])

    # Verifica el comportamiento de pago parcial aplica primero mora y registra el desglose y sus condiciones relevantes.
    def test_pago_parcial_aplica_primero_mora_y_registra_el_desglose(self):
        self.casa.cartera = Decimal('500000.00')
        self.casa.saldo_mora = Decimal('10000.00')
        self.casa.save(update_fields=('cartera', 'saldo_mora'))
        pago = Pago.objects.create(valor='200000.00', fecha='2026-09-23', estado='Pendiente', id_casa=self.casa)
        administrador = User.objects.create_user(username='admin-abono-mora', password='clave', is_staff=True)
        self.client.force_login(administrador)

        respuesta = self.client.post(reverse('editar_pago', args=(pago.pk,)), {'estado': 'Pagado'})

        self.assertRedirects(respuesta, f"{reverse('registrar_pago')}?registros=1")
        pago.refresh_from_db()
        self.casa.refresh_from_db()
        self.assertEqual(pago.valor_mora_aplicada, Decimal('10000.00'))
        self.assertEqual(pago.valor_cartera_aplicada, Decimal('190000.00'))
        self.assertEqual(self.casa.saldo_mora, Decimal('0.00'))
        self.assertEqual(self.casa.cartera, Decimal('310000.00'))
        self.assertEqual(self.casa.cartera + self.casa.saldo_mora, Decimal('310000.00'))

    def test_sobrepago_se_acumula_como_saldo_a_favor_y_se_revierte(self):
        self.casa.cartera = Decimal('500000.00')
        self.casa.save(update_fields=('cartera',))
        administrador = User.objects.create_user(username='admin-saldo-favor', password='clave', is_staff=True)
        self.client.force_login(administrador)

        pago_justo = Pago.objects.create(valor='500000.00', fecha='2026-09-23', id_casa=self.casa)
        self.client.post(reverse('editar_pago', args=(pago_justo.pk,)), {'estado': 'Pagado'})
        self.casa.refresh_from_db()
        self.assertEqual(self.casa.cartera, Decimal('0.00'))
        self.assertEqual(self.casa.saldo_favor, Decimal('0.00'))
        self.client.post(reverse('registrar_pago'), {'action': 'delete', 'pago_id': pago_justo.pk})

        pago = Pago.objects.create(valor='1000000.00', fecha='2026-09-23', id_casa=self.casa)
        respuesta = self.client.post(reverse('editar_pago', args=(pago.pk,)), {'estado': 'Pagado'})

        self.assertRedirects(respuesta, f"{reverse('registrar_pago')}?registros=1")
        pago.refresh_from_db()
        self.casa.refresh_from_db()
        self.assertEqual(self.casa.cartera, Decimal('0.00'))
        self.assertEqual(self.casa.saldo_favor, Decimal('500000.00'))
        self.assertEqual(pago.valor_saldo_favor_aplicado, Decimal('500000.00'))
        respuesta = self.client.get(reverse('registrar_pago'))
        self.assertEqual(respuesta.context['saldos_actuales_casas'][0]['saldo_favor'], Decimal('500000.00'))
        self.assertContains(respuesta, 'Saldo a favor')
        self.assertContains(respuesta, '$500.000')

        pago_adicional = Pago.objects.create(valor='100000.00', fecha='2026-09-23', id_casa=self.casa)
        self.client.post(reverse('editar_pago', args=(pago_adicional.pk,)), {'estado': 'Pagado'})
        self.casa.refresh_from_db()
        self.assertEqual(self.casa.saldo_favor, Decimal('600000.00'))
        self.client.post(reverse('registrar_pago'), {'action': 'delete', 'pago_id': pago_adicional.pk})
        self.casa.refresh_from_db()
        self.assertEqual(self.casa.saldo_favor, Decimal('500000.00'))

        self.client.post(reverse('editar_pago', args=(pago.pk,)), {'estado': 'Pendiente'})
        self.casa.refresh_from_db()
        self.assertEqual(self.casa.cartera, Decimal('500000.00'))
        self.assertEqual(self.casa.saldo_favor, Decimal('0.00'))

        self.client.post(reverse('editar_pago', args=(pago.pk,)), {'estado': 'Pagado'})
        respuesta = self.client.post(reverse('registrar_pago'), {'action': 'delete', 'pago_id': pago.pk})
        self.assertRedirects(respuesta, f"{reverse('registrar_pago')}?registros=1")
        self.casa.refresh_from_db()
        self.assertEqual(self.casa.cartera, Decimal('500000.00'))
        self.assertEqual(self.casa.saldo_favor, Decimal('0.00'))

    # Verifica el comportamiento de recibo pendiente se descarga como pendiente y sus condiciones relevantes.
    def test_recibo_pendiente_se_descarga_como_pendiente(self):
        pago = Pago.objects.create(valor='200000.00', fecha='2026-09-23', estado='Pendiente', id_casa=self.casa)
        administrador = User.objects.create_user(username='admin-recibo-pendiente', password='clave', is_staff=True)
        self.client.force_login(administrador)

        respuesta = self.client.get(reverse('recibo_pago', args=(pago.pk,)))

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta['Content-Type'], 'application/pdf')

    # Verifica el comportamiento de no se puede registro pago para casa sin propietario y sus condiciones relevantes.
    def test_no_se_puede_registrar_pago_para_casa_sin_propietario(self):
        administrador = User.objects.create_user(username='admin-pago-sin-propietario', password='clave', is_staff=True)
        casa_sin_propietario = Casa.objects.create(
            numero_casa=602,
            cantidad_personas=2,
            cantidad_residentes=1,
            estado='Ocupada',
        )
        self.client.force_login(administrador)

        response = self.client.post(reverse('registrar_pago'), {
            'id_casa': casa_sin_propietario.pk,
            'valor': '100.00',
            'fecha': '2026-09-23',
            'estado': 'Pagado',
        })

        self.assertEqual(response.status_code, 200)
        self.assertIn('id_casa', response.context['form'].errors)
        self.assertFalse(Pago.objects.filter(id_casa=casa_sin_propietario).exists())

    # Verifica el comportamiento de tabla pagos filtra por fecha y pendientes y sus condiciones relevantes.
    def test_tabla_pagos_filtra_por_fecha_y_pendientes(self):
        pago_antiguo = Pago.objects.create(valor='40.00', fecha='2026-09-10', estado='Pendiente', id_casa=self.casa)
        pago_filtrado = Pago.objects.create(valor='50.00', fecha='2026-09-20', estado='Pendiente', id_casa=self.casa)
        Pago.objects.create(valor='60.00', fecha='2026-09-21', estado='Pagado', id_casa=self.casa)
        administrador = User.objects.create_user(username='admin-filtro-pagos', password='clave', is_staff=True)
        self.client.force_login(administrador)

        response = self.client.get(reverse('registrar_pago'), {
            'desde': '2026-09-15',
            'hasta': '2026-09-20',
            'estado': 'Pendiente',
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context['pagos']), [pago_filtrado])
        self.assertEqual(response.context['desde_filtro'], '2026-09-15')
        self.assertEqual(response.context['hasta_filtro'], '2026-09-20')
        self.assertEqual(response.context['estado_filtro'], 'Pendiente')
        self.assertNotIn(pago_antiguo, response.context['pagos'])

    # Verifica el comportamiento de tabla pagos se ordena por fecha mas reciente y sus condiciones relevantes.
    def test_tabla_pagos_se_ordena_por_fecha_mas_reciente(self):
        pago_antiguo = Pago.objects.create(valor='40.00', fecha='2026-09-10', id_casa=self.casa)
        pago_reciente = Pago.objects.create(valor='50.00', fecha='2026-09-20', id_casa=self.casa)
        administrador = User.objects.create_user(username='admin-orden-pagos', password='clave', is_staff=True)
        self.client.force_login(administrador)

        response = self.client.get(reverse('registrar_pago'))

        self.assertEqual(list(response.context['pagos']), [pago_reciente, pago_antiguo])


# Agrupa pruebas automatizadas relacionadas con mora cartera pruebas.
class MoraCarteraTests(TestCase):
    # Crea creación propietario y coordina los datos relacionados.
    def crear_propietario(self, *, cedula, correo):
        return Propietario.objects.create(
            cedula=cedula,
            nombre='Laura',
            apellido='Gil',
            telefono='3001234801',
            correo=correo,
            rol='Propietario',
        )

    def test_incremento_mensual_incluye_casas_con_pagos_pendientes_o_pagados(self):
        casas = []
        for numero, estado_pago in ((910, 'Pagado'), (911, 'Pendiente')):
            propietario = self.crear_propietario(
                cedula=771100 + numero,
                correo=f'casa-{numero}@example.com',
            )
            casa = Casa.objects.create(
                numero_casa=numero,
                cantidad_personas=2,
                cantidad_residentes=1,
                estado='Ocupada',
                cartera=Decimal('500000.00'),
                saldo_favor=Decimal('200000.00') if estado_pago == 'Pendiente' else Decimal('0.00'),
                id_propietario=propietario,
                ultima_mora_aplicada=date(2026, 4, 30),
            )
            Pago.objects.create(valor='100.00', fecha='2026-04-15', estado=estado_pago, id_casa=casa)
            casas.append(casa)
        casa_sin_pago = Casa.objects.create(
            numero_casa=912,
            cantidad_personas=2,
            cantidad_residentes=1,
            estado='Ocupada',
            cartera=Decimal('500000.00'),
            ultima_mora_aplicada=date(2026, 4, 30),
        )
        configuracion = ConfiguracionCartera.objects.get(pk=1)
        configuracion.frecuencia_mora = 'mensual'
        configuracion.porcentaje_mora = Decimal('2.00')
        configuracion.monto_aumento_mensual = Decimal('500000.00')
        configuracion.dia_vencimiento = 30
        configuracion.save(update_fields=(
            'frecuencia_mora',
            'porcentaje_mora',
            'monto_aumento_mensual',
            'dia_vencimiento',
        ))

        actualizadas = aplicar_mora_vencida(date(2026, 5, 31))

        casa_pagado, casa_pendiente = casas
        casa_pagado.refresh_from_db()
        casa_pendiente.refresh_from_db()
        self.assertEqual(casa_pagado.cartera, Decimal('1000000.00'))
        self.assertEqual(casa_pagado.saldo_mora, Decimal('10000.00'))
        self.assertEqual(saldos_actuales_por_casa([casa_pagado])[casa_pagado.pk], Decimal('1010000.00'))
        self.assertEqual(casa_pagado.ultima_mora_aplicada, date(2026, 5, 30))
        self.assertEqual(casa_pendiente.cartera, Decimal('1000000.00'))
        self.assertEqual(casa_pendiente.saldo_mora, Decimal('6000.00'))
        self.assertEqual(saldos_actuales_por_casa([casa_pendiente])[casa_pendiente.pk], Decimal('806000.00'))
        self.assertEqual(casa_pendiente.ultima_mora_aplicada, date(2026, 5, 30))
        casa_sin_pago.refresh_from_db()
        self.assertEqual(casa_sin_pago.saldo_mora, Decimal('0.00'))
        self.assertEqual(casa_sin_pago.cartera, Decimal('500000.00'))
        self.assertEqual(casa_sin_pago.ultima_mora_aplicada, date(2026, 4, 30))
        self.assertEqual(actualizadas, 2)

        actualizadas = aplicar_mora_vencida(date(2026, 7, 1))
        casa_pagado.refresh_from_db()
        self.assertEqual(casa_pagado.cartera, Decimal('1500000.00'))
        self.assertEqual(casa_pagado.saldo_mora, Decimal('30200.00'))
        self.assertEqual(saldos_actuales_por_casa([casa_pagado])[casa_pagado.pk], Decimal('1530200.00'))
        self.assertEqual(actualizadas, 2)

    # Verifica el comportamiento de aplica dos por ciento una vez despues del vencimiento y sus condiciones relevantes.
    def test_aplica_dos_por_ciento_una_vez_despues_del_vencimiento(self):
        propietario = self.crear_propietario(cedula=771001, correo='laura.gil.mora@gmail.com')
        casa = Casa.objects.create(
            numero_casa=901,
            cantidad_personas=2,
            cantidad_residentes=1,
            estado='Ocupada',
            cartera=Decimal('250000.00'),
            id_propietario=propietario,
            ultima_mora_aplicada=date(2026, 4, 30),
        )
        Pago.objects.create(valor='100.00', fecha='2026-09-01', estado='Pagado', id_casa=casa)
        casa_sin_propietario = Casa.objects.create(
            numero_casa=902,
            cantidad_personas=2,
            cantidad_residentes=1,
            estado='Ocupada',
            cartera=Decimal('500.00'),
        )
        configuracion = ConfiguracionCartera.objects.get(pk=1)
        configuracion.porcentaje_mora = Decimal('2.00')
        configuracion.dia_vencimiento = 30
        configuracion.save(update_fields=('porcentaje_mora', 'dia_vencimiento'))

        actualizadas = aplicar_mora_vencida(date(2026, 5, 31))
        casa.refresh_from_db()
        casa_sin_propietario.refresh_from_db()

        self.assertEqual(actualizadas, 1)
        self.assertEqual(casa.cartera, Decimal('250000.00'))
        self.assertEqual(casa.saldo_mora, Decimal('5000.00'))
        self.assertEqual(casa_sin_propietario.cartera, Decimal('500.00'))
        self.assertEqual(casa.ultima_mora_aplicada, date(2026, 5, 30))

        actualizadas = aplicar_mora_vencida(date(2026, 5, 31))
        casa.refresh_from_db()
        self.assertEqual(actualizadas, 0)
        self.assertEqual(casa.saldo_mora, Decimal('5000.00'))

        actualizadas = aplicar_mora_vencida(date(2026, 7, 1))
        casa.refresh_from_db()
        self.assertEqual(actualizadas, 1)
        self.assertEqual(casa.cartera, Decimal('250000.00'))
        self.assertEqual(casa.saldo_mora, Decimal('10100.00'))

    # Verifica el comportamiento de modo prueba aplica dos por ciento sobre el saldo acumulado por minuto y sus condiciones relevantes.
    def test_modo_prueba_aplica_dos_por_ciento_sobre_el_saldo_acumulado_por_minuto(self):
        propietario = self.crear_propietario(cedula=771003, correo='laura.gil.minuto@gmail.com')
        ahora = timezone.make_aware(datetime(2026, 10, 1, 12, 0))
        casa = Casa.objects.create(
            numero_casa=904,
            cantidad_personas=2,
            cantidad_residentes=1,
            estado='Ocupada',
            cartera=Decimal('500000.00'),
            id_propietario=propietario,
            ultima_mora_calculada=ahora,
        )
        Pago.objects.create(valor='100.00', fecha='2026-09-01', estado='Pagado', id_casa=casa)
        configuracion = ConfiguracionCartera.objects.get(pk=1)
        configuracion.frecuencia_mora = 'minuto'
        configuracion.porcentaje_mora = Decimal('2.00')
        configuracion.monto_aumento_mensual = Decimal('500000.00')
        configuracion.save(update_fields=('frecuencia_mora', 'porcentaje_mora', 'monto_aumento_mensual'))

        actualizadas = aplicar_mora_vencida(ahora=ahora + timedelta(minutes=2, seconds=15))
        casa.refresh_from_db()

        self.assertEqual(actualizadas, 2)
        self.assertEqual(casa.cartera + casa.saldo_mora, Decimal('1530200.00'))

    def test_modo_prueba_aplica_mora_a_casa_con_saldo_sin_pago_confirmado(self):
        propietario = self.crear_propietario(cedula=771004, correo='laura.gil.sinpago@gmail.com')
        ahora = timezone.make_aware(datetime(2026, 10, 1, 12, 0))
        casa = Casa.objects.create(
            numero_casa=905,
            cantidad_personas=2,
            cantidad_residentes=1,
            estado='Ocupada',
            cartera=Decimal('500000.00'),
            id_propietario=propietario,
            ultima_mora_calculada=ahora,
        )
        configuracion = ConfiguracionCartera.objects.get(pk=1)
        configuracion.frecuencia_mora = 'minuto'
        configuracion.porcentaje_mora = Decimal('2.00')
        configuracion.monto_aumento_mensual = Decimal('0.00')
        configuracion.save(update_fields=('frecuencia_mora', 'porcentaje_mora', 'monto_aumento_mensual'))

        actualizadas = aplicar_mora_vencida(ahora=ahora + timedelta(minutes=1))
        casa.refresh_from_db()

        self.assertEqual(actualizadas, 1)
        self.assertEqual(casa.saldo_mora, Decimal('10000.00'))

    def test_endpoint_modo_prueba_devuelve_casa_con_saldo_sin_pago_confirmado(self):
        propietario = self.crear_propietario(cedula=771005, correo='laura.gil.endpoint-sinpago@gmail.com')
        casa = Casa.objects.create(
            numero_casa=906,
            cantidad_personas=2,
            cantidad_residentes=1,
            estado='Ocupada',
            cartera=Decimal('500000.00'),
            id_propietario=propietario,
            ultima_mora_calculada=timezone.now() - timedelta(minutes=1, seconds=5),
        )
        configuracion = ConfiguracionCartera.objects.get(pk=1)
        configuracion.frecuencia_mora = 'minuto'
        configuracion.porcentaje_mora = Decimal('2.00')
        configuracion.monto_aumento_mensual = Decimal('0.00')
        configuracion.save(update_fields=('frecuencia_mora', 'porcentaje_mora', 'monto_aumento_mensual'))
        administrador = User.objects.create_user(username='admin-cartera-sin-pago', password='clave', is_staff=True)
        self.client.force_login(administrador)

        response = self.client.get(reverse('actualizar_saldos_cartera'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['saldos'][str(casa.pk)], '510000.00')

    # Verifica el comportamiento de endpoint aplica el minuto y retorna el saldo y sus condiciones relevantes.
    def test_endpoint_aplica_el_minuto_y_retorna_el_saldo(self):
        propietario = self.crear_propietario(cedula=771002, correo='laura.gil.endpoint@gmail.com')
        casa = Casa.objects.create(
            numero_casa=903,
            cantidad_personas=2,
            cantidad_residentes=1,
            estado='Ocupada',
            cartera=Decimal('250000.00'),
            id_propietario=propietario,
        )
        Pago.objects.create(valor='100.00', fecha='2026-09-01', estado='Pagado', id_casa=casa)
        administrador = User.objects.create_user(username='admin-cartera-endpoint', password='clave', is_staff=True)
        self.client.force_login(administrador)

        response = self.client.get(reverse('actualizar_saldos_cartera'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['saldos'][str(casa.pk)], '250000.00')

    # Verifica el comportamiento de solo administrador puede cambiar incremento y sus condiciones relevantes.
    def test_solo_administrador_puede_cambiar_incremento(self):
        administrador = User.objects.create_user(username='admin-config-cartera', password='clave', is_staff=True)
        self.client.force_login(administrador)

        pantalla = self.client.get(reverse('configuracion_cartera'))
        self.assertEqual(pantalla.status_code, 200)
        self.assertContains(pantalla, '<title>Configuración | Piemonte</title>', html=True)
        self.assertContains(pantalla, reverse('actualizar_saldos_cartera'))
        self.assertContains(pantalla, 'window.setInterval(solicitarActualizacionSaldos, 60000)')
        self.assertContains(pantalla, 'Cartera')
        self.assertContains(pantalla, 'Domiciliarios')
        self.assertContains(pantalla, 'Interés de mora (%)')
        self.assertContains(pantalla, 'Día límite de pago de cada mes')
        self.assertContains(pantalla, 'Tiempo máximo del domiciliario (minutos)')
        self.assertContains(pantalla, 'Estados de los módulos')
        self.assertContains(pantalla, 'Notas')
        self.assertContains(pantalla, 'Vista previa')
        self.assertContains(pantalla, 'data-status-preview')

        response = self.client.post(reverse('configuracion_cartera'), {
            'porcentaje_mora': '2.50',
            'monto_aumento_mensual': '0.00',
            'dia_vencimiento': '28',
            'frecuencia_mora': 'minuto',
            'tiempo_domiciliario_minutos': '5',
        })

        self.assertRedirects(response, reverse('configuracion_cartera'))
        configuracion = ConfiguracionCartera.objects.get(pk=1)
        self.assertEqual(configuracion.porcentaje_mora, Decimal('2.50'))
        self.assertEqual(configuracion.dia_vencimiento, 28)
        self.assertEqual(configuracion.frecuencia_mora, 'minuto')
        self.assertEqual(configuracion.tiempo_domiciliario_minutos, 5)

    def test_cambiar_frecuencia_reinicia_reloj_de_todas_las_casas(self):
        configuracion = ConfiguracionCartera.objects.get(pk=1)
        configuracion.frecuencia_mora = 'mensual'
        configuracion.monto_aumento_mensual = Decimal('0.00')
        configuracion.save(update_fields=('frecuencia_mora', 'monto_aumento_mensual'))
        propietario = self.crear_propietario(cedula=771006, correo='laura.gil.reloj@gmail.com')
        hace_dos_dias = timezone.now() - timedelta(days=2)
        casa = Casa.objects.create(
            numero_casa=907,
            cantidad_personas=2,
            cantidad_residentes=1,
            estado='Ocupada',
            cartera=Decimal('500000.00'),
            id_propietario=propietario,
            ultima_mora_calculada=hace_dos_dias,
        )
        administrador = User.objects.create_user(username='admin-config-reloj', password='clave', is_staff=True)
        self.client.force_login(administrador)

        response = self.client.post(reverse('configuracion_cartera'), {
            'porcentaje_mora': '2.00',
            'monto_aumento_mensual': '0.00',
            'dia_vencimiento': '29',
            'frecuencia_mora': 'minuto',
            'tiempo_domiciliario_minutos': '1',
        })

        self.assertRedirects(response, reverse('configuracion_cartera'))
        casa.refresh_from_db()
        self.assertGreater(casa.ultima_mora_calculada, hace_dos_dias)
        self.assertEqual(casa.ultima_mora_aplicada, timezone.localdate())

    # Verifica el comportamiento de estado se puede personalizar sin alterar otros datos de visualizacion y sus condiciones relevantes.
    def test_estado_se_puede_personalizar_sin_alterar_otros_datos_de_visualizacion(self):
        administrador = User.objects.create_user(username='admin-estados-config', password='clave', is_staff=True)
        self.client.force_login(administrador)
        datos = {
            'porcentaje_mora': '2',
            'monto_aumento_mensual': '0.00',
            'dia_vencimiento': '30',
            'frecuencia_mora': 'mensual',
            'tiempo_domiciliario_minutos': '1',
            'estado_domicilio_0_nombre': 'En ruta',
            'estado_domicilio_0_color': '#123456',
        }

        response = self.client.post(reverse('configuracion_cartera'), datos)

        self.assertRedirects(response, reverse('configuracion_cartera'))
        configuracion = ConfiguracionCartera.objects.get(pk=1)
        self.assertEqual(
            configuracion.estados_visualizacion['domicilio']['PENDIENTE'],
            {
                'nombre': 'En ruta',
                'color': '#123456',
            },
        )

        datos['estado_domicilio_0_nombre'] = 'En camino'
        response = self.client.post(reverse('configuracion_cartera'), datos)

        self.assertRedirects(response, reverse('configuracion_cartera'))
        configuracion.refresh_from_db()
        self.assertEqual(
            configuracion.estados_visualizacion['domicilio']['PENDIENTE']['nombre'],
            'En camino',
        )

    # Verifica el comportamiento de cambios de estado se aprecian en los modulos y movimientos y sus condiciones relevantes.
    def test_cambios_de_estado_se_aprecian_en_los_modulos_y_movimientos(self):
        administrador = User.objects.create_user(
            username='admin-verifica-estados',
            password='clave',
            is_staff=True,
        )
        propietario = self.crear_propietario(
            cedula=771020,
            correo='laura.gil.estados@gmail.com',
        )
        casa = Casa.objects.create(
            numero_casa=920,
            cantidad_personas=2,
            cantidad_residentes=1,
            estado='Ocupada',
            cartera=Decimal('1000.00'),
            id_propietario=propietario,
        )
        guardia = Guardia.objects.create(
            cedula=771021,
            nombre='Mario',
            apellido='Ruiz',
            telefono='3001234821',
            turno='Mañana',
        )
        domicilio = Domicilio.objects.create(
            nombre='Carlos',
            apellido='Lopez',
            telefono_negocio='3001234822',
        )
        paquete = Paquete.objects.create(
            nombre='Ana',
            apellido='Gil',
            transportadora='Mensajería',
        )
        visitante = Visitante.objects.create(
            nombre='Pedro',
            apellido='Diaz',
            cedula='771022',
            vehiculo_trae='NO',
        )
        fecha = timezone.now()
        Proceso.objects.create(
            tipo='Domicilio',
            estado='PENDIENTE',
            nombre='Carlos Lopez',
            fecha=fecha,
            id_guardia=guardia,
            id_casa=casa,
            id_domicilio=domicilio,
        )
        Proceso.objects.create(
            tipo='Paquete',
            estado='ENTREGADO',
            nombre='Ana Gil',
            fecha=fecha,
            id_guardia=guardia,
            id_casa=casa,
            id_paquete=paquete,
        )
        Proceso.objects.create(
            tipo='Visitante',
            estado='PENDIENTE',
            nombre='Pedro Diaz',
            fecha=fecha,
            id_guardia=guardia,
            id_casa=casa,
            id_visitante=visitante,
        )
        Pago.objects.create(
            valor=Decimal('100.00'),
            fecha=timezone.localdate(),
            estado='Pendiente',
            id_casa=casa,
        )
        Notas.objects.create(
            nombre='Clara',
            apellido='Diaz',
            nota='Revisar luminaria.',
            id_guardia=guardia,
        )
        self.client.force_login(administrador)

        configuracion_actualizada = self.client.post(
            reverse('configuracion_cartera'),
            {
                'porcentaje_mora': '2.50',
                'monto_aumento_mensual': '0.00',
                'dia_vencimiento': '28',
                'frecuencia_mora': 'mensual',
                'tiempo_domiciliario_minutos': '5',
                'estado_domicilio_0_nombre': 'En reparto',
                'estado_domicilio_0_color': '#123456',
                'estado_domicilio_1_nombre': 'Demora personalizada',
                'estado_domicilio_1_color': '#654321',
                'estado_visitante_0_nombre': 'Visita autorizada',
                'estado_visitante_0_color': '#234567',
                'estado_paquete_1_nombre': 'Entregado al residente',
                'estado_paquete_1_color': '#345678',
                'estado_pago_1_nombre': 'Saldo por pagar',
                'estado_pago_1_color': '#456789',
                'estado_nota_0_nombre': 'Nota recibida',
                'estado_nota_0_color': '#654321',
                'estado_casa_1_nombre': 'Habitada',
                'estado_casa_1_color': '#56789a',
            },
        )

        self.assertRedirects(configuracion_actualizada, reverse('configuracion_cartera'))
        comprobaciones = (
            ('registrar_domicilio', 'En reparto', '#123456'),
            ('registrar_paquete', 'Entregado al residente', '#345678'),
            ('registrar_pago', 'Saldo por pagar', '#456789'),
            ('registrar_casa', 'Habitada', '#56789a'),
            ('movimientos', 'Visita autorizada', '#234567'),
            ('dashboard', 'Visita autorizada', '#234567'),
        )
        for ruta, nombre_visible, color in comprobaciones:
            with self.subTest(modulo=ruta):
                respuesta = self.client.get(reverse(ruta))
                self.assertEqual(respuesta.status_code, 200)
                self.assertContains(respuesta, nombre_visible)
                self.assertContains(respuesta, f'background-color: {color}')
                if ruta == 'registrar_casa':
                    self.assertContains(respuesta, '<option value="Ocupada">Habitada</option>', html=True)
                if ruta == 'registrar_visitante':
                    self.assertContains(respuesta, 'Visita autorizada')
                if ruta == 'registrar_paquete':
                    self.assertContains(
                        respuesta,
                        '<option value="ENTREGADO">Entregado al residente</option>',
                        html=True,
                    )
                if ruta == 'registrar_pago':
                    self.assertContains(respuesta, '<option value="Pendiente">Saldo por pagar</option>', html=True)
                if ruta == 'registrar_nota':
                    self.assertContains(respuesta, 'Nota recibida')
                if ruta in ('movimientos', 'dashboard'):
                    self.assertGreaterEqual(
                        respuesta.content.decode().count(nombre_visible),
                        2,
                    )
        respuesta_domicilio = self.client.get(reverse('registrar_domicilio'))
        self.assertContains(respuesta_domicilio, 'Demora personalizada')
        self.assertContains(
            respuesta_domicilio,
            "window.aplicarEstadoVisual(etiqueta, 'domicilio', 'DEMORADO')",
        )

    # Verifica el comportamiento de nombre visible estado solo acepta letras y espacios y sus condiciones relevantes.
    def test_nombre_visible_estado_solo_acepta_letras_y_espacios(self):
        configuracion = ConfiguracionCartera.objects.get(pk=1)
        datos = {
            'porcentaje_mora': '2.50',
            'monto_aumento_mensual': '12500',
            'dia_vencimiento': '28',
            'frecuencia_mora': 'mensual',
            'tiempo_domiciliario_minutos': '5',
            'estado_domicilio_0_color': '#123456',
        }

        for nombre_invalido in ('Salida 2', 'Salida!'):
            with self.subTest(nombre=nombre_invalido):
                formulario = ConfiguracionCarteraForm(
                    data={**datos, 'estado_domicilio_0_nombre': nombre_invalido},
                    instance=configuracion,
                )
                self.assertFalse(formulario.is_valid())
                self.assertIn('estado_domicilio_0_nombre', formulario.errors)

        formulario = ConfiguracionCarteraForm(
            data={**datos, 'estado_domicilio_0_nombre': 'Salió a tiempo'},
            instance=configuracion,
        )
        self.assertTrue(formulario.is_valid(), formulario.errors)
        self.assertEqual(formulario.cleaned_data['porcentaje_mora'], Decimal('2.50'))
        self.assertEqual(formulario.cleaned_data['dia_vencimiento'], 28)
        self.assertEqual(formulario.cleaned_data['tiempo_domiciliario_minutos'], 5)

    # Verifica el comportamiento de tiempo domiciliario debe ser de un minuto como minimo y sus condiciones relevantes.
    def test_tiempo_domiciliario_debe_ser_de_un_minuto_como_minimo(self):
        configuracion = ConfiguracionCartera.objects.get(pk=1)
        form = ConfiguracionCarteraForm(data={
            'porcentaje_mora': configuracion.porcentaje_mora,
            'monto_aumento_mensual': configuracion.monto_aumento_mensual,
            'dia_vencimiento': configuracion.dia_vencimiento,
            'frecuencia_mora': configuracion.frecuencia_mora,
            'tiempo_domiciliario_minutos': '0',
        }, instance=configuracion)

        self.assertFalse(form.is_valid())
        self.assertIn('tiempo_domiciliario_minutos', form.errors)

    # Verifica el comportamiento de alerta de domiciliario usa el tiempo configurado y sus condiciones relevantes.
    def test_alerta_de_domiciliario_usa_el_tiempo_configurado(self):
        configuracion = ConfiguracionCartera.objects.get(pk=1)
        configuracion.tiempo_domiciliario_minutos = 3
        configuracion.save(update_fields=('tiempo_domiciliario_minutos',))
        administrador = User.objects.create_user(username='admin-tiempo-domicilio', password='clave', is_staff=True)
        guardia_usuario = User.objects.create_user(username='guardia-tiempo-domicilio', password='clave')
        guardia = Guardia.objects.create(
            cedula=987650,
            nombre='Laura',
            apellido='Rojas',
            telefono='3001234500',
            turno='Mañana',
            usuario=guardia_usuario,
        )
        casa = Casa.objects.create(numero_casa=990, cantidad_personas=2, cantidad_residentes=1, estado='Ocupada')
        domicilio = Domicilio.objects.create(nombre='Carlos', apellido='Perez', telefono_negocio='3001234567')
        ahora = timezone.now()
        dentro_del_limite = Proceso.objects.create(
            tipo='Domicilio',
            nombre='Carlos Perez',
            fecha=ahora - timedelta(minutes=2),
            id_guardia=guardia,
            id_casa=casa,
            id_domicilio=domicilio,
        )
        primera_demora = Proceso.objects.create(
            tipo='Domicilio',
            nombre='Carlos Perez',
            fecha=ahora - timedelta(minutes=4),
            id_guardia=guardia,
            id_casa=casa,
            id_domicilio=domicilio,
        )
        supero_el_limite = Proceso.objects.create(
            tipo='Domicilio',
            nombre='Carlos Perez',
            fecha=ahora - timedelta(minutes=3, seconds=1),
            id_guardia=guardia,
            id_casa=casa,
            id_domicilio=domicilio,
        )
        self.client.force_login(administrador)

        response = self.client.get(reverse('domicilios_demorados'))

        self.assertEqual(response.status_code, 200)
        domicilios_demorados = response.json()['domicilios']
        self.assertEqual([item['id'] for item in domicilios_demorados], [primera_demora.pk, supero_el_limite.pk])
        self.assertEqual(domicilios_demorados[0], {
            'id': primera_demora.pk,
            'nombre': 'Carlos Perez',
            'casa': casa.numero_casa,
        })
        self.assertNotIn(dentro_del_limite.pk, [item['id'] for item in domicilios_demorados])

        pantalla_domicilios = self.client.get(reverse('registrar_domicilio'))
        self.assertEqual(pantalla_domicilios.status_code, 200)
        self.assertContains(pantalla_domicilios, 'data-floating-help')
        self.assertContains(pantalla_domicilios, 'Manual técnico')
        self.assertContains(pantalla_domicilios, 'core/sounds/alarma.mp3')
        self.assertContains(pantalla_domicilios, 'data-limite-segundos="180"')
        self.assertContains(pantalla_domicilios, '<span class="temporizador">03:00</span>', html=True)

        self.client.post(reverse('registrar_domicilio'), {
            'action': 'delivered',
            'domicilio_id': domicilio.pk,
        })
        dentro_del_limite.refresh_from_db()
        self.assertEqual(dentro_del_limite.estado, 'ENTREGADO')
        self.assertGreater(dentro_del_limite.tiempo_restante, 0)
        self.assertLessEqual(dentro_del_limite.tiempo_restante, 60)


# Agrupa pruebas automatizadas relacionadas con copias seguridad pruebas.
class CopiasSeguridadTests(TransactionTestCase):
    # Organiza el flujo de asignación up dentro de este módulo.
    def setUp(self):
        self.directorio_temporal = tempfile.TemporaryDirectory()
        self.addCleanup(self.directorio_temporal.cleanup)
        self.proyecto_temporal = Path(self.directorio_temporal.name) / 'proyecto'
        self.proyecto_temporal.mkdir()
        self.enterContext(override_settings(BASE_DIR=self.proyecto_temporal))
        self.directorio_copias = Path(self.directorio_temporal.name) / 'copia de seguridad Piemonte'
        self.media_temporal = self.proyecto_temporal / 'media'
        self.media_temporal.mkdir()
        self.enterContext(override_settings(MEDIA_ROOT=self.media_temporal))
        self.administrador = User.objects.create_user(
            username='admin-copias-seguridad',
            password='Clave-segura1!',
            is_staff=True,
        )

    def test_lector_json_incremental_maneja_registros_fragmentados(self):
        from BD.copias_seguridad import _iterar_lista_json

        registros_esperados = [
            {'model': 'BD.novedad', 'fields': {'nota': 'texto [con llaves] y "comillas" ' + ('á' * 70000)}},
            {'model': 'auth.user', 'fields': {'username': 'usuario'}},
        ]

        self.assertEqual(
            list(_iterar_lista_json(StringIO(json.dumps(registros_esperados, ensure_ascii=False)))),
            registros_esperados,
        )
        with self.assertRaisesRegex(ValueError, 'separador inválido'):
            list(_iterar_lista_json(StringIO('[{},]')))

    # Verifica el comportamiento de administrador ve el modulo y puede guardar la frecuencia y sus condiciones relevantes.
    def test_administrador_ve_el_modulo_y_puede_guardar_la_frecuencia(self):
        self.client.force_login(self.administrador)

        pagina = self.client.get(reverse('copias_seguridad'))

        self.assertEqual(pagina.status_code, 200)
        self.assertContains(pagina, 'Copias de Seguridad')
        self.assertContains(pagina, 'Solo información')
        self.assertContains(pagina, 'Subir y fusionar')
        self.assertContains(pagina, 'Subir ZIP del proyecto')
        self.assertContains(pagina, '¿Fusionar esta información?')
        self.assertContains(pagina, '¿Eliminar este elemento?')
        self.assertContains(pagina, 'data-confirm-delete')
        self.assertContains(pagina, str(self.directorio_copias))
        self.assertContains(pagina, 'Seleccionar carpeta')
        self.assertContains(pagina, 'equipo donde corre Piemonte')
        destino_alternativo = Path(self.directorio_temporal.name) / 'dispositivo externo' / 'Piemonte'

        respuesta = self.client.post(reverse('copias_seguridad'), {
            'accion': 'guardar_programacion',
            'intervalo': '3',
            'unidad_intervalo': 'horas',
            'automaticas_activas': 'on',
            'ruta_destino': str(destino_alternativo),
        })

        self.assertRedirects(respuesta, reverse('copias_seguridad'), fetch_redirect_response=False)
        configuracion = ConfiguracionCopiasSeguridad.objects.get(pk=1)
        self.assertEqual(configuracion.intervalo, 3)
        self.assertEqual(configuracion.unidad_intervalo, 'horas')
        self.assertTrue(configuracion.automaticas_activas)
        self.assertEqual(configuracion.ruta_destino, str(destino_alternativo))
        self.assertGreater(configuracion.proxima_automatica, timezone.now())
        pagina_con_resultado = self.client.get(reverse('copias_seguridad'))
        self.assertContains(pagina_con_resultado, str(destino_alternativo))
        self.assertContains(pagina_con_resultado, 'id="siteNotificationModal"')
        self.assertContains(pagina_con_resultado, 'La programación y la carpeta de destino se guardaron correctamente.')

    # Verifica el comportamiento de frecuencia debe ser positiva y maximo 365 y sus condiciones relevantes.
    def test_frecuencia_debe_ser_positiva_y_maximo_365(self):
        configuracion = ConfiguracionCopiasSeguridad()
        for intervalo in ('0', '366'):
            form = ConfiguracionCopiasSeguridadForm(data={
                'intervalo': intervalo,
                'unidad_intervalo': 'dias',
                'automaticas_activas': 'on',
            }, instance=configuracion)
            self.assertFalse(form.is_valid())
            self.assertIn('intervalo', form.errors)

    # Verifica el comportamiento de ruta de destino debe ser absoluta y externa al proyecto y sus condiciones relevantes.
    def test_ruta_de_destino_debe_ser_absoluta_y_externa_al_proyecto(self):
        for ruta in ('copias-relativas', str(self.proyecto_temporal / 'dentro-del-proyecto')):
            form = ConfiguracionCopiasSeguridadForm(data={
                'intervalo': '1',
                'unidad_intervalo': 'dias',
                'automaticas_activas': 'on',
                'ruta_destino': ruta,
            })
            self.assertFalse(form.is_valid())
            self.assertIn('ruta_destino', form.errors)

    # Verifica el comportamiento de selector de carpetas lista subcarpetas para administrador y sus condiciones relevantes.
    def test_selector_de_carpetas_lista_subcarpetas_para_administrador(self):
        from BD.copias_seguridad import directorio_copias

        carpeta_destino = self.proyecto_temporal.parent / 'carpeta selector'
        (carpeta_destino / 'subcarpeta').mkdir(parents=True)
        (carpeta_destino / 'archivo.txt').write_text('No mostrar como carpeta', encoding='utf-8')
        self.client.force_login(self.administrador)

        respuesta = self.client.get(
            reverse('explorar_carpetas_copias_seguridad'),
            {'ruta': str(carpeta_destino)},
        )

        self.assertEqual(respuesta.status_code, 200)
        datos = respuesta.json()
        self.assertEqual(datos['actual'], str(carpeta_destino.resolve()))
        self.assertIn('subcarpeta', [carpeta['nombre'] for carpeta in datos['carpetas']])
        self.assertNotIn('archivo.txt', [carpeta['nombre'] for carpeta in datos['carpetas']])

    # Verifica el comportamiento de selector de carpetas requiere administrador y sus condiciones relevantes.
    def test_selector_de_carpetas_requiere_administrador(self):
        usuario = User.objects.create_user(username='usuario-selector', password='Clave-segura1!')
        self.client.force_login(usuario)

        respuesta = self.client.get(reverse('explorar_carpetas_copias_seguridad'))

        self.assertEqual(respuesta.status_code, 302)

    def test_selector_de_carpetas_muestra_raices_sin_listdrives(self):
        from BD.views import explorar_carpetas_copias_seguridad_view

        solicitud = RequestFactory().get(reverse('explorar_carpetas_copias_seguridad'))
        solicitud.user = self.administrador
        with patch('BD.views.os.name', 'posix'):
            respuesta = explorar_carpetas_copias_seguridad_view(solicitud)

        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(json.loads(respuesta.content)['carpetas'])

    # Verifica el comportamiento de copia manual incluye todo el programa y deduplica contenido igual y sus condiciones relevantes.
    def test_copia_manual_incluye_todo_el_programa_y_deduplica_contenido_igual(self):
        from BD.copias_seguridad import crear_copia_seguridad

        configuracion = ConfiguracionCopiasSeguridad.objects.create(
            pk=1,
            intervalo=2,
            unidad_intervalo='horas',
            ruta_destino=str(self.directorio_copias),
        )
        (self.proyecto_temporal / 'manage.py').write_text('print("Piemonte")', encoding='utf-8')
        (self.media_temporal / 'comprobantes').mkdir()
        archivo_media = self.media_temporal / 'comprobantes' / 'prueba.txt'
        archivo_media.write_text('Evidencia de prueba', encoding='utf-8')
        archivo_esquema = self.proyecto_temporal / 'database' / 'piemonte_schema.sql'
        archivo_esquema.parent.mkdir()
        archivo_esquema.write_text('CREATE TABLE ejemplo (id INTEGER);', encoding='utf-8')
        archivo_heredado = self.proyecto_temporal / 'evidencias_paquetes' / 'goku.jpg'
        archivo_heredado.parent.mkdir()
        archivo_heredado.write_bytes(b'archivo de evidencia heredado')

        primera, creada = crear_copia_seguridad(tipo='manual', usuario=self.administrador)
        nombre_primera_copia = primera.archivo
        segunda, segunda_creada = crear_copia_seguridad(tipo='manual', usuario=self.administrador)

        self.assertTrue(creada)
        self.assertTrue(segunda_creada)
        self.assertEqual(primera.pk, segunda.pk)
        self.assertEqual(CopiaSeguridad.objects.count(), 1)
        primera.refresh_from_db()
        self.assertNotEqual(primera.archivo, nombre_primera_copia)
        self.assertFalse((self.directorio_copias / nombre_primera_copia).exists())
        ruta_copia = self.directorio_copias / primera.archivo
        self.assertTrue(ruta_copia.is_file())
        with zipfile.ZipFile(ruta_copia) as archivo_zip:
            contenido_zip = archivo_zip.namelist()
            self.assertIn('program/manage.py', contenido_zip)
            self.assertIn('program/media/comprobantes/prueba.txt', contenido_zip)
            self.assertIn('program/database/piemonte_schema.sql', contenido_zip)
            self.assertIn('program/evidencias_paquetes/goku.jpg', contenido_zip)
            self.assertIn('manifest.json', archivo_zip.namelist())
            manifiesto = json.loads(archivo_zip.read('manifest.json').decode('utf-8'))
            if connection.vendor == 'sqlite':
                self.assertIn('program/BD.sqlite3', contenido_zip)
                ruta_db_restaurada = Path(self.directorio_temporal.name) / 'base-restaurada.sqlite3'
                ruta_db_restaurada.write_bytes(archivo_zip.read('program/BD.sqlite3'))
                with closing(sqlite3.connect(ruta_db_restaurada)) as base_restaurada:
                    tablas = {
                        fila[0]
                        for fila in base_restaurada.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
                    }
                    self.assertIn('auth_user', tablas)
                    self.assertIn('configuracion_copias_seguridad', tablas)
                    self.assertIn('copia_seguridad', tablas)
                    usuario_restaurado = base_restaurada.execute(
                        'SELECT username FROM auth_user WHERE username = ?',
                        (self.administrador.username,),
                    ).fetchone()
                    configuracion_restaurada = base_restaurada.execute(
                        'SELECT ruta_destino FROM configuracion_copias_seguridad WHERE id = 1'
                    ).fetchone()
                    self.assertEqual(usuario_restaurado[0], self.administrador.username)
                    self.assertEqual(configuracion_restaurada[0], str(self.directorio_copias))
                self.assertEqual(manifiesto['motor_base_datos'], 'sqlite')
            else:
                ruta_fixture = 'program/database/piemonte_mysql.jsonl'
                self.assertIn(ruta_fixture, contenido_zip)
                with archivo_zip.open(ruta_fixture) as fixture:
                    cabecera = json.loads(fixture.readline().decode('utf-8'))
                self.assertEqual(cabecera['backend'], 'mysql')
                self.assertEqual(manifiesto['motor_base_datos'], 'mysql')

        otro_dispositivo = Path(self.directorio_temporal.name) / 'otro dispositivo' / 'Piemonte'
        configuracion.ruta_destino = str(otro_dispositivo)
        configuracion.save(update_fields=('ruta_destino',))
        tercera, tercera_creada = crear_copia_seguridad(tipo='manual', usuario=self.administrador)
        cuarta, cuarta_creada = crear_copia_seguridad(tipo='manual', usuario=self.administrador)

        self.assertTrue(tercera_creada)
        self.assertTrue(cuarta_creada)
        self.assertEqual(primera.pk, tercera.pk)
        self.assertEqual(tercera.pk, cuarta.pk)
        self.assertEqual(CopiaSeguridad.objects.count(), 1)
        cuarta.refresh_from_db()
        self.assertTrue(Path(cuarta.ruta_archivo).is_file())
        self.client.force_login(self.administrador)
        descarga_primera = self.client.get(reverse('descargar_copia_seguridad', args=(primera.pk,)))
        self.assertEqual(descarga_primera.status_code, 200)
        descarga_primera.close()

    def test_copia_de_informacion_segun_backend_y_actualiza_el_duplicado(self):
        from BD.copias_seguridad import crear_copia_seguridad

        ConfiguracionCopiasSeguridad.objects.create(
            pk=1,
            intervalo=1,
            ruta_destino=str(self.directorio_copias),
        )

        primera, creada_primera = crear_copia_seguridad(alcance='informacion', usuario=self.administrador)
        nombre_anterior = primera.archivo
        segunda, creada_segunda = crear_copia_seguridad(alcance='informacion', usuario=self.administrador)

        self.assertTrue(creada_primera)
        self.assertTrue(creada_segunda)
        self.assertEqual(primera.pk, segunda.pk)
        self.assertEqual(segunda.alcance, 'informacion')
        self.assertFalse((self.directorio_copias / nombre_anterior).exists())
        if connection.vendor == 'sqlite':
            self.assertTrue(segunda.archivo.endswith('.sqlite3'))
            with closing(sqlite3.connect(segunda.ruta_archivo)) as base:
                tablas = {fila[0] for fila in base.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
            self.assertIn('auth_user', tablas)
            self.assertNotIn('program', tablas)
        else:
            self.assertTrue(segunda.archivo.endswith('.jsonl'))
            with Path(segunda.ruta_archivo).open(encoding='utf-8') as fixture:
                cabecera = json.loads(fixture.readline())
                self.assertEqual(cabecera['backend'], 'mysql')
                self.assertIn('auth.user', cabecera['models'])

    def test_subir_zip_completo_valida_y_actualiza_la_copia_sin_extraerlo(self):
        from BD.copias_seguridad import crear_copia_seguridad

        ConfiguracionCopiasSeguridad.objects.create(
            pk=1,
            intervalo=1,
            ruta_destino=str(self.directorio_copias),
        )
        (self.proyecto_temporal / 'manage.py').write_text('print("Piemonte")', encoding='utf-8')
        copia, _ = crear_copia_seguridad(usuario=self.administrador)
        nombre_anterior = copia.archivo
        archivo_subido = SimpleUploadedFile(
            'piemonte.zip',
            Path(copia.ruta_archivo).read_bytes(),
            content_type='application/zip',
        )
        self.client.force_login(self.administrador)

        respuesta = self.client.post(
            reverse('subir_copia_proyecto'),
            {'archivo_proyecto': archivo_subido},
        )

        self.assertRedirects(respuesta, reverse('copias_seguridad'))
        copia.refresh_from_db()
        self.assertEqual(CopiaSeguridad.objects.filter(alcance='proyecto').count(), 1)
        self.assertNotEqual(copia.archivo, nombre_anterior)
        self.assertFalse((self.directorio_copias / nombre_anterior).exists())
        self.assertTrue(Path(copia.ruta_archivo).is_file())
        self.assertTrue(zipfile.is_zipfile(copia.ruta_archivo))

    def test_subir_zip_completo_rechaza_rutas_fuera_del_proyecto(self):
        from BD.copias_seguridad import subir_copia_proyecto

        ConfiguracionCopiasSeguridad.objects.create(
            pk=1,
            intervalo=1,
            ruta_destino=str(self.directorio_copias),
        )
        contenido = BytesIO()
        with zipfile.ZipFile(contenido, 'w') as paquete:
            paquete.writestr('manifest.json', '{}')
            paquete.writestr('program/../fuera.txt', 'no debe extraerse')
        archivo_subido = SimpleUploadedFile(
            'invalido.zip',
            contenido.getvalue(),
            content_type='application/zip',
        )

        with self.assertRaisesRegex(ValueError, 'rutas, enlaces o archivos no permitidos'):
            subir_copia_proyecto(archivo_subido, self.administrador)

        self.assertFalse(CopiaSeguridad.objects.filter(alcance='proyecto').exists())
        self.assertEqual(list(self.directorio_copias.iterdir()), [])

    def test_retencion_conserva_las_cuatro_copias_mas_recientes_de_cada_alcance(self):
        from BD.copias_seguridad import _aplicar_retencion

        copias_por_alcance = {'informacion': [], 'proyecto': []}
        hora = timezone.now()
        for alcance in copias_por_alcance:
            for indice in range(6):
                nombre = f'{alcance}_{indice}.sqlite3'
                ruta = self.directorio_copias / nombre
                ruta.parent.mkdir(parents=True, exist_ok=True)
                ruta.write_bytes(b'copia')
                copias_por_alcance[alcance].append(CopiaSeguridad.objects.create(
                    archivo=nombre,
                    ruta_archivo=str(ruta),
                    sha256=f'{indice:032x}{len(alcance):032x}',
                    tipo='manual',
                    alcance=alcance,
                    creado_en=hora + timedelta(seconds=indice),
                    tamano_bytes=ruta.stat().st_size,
                ))

        for alcance, copias_creadas in copias_por_alcance.items():
            _aplicar_retencion(alcance)
            self.assertEqual(CopiaSeguridad.objects.filter(alcance=alcance).count(), 4)
            for copia in copias_creadas[:2]:
                self.assertFalse(Path(copia.ruta_archivo).exists())
            for copia in copias_creadas[2:]:
                self.assertTrue(Path(copia.ruta_archivo).exists())

    def test_mezcla_agrega_faltantes_y_no_reemplaza_registros_por_versiones_antiguas(self):
        from BD.copias_seguridad import _mezclar_bases_datos

        ruta_actual = Path(self.directorio_temporal.name) / 'actual.sqlite3'
        ruta_copia = Path(self.directorio_temporal.name) / 'copia.sqlite3'
        for ruta in (ruta_actual, ruta_copia):
            with closing(sqlite3.connect(ruta)) as base:
                base.execute(
                    'CREATE TABLE registro (id INTEGER PRIMARY KEY, fecha_creacion TEXT, valor TEXT)'
                )
        with closing(sqlite3.connect(ruta_actual)) as base:
            base.executemany('INSERT INTO registro VALUES (?, ?, ?)', [
                (1, '2026-11-10T00:00:00+00:00', 'actual reciente'),
                (3, '2026-11-01T00:00:00+00:00', 'solo actual'),
                (4, '2026-11-10T00:00:00+00:00', 'actual antiguo'),
            ])
            base.commit()
        with closing(sqlite3.connect(ruta_copia)) as base:
            base.executemany('INSERT INTO registro VALUES (?, ?, ?)', [
                (1, '2026-11-09T00:00:00+00:00', 'copia antigua'),
                (2, '2026-11-12T00:00:00+00:00', 'faltante'),
                (4, '2026-11-13T00:00:00+00:00', 'copia reciente'),
            ])
            base.commit()

        agregados, actualizados = _mezclar_bases_datos(ruta_actual, ruta_copia)

        self.assertEqual((agregados, actualizados), (1, 1))
        with closing(sqlite3.connect(ruta_actual)) as base:
            registros = dict(base.execute('SELECT id, valor FROM registro'))
        self.assertEqual(registros, {
            1: 'actual reciente',
            2: 'faltante',
            3: 'solo actual',
            4: 'copia reciente',
        })

    @skipUnless(connection.vendor == 'sqlite', 'Esta prueba modifica directamente una instantánea SQLite.')
    def test_restaurar_informacion_fusiona_sin_perder_registros_actuales(self):
        from BD.copias_seguridad import restaurar_copia_informacion

        ConfiguracionCopiasSeguridad.objects.create(
            pk=1,
            intervalo=1,
            ruta_destino=str(self.directorio_copias),
        )
        anterior = Novedad.objects.create(titulo='Conflicto anterior', nota='valor actual reciente')
        versionable = Novedad.objects.create(titulo='Conflicto versionable', nota='valor actual antiguo')
        Novedad.objects.filter(pk=anterior.pk).update(fecha_creacion='2026-11-10T00:00:00+00:00')
        Novedad.objects.filter(pk=versionable.pk).update(fecha_creacion='2026-11-10T00:00:00+00:00')
        ruta_copia = Path(self.directorio_temporal.name) / 'datos.sqlite3'
        with closing(sqlite3.connect(ruta_copia)) as base_copia:
            connection.ensure_connection()
            connection.connection.backup(base_copia)
            base_copia.execute(
                'UPDATE novedad SET nota = ?, fecha_creacion = ? WHERE id_novedad = ?',
                ('valor antiguo de copia', '2026-11-09T00:00:00+00:00', anterior.pk),
            )
            base_copia.execute(
                'UPDATE novedad SET nota = ?, fecha_creacion = ? WHERE id_novedad = ?',
                ('valor reciente de copia', '2026-11-13T00:00:00+00:00', versionable.pk),
            )
            base_copia.execute(
                'INSERT INTO novedad (titulo, tipo, nota, evidencia, fecha_creacion, fecha, registrado_por) '
                'VALUES (?, ?, ?, ?, ?, ?, ?)',
                ('Registro faltante', 'General', 'desde copia', '', '2026-11-12T00:00:00+00:00',
                 '2026-11-12T00:00:00+00:00', None),
            )
            base_copia.commit()
        solo_actual = Novedad.objects.create(
            id_novedad=90001,
            titulo='Solo actual',
            nota='no debe desaparecer',
        )

        archivo = SimpleUploadedFile(
            'piemonte_informacion.sqlite3',
            ruta_copia.read_bytes(),
            content_type='application/x-sqlite3',
        )
        _, copia_importada, agregados, actualizados = restaurar_copia_informacion(
            archivo,
            self.administrador,
        )

        anterior.refresh_from_db()
        versionable.refresh_from_db()
        solo_actual.refresh_from_db()
        self.assertEqual(anterior.nota, 'valor actual reciente')
        self.assertEqual(versionable.nota, 'valor reciente de copia')
        self.assertEqual(solo_actual.nota, 'no debe desaparecer')
        self.assertTrue(Novedad.objects.filter(titulo='Registro faltante').exists())
        self.assertGreaterEqual(agregados, 1)
        self.assertGreaterEqual(actualizados, 1)
        self.assertTrue(Path(copia_importada.ruta_archivo).is_file())

    @skipUnless(connection.vendor == 'sqlite', 'Esta prueba crea directamente una instantánea SQLite.')
    def test_subir_copia_identica_muestra_modal_y_detiene_la_fusion(self):
        ConfiguracionCopiasSeguridad.objects.create(
            pk=1,
            intervalo=1,
            ruta_destino=str(self.directorio_copias),
        )
        Novedad.objects.create(titulo='Registro que debe conservarse', nota='actual')
        ruta_copia = Path(self.directorio_temporal.name) / 'respaldo.sqlite3'
        with closing(sqlite3.connect(ruta_copia)) as base_copia:
            connection.ensure_connection()
            connection.connection.backup(base_copia)
        archivo = SimpleUploadedFile(
            'piemonte_informacion.sqlite3',
            ruta_copia.read_bytes(),
            content_type='application/x-sqlite3',
        )
        self.client.force_login(self.administrador)
        with patch.dict(connection.settings_dict, {'NAME': str(self.proyecto_temporal / 'BD.sqlite3')}):
            respuesta = self.client.post(
                reverse('restaurar_copia_informacion'),
                {
                    'confirmar_restauracion': 'on',
                    'archivo_copia': archivo,
                },
                follow=True,
            )

        self.assertEqual(respuesta.status_code, 200)
        mensajes = [str(mensaje) for mensaje in respuesta.context['messages']]
        self.assertIn('Esta copia es idéntica a la información actual; no se realizó la fusión.', mensajes)
        self.assertContains(respuesta, 'id="siteNotificationModal"')
        self.assertFalse(CopiaSeguridad.objects.exists())
        self.assertTrue(Novedad.objects.filter(titulo='Registro que debe conservarse').exists())

    def test_copia_mysql_de_informacion_genera_un_fixture_validado(self):
        from BD.copias_seguridad import _validar_copia_mysql, crear_copia_seguridad

        Novedad.objects.create(titulo='Respaldo MySQL', nota='registro de prueba')
        with patch.object(connection, 'vendor', 'mysql'):
            copia, creada = crear_copia_seguridad(
                alcance='informacion',
                usuario=self.administrador,
            )

        self.assertTrue(creada)
        self.assertTrue(copia.archivo.endswith('.jsonl'))
        cabecera = _validar_copia_mysql(copia.ruta_archivo)
        self.assertEqual(cabecera['backend'], 'mysql')
        self.assertIn('BD.novedad', cabecera['models'])
        self.assertIn('auth.user', cabecera['models'])

    def test_copia_mysql_de_proyecto_incluye_fixture_y_valida_el_manifiesto(self):
        from BD.copias_seguridad import _validar_copia_proyecto, crear_copia_seguridad

        (self.proyecto_temporal / 'manage.py').write_text('print("Piemonte")', encoding='utf-8')
        with patch.object(connection, 'vendor', 'mysql'):
            copia, creada = crear_copia_seguridad(usuario=self.administrador)

        self.assertTrue(creada)
        with zipfile.ZipFile(copia.ruta_archivo) as paquete:
            rutas = paquete.namelist()
            ruta_fixture = 'program/database/piemonte_mysql.jsonl'
            self.assertIn(ruta_fixture, rutas)
            manifiesto = json.loads(paquete.read('manifest.json').decode('utf-8'))
            self.assertEqual(manifiesto['motor_base_datos'], 'mysql')
            cabecera = json.loads(paquete.read(ruta_fixture).splitlines()[0].decode('utf-8'))
            self.assertEqual(cabecera['backend'], 'mysql')
        self.assertEqual(_validar_copia_proyecto(copia.ruta_archivo), manifiesto['sha256_contenido'])

    def test_restaurar_fixture_mysql_agrega_faltantes_y_solo_actualiza_versiones_mas_recientes(self):
        from BD.copias_seguridad import _exportar_fixture_mysql, restaurar_copia_informacion

        actual = Novedad.objects.create(titulo='Conflicto MySQL', nota='versión actual')
        fecha_actual = timezone.now() - timedelta(days=2)
        fecha_copia = timezone.now() + timedelta(days=2)
        Novedad.objects.filter(pk=actual.pk).update(fecha_creacion=fecha_actual)

        ruta_fixture = Path(self.directorio_temporal.name) / 'copia-mysql.jsonl'
        _exportar_fixture_mysql(ruta_fixture)
        lineas = ruta_fixture.read_text(encoding='utf-8').splitlines()
        registros = [json.loads(linea) for linea in lineas[1:]]
        registro_actual = next(
            registro for registro in registros
            if registro.get('model') == 'BD.novedad' and registro.get('pk') == actual.pk
        )
        registro_actual['fields']['fecha_creacion'] = fecha_copia.isoformat()
        registro_actual['fields']['nota'] = 'versión más reciente de la copia'
        mayor_pk = (Novedad.objects.order_by('-pk').values_list('pk', flat=True).first() or 0) + 10000
        registro_nuevo = json.loads(json.dumps(registro_actual))
        registro_nuevo['pk'] = mayor_pk
        registro_nuevo['fields']['titulo'] = 'Registro agregado desde MySQL'
        registros.append(registro_nuevo)
        ruta_fixture.write_text(
            '\n'.join([lineas[0]] + [
                json.dumps(registro, ensure_ascii=False, separators=(',', ':'))
                for registro in registros
            ]) + '\n',
            encoding='utf-8',
        )
        archivo = SimpleUploadedFile(
            'piemonte_informacion.jsonl',
            ruta_fixture.read_bytes(),
            content_type='application/x-ndjson',
        )

        with patch.object(connection, 'vendor', 'mysql'):
            _, copia_importada, agregados, actualizados = restaurar_copia_informacion(
                archivo,
                self.administrador,
            )

        actual.refresh_from_db()
        self.assertEqual(actual.nota, 'versión más reciente de la copia')
        self.assertGreaterEqual(agregados, 1)
        self.assertGreaterEqual(actualizados, 1)
        self.assertTrue(Novedad.objects.filter(pk=mayor_pk, titulo='Registro agregado desde MySQL').exists())
        self.assertTrue(Path(copia_importada.ruta_archivo).is_file())

    # Verifica el comportamiento de accion manual crea y descarga el archivo comprimido y sus condiciones relevantes.
    def test_accion_manual_crea_y_descarga_el_archivo_comprimido(self):
        self.client.force_login(self.administrador)

        respuesta = self.client.post(reverse('copias_seguridad'), {'accion': 'crear_manual'})

        self.assertRedirects(respuesta, reverse('copias_seguridad'))
        copia = CopiaSeguridad.objects.get()
        self.assertEqual(copia.tipo, 'manual')
        self.assertTrue(Path(copia.ruta_archivo).is_file())
        descarga = self.client.get(reverse('descargar_copia_seguridad', args=(copia.pk,)))
        self.assertEqual(descarga.status_code, 200)
        self.assertTrue(descarga['Content-Disposition'].startswith('attachment;'))
        descarga.close()

    # Verifica el comportamiento de administrador puede eliminación una copia y sus condiciones relevantes.
    def test_administrador_puede_eliminar_una_copia(self):
        from BD.copias_seguridad import crear_copia_seguridad

        copia, _ = crear_copia_seguridad(tipo='manual', usuario=self.administrador)
        ruta_copia = self.directorio_copias / copia.archivo
        self.client.force_login(self.administrador)
        pagina = self.client.get(reverse('copias_seguridad'))
        self.assertContains(pagina, 'id="confirmarEliminacionGlobal"')
        self.assertContains(pagina, f'data-delete-label="{copia.archivo}"')

        respuesta = self.client.post(reverse('eliminar_copia_seguridad', args=(copia.pk,)))

        self.assertRedirects(respuesta, reverse('copias_seguridad'))
        self.assertFalse(ruta_copia.exists())
        self.assertFalse(CopiaSeguridad.objects.filter(pk=copia.pk).exists())

    # Verifica el comportamiento de comando crea respaldo cuando se cumple la frecuencia y sus condiciones relevantes.
    def test_comando_crea_respaldo_cuando_se_cumple_la_frecuencia(self):
        configuracion = ConfiguracionCopiasSeguridad.objects.create(
            pk=1,
            intervalo=1,
            unidad_intervalo='minutos',
            automaticas_activas=True,
            proxima_automatica=timezone.now() - timedelta(seconds=1),
        )

        call_command('revisar_copias_seguridad')

        copias = list(CopiaSeguridad.objects.order_by('alcance'))
        configuracion.refresh_from_db()
        self.assertEqual(len(copias), 2)
        self.assertEqual({copia.alcance for copia in copias}, {'informacion', 'proyecto'})
        self.assertTrue(all(copia.tipo == 'automatica' for copia in copias))
        self.assertIsNotNone(configuracion.ultima_automatica)
        self.assertGreater(configuracion.proxima_automatica, timezone.now())

    # Verifica el comportamiento de usuario sin permisos no puede ver el modulo y sus condiciones relevantes.
    def test_usuario_sin_permisos_no_puede_ver_el_modulo(self):
        usuario = User.objects.create_user(username='usuario-sin-copias', password='Clave-segura1!')
        self.client.force_login(usuario)

        respuesta = self.client.get(reverse('copias_seguridad'))

        self.assertEqual(respuesta.status_code, 302)


# Agrupa pruebas automatizadas relacionadas con report date filter pruebas.
class ReportDateFilterTests(TestCase):
    # Organiza el flujo de asignación up dentro de este módulo.
    def setUp(self):
        self.propietario = Propietario.objects.create(
            cedula=770700,
            nombre='Andrea',
            apellido='Mora',
            telefono='3001234700',
            correo='andrea.mora@gmail.com',
            rol='Propietario',
        )
        self.casa = Casa.objects.create(
            numero_casa=701,
            cantidad_personas=2,
            cantidad_residentes=1,
            estado='Ocupada',
            id_propietario=self.propietario,
        )

    # Verifica el comportamiento de pago incluye los dos extremos del rango y sus condiciones relevantes.
    def test_pago_incluye_los_dos_extremos_del_rango(self):
        Pago.objects.create(valor='10.00', fecha='2026-05-01', id_casa=self.casa)
        Pago.objects.create(valor='20.00', fecha='2026-05-31', id_casa=self.casa)
        Pago.objects.create(valor='30.00', fecha='2026-06-01', id_casa=self.casa)
        request = RequestFactory().get('/reportes/', {
            'desde': '2026-05-01',
            'hasta': '2026-05-31',
        })

        _, _, rows = build_report_rows(request, 'pagos')

        self.assertEqual([row[2] for row in rows], ['01/05/2026', '31/05/2026'])

    # Verifica el comportamiento de resumen suma pagos de varias casas en el mes y sus condiciones relevantes.
    def test_resumen_suma_pagos_de_varias_casas_en_el_mes(self):
        otra_casa = Casa.objects.create(
            numero_casa=703,
            cantidad_personas=2,
            cantidad_residentes=1,
            estado='Ocupada',
            id_propietario=Propietario.objects.create(
                cedula=770703,
                nombre='Luis',
                apellido='Gil',
                telefono='3001234703',
                correo='luis.gil@gmail.com',
                rol='Propietario',
            ),
        )
        Pago.objects.create(valor='100.00', fecha='2026-07-05', estado='Pagado', id_casa=self.casa)
        Pago.objects.create(valor='200.00', fecha='2026-07-20', estado='Pagado', id_casa=otra_casa)
        Pago.objects.create(valor='50.00', fecha='2026-07-25', estado='Pendiente', id_casa=self.casa)
        Pago.objects.create(valor='900.00', fecha='2026-06-30', estado='Pagado', id_casa=otra_casa)
        request = RequestFactory().get('/reportes/', {
            'reporte': 'pagos',
            'desde': '2026-07-01',
            'hasta': '2026-07-31',
        })

        summary = build_payment_summary(request)

        self.assertEqual(summary['cantidad'], 3)
        self.assertEqual(summary['total'], 350)
        self.assertEqual(summary['pagado'], 300)
        self.assertEqual(summary['pendiente'], 50)
        self.assertEqual(summary['saldo_actual'], 0)
        self.assertEqual(summary['fecha_resumen'], '31 de julio (07) de 2026')

    # Verifica el comportamiento de reporte y total excluyen pagos de casas sin propietario y sus condiciones relevantes.
    def test_reporte_y_total_excluyen_pagos_de_casas_sin_propietario(self):
        casa_sin_propietario = Casa.objects.create(
            numero_casa=704,
            cantidad_personas=2,
            cantidad_residentes=1,
            estado='Ocupada',
        )
        Pago.objects.create(valor='120.00', fecha='2026-07-10', estado='Pagado', id_casa=self.casa)
        Pago.objects.create(valor='900.00', fecha='2026-07-10', estado='Pagado', id_casa=casa_sin_propietario)
        request = RequestFactory().get('/reportes/', {'desde': '2026-07-01', 'hasta': '2026-07-31'})

        _, _, rows = build_report_rows(request, 'pagos')
        summary = build_payment_summary(request)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][1], 'Andrea Mora')
        self.assertEqual(summary['total'], 120)


    # Verifica el comportamiento de pantalla de reportes muestra totales del periodo y sus condiciones relevantes.
    def test_pantalla_de_reportes_muestra_totales_del_periodo(self):
        administrador = User.objects.create_user(username='admin-total-pagos', password='clave', is_staff=True)
        self.client.force_login(administrador)
        Pago.objects.create(valor='125000.00', fecha='2026-07-12', estado='Pagado', id_casa=self.casa)

        response = self.client.get(reverse('reportes'), {
            'reporte': 'pagos',
            'desde': '2026-07-01',
            'hasta': '2026-07-31',
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Resumen del mes seleccionado')
        self.assertContains(response, '$ 125.000')
        self.assertContains(response, '31 de julio (07) de 2026')
        self.assertContains(response, 'id="download-payments-excel"')
        self.assertNotRegex(response.content.decode(), r'id="download-payments-excel"[^>]*\shidden(?:\s|>)')

    # Verifica el comportamiento de PDF de pagos se genera con resumen del periodo y sus condiciones relevantes.
    def test_pdf_de_pagos_se_genera_con_resumen_del_periodo(self):
        administrador = User.objects.create_user(username='admin-pdf-pagos', password='clave', is_staff=True)
        self.client.force_login(administrador)
        Pago.objects.create(valor='125000.00', fecha='2026-07-12', estado='Pagado', id_casa=self.casa)

        response = self.client.get(reverse('reporte_pdf'), {
            'reporte': 'pagos',
            'desde': '2026-07-01',
            'hasta': '2026-07-31',
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertTrue(response.content.startswith(b'%PDF'))
        self.assertIn(b'/Subtype /Image', response.content)

    # Verifica que el PDF tabular incluya el logo y los metadatos del tipo de reporte.
    def test_pdf_de_reporte_general_incluye_logo_y_titulo_del_reporte(self):
        administrador = User.objects.create_user(username='admin-pdf-visitantes', password='clave', is_staff=True)
        self.client.force_login(administrador)

        response = self.client.get(reverse('reporte_pdf'), {'reporte': 'visitantes'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertTrue(response.content.startswith(b'%PDF'))
        self.assertIn(b'/Subtype /Image', response.content)
        self.assertIn(b'/Title', response.content)
        self.assertIn(b'Visitantes', response.content)
        self.assertIn(b'Piemonte', response.content)

    # Verifica el comportamiento de Excel de pagos exporta columnas y estado con los filtros y sus condiciones relevantes.
    def test_excel_de_pagos_exporta_columnas_y_estado_con_los_filtros(self):
        Pago.objects.create(valor='150000.00', fecha='2026-07-12', estado='Pagado', id_casa=self.casa)
        Pago.objects.create(valor='250000.00', fecha='2026-07-20', estado='Pendiente', id_casa=self.casa)
        administrador = User.objects.create_user(username='admin-excel-pagos', password='clave', is_staff=True)
        self.client.force_login(administrador)

        response = self.client.get(reverse('reporte_excel_pagos'), {
            'desde': '2026-07-01',
            'hasta': '2026-07-15',
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        worksheet = load_workbook(BytesIO(response.content), read_only=True, data_only=True).active
        rows = list(worksheet.values)
        self.assertEqual(rows[0], ('Casas', 'Fecha mes', 'Fecha día', 'Valor mensual', 'Pagado (Sí o No)'))
        self.assertEqual(rows[1], (701, 'Julio 2026', 12, 150000, 'Sí'))
        self.assertEqual(len(rows), 2)

    # Verifica el comportamiento de visitante muestra casa y fecha del evento filtrado y sus condiciones relevantes.
    def test_visitante_muestra_casa_y_fecha_del_evento_filtrado(self):
        otra_casa = Casa.objects.create(
            numero_casa=702,
            cantidad_personas=2,
            cantidad_residentes=1,
            estado='Ocupada',
        )
        guardia = Guardia.objects.create(cedula=770001, nombre='Luis', apellido='Diaz', turno='Día')
        visitante = Visitante.objects.create(
            nombre='Ana',
            apellido='Perez',
            cedula='770002',
            vehiculo_trae='NO',
        )
        Proceso.objects.create(
            tipo='Visitante',
            nombre='Ana Perez',
            fecha=timezone.make_aware(datetime(2026, 5, 10, 9, 0)),
            id_guardia=guardia,
            id_casa=self.casa,
            id_visitante=visitante,
        )
        Proceso.objects.create(
            tipo='Visitante',
            nombre='Ana Perez',
            fecha=timezone.make_aware(datetime(2026, 6, 10, 9, 0)),
            id_guardia=guardia,
            id_casa=otra_casa,
            id_visitante=visitante,
        )
        request = RequestFactory().get('/reportes/', {
            'desde': '2026-05-10',
            'hasta': '2026-05-10',
        })

        _, headers, rows = build_report_rows(request, 'visitantes')

        self.assertEqual(headers[:2], ['Fecha', 'Casa'])
        self.assertEqual(rows[0][:2], ['10/05/2026 09:00', 'Casa 701'])

    # Verifica el comportamiento de reporte de residentes se genera y sus condiciones relevantes.
    def test_reporte_de_residentes_se_genera(self):
        residente = Residente.objects.create(
            cedula=770003,
            nombre='Marta',
            apellido='Lopez',
            telefono='3001234567',
        )
        self.casa.id_residente = residente
        self.casa.save(update_fields=('id_residente',))

        _, headers, rows = build_report_rows(RequestFactory().get('/reportes/'), 'residentes')

        self.assertIn('Nombre', headers)
        self.assertEqual(rows[0][2], 'Marta')

    # Verifica el comportamiento de interfaz no aplica fecha a reportes sin fecha y sus condiciones relevantes.
    def test_interfaz_no_aplica_fecha_a_reportes_sin_fecha(self):
        administrador = User.objects.create_user(
            username='admin-filtros-reportes',
            password='clave',
            is_staff=True,
        )
        self.client.force_login(administrador)

        response = self.client.get(reverse('reportes'), {
            'reporte': 'casas',
            'desde': '2026-05-01',
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['filtro_desde'], '')
        self.assertContains(response, 'data-has-date="false"')
        self.assertContains(response, 'id="download-payments-excel" type="submit"')
        self.assertContains(response, 'hidden disabled')

    # Verifica el comportamiento de propietario no puede edición pago por url directa y sus condiciones relevantes.
    def test_propietario_no_puede_editar_pago_por_url_directa(self):
        usuario = User.objects.create_user(username='propietario-edicion-pago', password='clave')
        grupo, _ = Group.objects.get_or_create(name='Propietario')
        usuario.groups.add(grupo)
        propietario = Propietario.objects.create(
            cedula=889999,
            nombre='Marta',
            apellido='Rojas',
            telefono='3001234502',
            correo='marta.pagos@gmail.com',
            rol='Propietario',
            usuario=usuario,
        )
        self.casa.id_propietario = propietario
        self.casa.save(update_fields=('id_propietario',))
        pago = Pago.objects.create(valor='100.00', fecha='2026-09-23', id_casa=self.casa)
        self.client.force_login(usuario)

        respuesta = self.client.get(reverse('editar_pago', args=(pago.pk,)))

        self.assertEqual(respuesta.status_code, 403)

    # Verifica el comportamiento de administrador puede registro pago como pagado y sus condiciones relevantes.
    def test_administrador_puede_registrar_pago_como_pagado(self):
        administrador = User.objects.create_user(username='admin-registrar-pagado', password='clave', is_staff=True)
        self.client.force_login(administrador)
        with tempfile.TemporaryDirectory() as media_dir, override_settings(MEDIA_ROOT=media_dir):
            respuesta = self.client.post(reverse('registrar_pago'), {
                'id_casa': self.casa.pk,
                'valor': '100.00',
                'fecha': '2026-09-23',
                'estado': 'Pagado',
                'evidencia': SimpleUploadedFile('comprobante.pdf', b'%PDF comprobante', content_type='application/pdf'),
            })

        self.assertRedirects(respuesta, f"{reverse('registrar_pago')}?registros=1")
        self.assertEqual(Pago.objects.get(id_casa=self.casa).estado, 'Pagado')


class CrudDeleteSmokeTests(TestCase):
    def setUp(self):
        administrador = User.objects.create_user(
            username='crud-delete-admin',
            password='Admin-seguro1!',
            is_staff=True,
        )
        self.client.force_login(administrador)
        ConfiguracionCartera.objects.get_or_create(pk=1)

    def test_eliminar_resena(self):
        resena = Resena.objects.create(nombre='Prueba', comentario='Comentario', calificacion=5)

        respuesta = self.client.post(reverse('resenas'), {'action': 'delete', 'resena_id': resena.pk})

        self.assertEqual(respuesta.status_code, 302)
        self.assertFalse(Resena.objects.filter(pk=resena.pk).exists())

    def test_eliminar_residente_desde_su_modulo(self):
        residente = Residente.objects.create(cedula=880901, nombre='Ana', apellido='Prueba')

        respuesta = self.client.post(
            reverse('residentes'),
            {'action': 'delete', 'residente_id': residente.pk},
        )

        self.assertEqual(respuesta.status_code, 302)
        self.assertFalse(Residente.objects.filter(pk=residente.pk).exists())

    def test_eliminar_residente_desde_directorio_de_propietarios(self):
        residente = Residente.objects.create(cedula=880902, nombre='Luis', apellido='Prueba')

        respuesta = self.client.post(
            reverse('registrar_propietario'),
            {'action': 'delete_residente', 'residente_id': residente.pk},
        )

        self.assertEqual(respuesta.status_code, 302)
        self.assertFalse(Residente.objects.filter(pk=residente.pk).exists())

    def test_eliminar_domicilio(self):
        domicilio = Domicilio.objects.create(
            nombre='Carlos',
            apellido='Prueba',
            telefono_negocio='3001234567',
        )

        respuesta = self.client.post(
            reverse('registrar_domicilio'),
            {'action': 'delete', 'domicilio_id': domicilio.pk},
        )

        self.assertEqual(respuesta.status_code, 302)
        self.assertFalse(Domicilio.objects.filter(pk=domicilio.pk).exists())

    def test_eliminar_paquete(self):
        paquete = Paquete.objects.create(
            nombre='Maria',
            apellido='Prueba',
            transportadora='Prueba Express',
        )

        respuesta = self.client.post(
            reverse('registrar_paquete'),
            {'action': 'delete', 'paquete_id': paquete.pk},
        )

        self.assertEqual(respuesta.status_code, 302)
        self.assertFalse(Paquete.objects.filter(pk=paquete.pk).exists())

    def test_eliminar_novedad(self):
        novedad = Novedad.objects.create(titulo='Prueba', nota='Novedad de prueba')

        respuesta = self.client.post(
            reverse('registrar_novedad'),
            {'action': 'delete', 'nota_id': novedad.pk},
        )

        self.assertEqual(respuesta.status_code, 302)
        self.assertFalse(Novedad.objects.filter(pk=novedad.pk).exists())

    def test_eliminar_nota(self):
        nota = Notas.objects.create(nombre='Elena', apellido='Prueba', nota='Nota de prueba')

        respuesta = self.client.post(
            reverse('registrar_nota'),
            {'action': 'delete', 'nota_id': nota.pk},
        )

        self.assertEqual(respuesta.status_code, 302)
        self.assertFalse(Notas.objects.filter(pk=nota.pk).exists())
