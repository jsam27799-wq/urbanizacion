# Módulo: Agrupa pruebas automatizadas de los comportamientos y reglas de la aplicación.
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from core.forms import PerfilForm
from core.models import PerfilUsuario
from BD.views import asignar_grupo_por_rol
from BD.models import Novedad, RegistroBitacora, Resena
from core.manual_content import MANUAL_MODULES


class ManualUsuarioViewTests(TestCase):
    def test_manual_usuario_muestra_capturas_reales_y_delimita_su_alcance(self):
        response = self.client.get(reverse('manual_usuario'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Manual de usuario')
        self.assertContains(response, 'data-manual-dialog')
        self.assertContains(response, '573332922849')
        self.assertContains(response, 'Bot de soporte')
        self.assertContains(response, 'Solo lo que ves en la página pública')
        self.assertContains(response, 'data-manual-capture="pagina-portada"')
        self.assertContains(response, 'data-manual-capture="dialogo-acceso"')
        self.assertContains(response, 'No explica la pantalla de acceso ni las páginas que aparecen después de ingresar.')
        self.assertNotContains(response, 'Captura pendiente')
        for screenshot in (
            '01-portada',
            '02-menu-y-acceso',
            '03-servicios',
            '04-espacios',
            '05-novedades',
            '06-resenas',
            '07-contacto-y-ubicacion',
            '08-ayuda-rapida',
        ):
            self.assertContains(response, f'core/images/manual/{screenshot}.')

    def test_pagina_principal_muestra_el_acceso_flotante(self):
        response = self.client.get('/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Iniciar sesión')
        self.assertContains(response, 'data-manual-open')
        self.assertContains(response, 'data-floating-help')
        self.assertContains(response, 'floating-help__shortcut')
        self.assertContains(response, 'aria-expanded="false"')

    def test_usuario_autenticado_ve_bienvenida_perfil_y_cerrar_sesion(self):
        user = get_user_model().objects.create_user(
            username='ana-mora',
            password='clave',
            first_name='Ana',
            last_name='Mora',
            email='ana.mora@gmail.com',
        )
        PerfilUsuario.objects.create(usuario=user, telefono='3236669030')
        self.client.force_login(user)

        response = self.client.get('/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '¡Bienvenido, Ana Mora!')
        self.assertContains(response, 'data-open-profile')
        self.assertContains(response, 'data-profile-dialog')
        self.assertContains(response, 'ana.mora@gmail.com')
        self.assertContains(response, '+57 323-6669030')
        self.assertContains(response, reverse('perfil'))
        self.assertContains(response, 'Volver al dashboard')
        self.assertContains(response, reverse('dashboard'))
        self.assertContains(response, reverse('logout'))
        self.assertNotContains(response, 'href="/login/" class="login-menu-link"')

        perfil_response = self.client.get(reverse('perfil'))
        self.assertEqual(perfil_response.status_code, 200)
        self.assertContains(perfil_response, 'name="codigo_pais"')
        self.assertContains(perfil_response, 'CO (+57)')


class ManualRolesViewTests(TestCase):
    def test_administrador_consulta_todos_los_modulos_del_manual(self):
        admin = get_user_model().objects.create_user(
            username='admin-manuales',
            password='clave-segura',
            is_staff=True,
        )
        self.client.force_login(admin)

        response = self.client.get(reverse('manual_roles'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<h2>Manual de administrador</h2>')
        for module, screenshot in (
            ('perfil', '04-menu-sesion.png'),
            ('dashboard', '07-dashboard-admin.png'),
            ('usuarios', '10-crear-cuenta.png'),
            ('personas', '12-propietario-residente.png'),
            ('casas', '15-casa-formulario.png'),
            ('visitantes', '18-visitante-formulario.png'),
            ('domiciliarios', '22-domiciliario-formulario.png'),
            ('paquetes', '24-paquete-formulario.png'),
            ('notas', '32-nota-formulario.png'),
            ('pagos', '27-pago-formulario.png'),
            ('novedades', '31-novedad-formulario.png'),
            ('resenas', '33-resena-publica.png'),
            ('reportes', '36-reportes-filtros.png'),
            ('historial', '38-historial.png'),
            ('copias', '39-copias-seguridad.png'),
            ('configuracion', '29-configuracion-cartera.png'),
        ):
            self.assertContains(response, f'data-manual-module="{module}"')
            screenshot_name = screenshot.rsplit('.', 1)[0]
            self.assertContains(response, f'core/images/manual-operativo/{screenshot_name}.')

        home_response = self.client.get('/')
        self.assertContains(home_response, reverse('manual_roles'))
        self.assertContains(home_response, 'Manual de administrador')
        self.assertNotContains(home_response, 'Manual técnico')
        self.assertNotContains(home_response, 'data-manual-open')
        self.assertEqual(self.client.get('/manual-tecnico/').status_code, 404)

    def test_guardia_y_propietario_solo_consultan_su_guia(self):
        for role, expected_role, visible_modules, hidden_modules in (
            ('Guardia', 'guardia', {'perfil', 'dashboard', 'visitantes', 'domiciliarios', 'paquetes', 'notas'}, {'usuarios', 'casas', 'pagos', 'reportes', 'copias'}),
            ('Propietario', 'propietario', {'perfil', 'pagos', 'comunidad'}, {'usuarios', 'visitantes', 'domiciliarios', 'paquetes', 'reportes', 'copias'}),
        ):
            with self.subTest(role=role):
                user = get_user_model().objects.create_user(username=f'manual-{expected_role}')
                asignar_grupo_por_rol(user, expected_role)
                self.client.force_login(user)

                response = self.client.get(reverse('manual_roles'))

                self.assertEqual(response.status_code, 200)
                expected_title = f'Manual de {expected_role}'
                self.assertContains(response, f'<h2>{expected_title}</h2>')
                self.assertContains(response, '<small>Finaliza la sesión actual.</small>')
                for module in visible_modules:
                    self.assertContains(response, f'data-manual-module="{module}"')
                for module in hidden_modules:
                    self.assertNotContains(response, f'data-manual-module="{module}"')
                if expected_role == 'guardia':
                    self.assertContains(response, 'core/images/manual-operativo/08-dashboard-guardia.')
                    for screenshot in (
                        '04-menu-sesion',
                        '05-perfil',
                        '06-perfil-confirmacion',
                        '07-dashboard-admin',
                        '09-movimientos-recientes',
                    ):
                        self.assertNotContains(
                            response,
                            f'core/images/manual-operativo/{screenshot}.',
                        )
                elif expected_role == 'propietario':
                    self.assertContains(response, 'core/images/manual-operativo/04-menu-cuenta-propietario.')
                    for screenshot in (
                        '04-menu-sesion',
                        '05-perfil',
                        '06-perfil-confirmacion',
                        '07-dashboard-admin',
                    ):
                        self.assertNotContains(
                            response,
                            f'core/images/manual-operativo/{screenshot}.',
                        )

                home_response = self.client.get('/')
                self.assertContains(home_response, reverse('manual_roles'))
                self.assertContains(home_response, expected_title)
                self.assertNotContains(home_response, 'Manual técnico')
                self.assertEqual(self.client.get('/manual-tecnico/').status_code, 404)

    def test_todas_las_capturas_de_los_manuales_existen_en_static(self):
        for modules in MANUAL_MODULES.values():
            for module in modules:
                for figure in module['figures']:
                    asset_path = Path(__file__).parent / 'static' / figure['src']
                    with self.subTest(image=figure['src']):
                        self.assertTrue(asset_path.is_file(), f'No existe la captura {asset_path}')

    def test_manuales_internos_requieren_una_sesion(self):
        response = self.client.get(reverse('manual_roles'))

        self.assertRedirects(
            response,
            f'{reverse("login")}?next={reverse("manual_roles")}',
        )


# Agrupa pruebas automatizadas relacionadas con inicio de sesión vista pruebas.
class LoginViewTests(TestCase):
    def test_login_muestra_opcion_de_recuperacion_y_rutas_de_reset_existen(self):
        response = self.client.get(reverse('login'))

        self.assertContains(response, '¿Olvidaste tu contraseña?')
        self.assertContains(response, reverse('password_reset'))
        recovery_response = self.client.get(reverse('password_reset'))
        self.assertEqual(recovery_response.status_code, 200)
        self.assertContains(recovery_response, 'recovery-card')
        self.assertContains(recovery_response, 'Enviar instrucciones')

        done_response = self.client.get(reverse('password_reset_done'))
        self.assertContains(done_response, 'Solicitud recibida')

    def test_password_reset_email_includes_html_design_and_secure_link(self):
        user = get_user_model().objects.create_user(
            username='usuario-recuperacion',
            email='usuario@outlook.com',
            password='Clave-segura1!',
            first_name='Ana',
        )

        with self.settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend'):
            response = self.client.post(reverse('password_reset'), {'email': user.email})

        self.assertRedirects(response, reverse('password_reset_done'))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [user.email])
        self.assertEqual(len(mail.outbox[0].alternatives), 1)
        html_message = mail.outbox[0].alternatives[0][0]
        self.assertIn('Crear nueva contraseña', html_message)
        self.assertIn('/reset/', html_message)

        reset_url = reverse('password_reset_confirm', kwargs={
            'uidb64': urlsafe_base64_encode(force_bytes(user.pk)),
            'token': default_token_generator.make_token(user),
        })
        reset_response = self.client.get(reset_url, follow=True)
        self.assertEqual(reset_response.status_code, 200)
        self.assertContains(reset_response, 'Crea una nueva contraseña')
        response_after_save = self.client.post(
            reset_response.request['PATH_INFO'],
            {
                'new_password1': 'Otra-clave-segura-2026!',
                'new_password2': 'Otra-clave-segura-2026!',
            },
            follow=True,
        )
        self.assertEqual(response_after_save.status_code, 200)
        self.assertContains(response_after_save, 'Contraseña actualizada')
        user.refresh_from_db()
        self.assertTrue(user.check_password('Otra-clave-segura-2026!'))

    def test_password_reset_no_usa_terminal_si_falta_configurar_smtp(self):
        user = get_user_model().objects.create_user(
            username='usuario-smtp-no-configurado',
            email='usuario@example.com',
            password='Clave-segura1!',
        )

        with self.settings(
            EMAIL_BACKEND='django.core.mail.backends.smtp.EmailBackend',
            EMAIL_HOST_USER='',
            EMAIL_HOST_PASSWORD='',
        ):
            response = self.client.post(
                reverse('password_reset'),
                {'email': user.email},
            )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'El envío de correo no está configurado')

    def test_password_reset_muestra_error_si_smtp_no_puede_enviar(self):
        user = get_user_model().objects.create_user(
            username='usuario-smtp-error',
            email='usuario@example.com',
            password='Clave-segura1!',
        )

        with self.settings(
            EMAIL_BACKEND='django.core.mail.backends.smtp.EmailBackend',
            EMAIL_HOST_USER='remitente@example.com',
            EMAIL_HOST_PASSWORD='credencial-de-prueba',
        ):
            with patch(
                'django.contrib.auth.forms.PasswordResetForm.send_mail',
                side_effect=OSError('SMTP unavailable'),
            ):
                response = self.client.post(
                    reverse('password_reset'),
                    {'email': user.email},
                )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'No se pudo enviar el correo')

    def test_correo_no_registrado_recibe_respuesta_neutral_y_no_envia_mensaje(self):
        with self.settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend'):
            response = self.client.post(
                reverse('password_reset'),
                {'email': 'no-registrado@outlook.com'},
            )

        self.assertRedirects(response, reverse('password_reset_done'))
        self.assertEqual(len(mail.outbox), 0)
        self.assertContains(
            self.client.get(reverse('password_reset_done')),
            'Si existe una cuenta asociada a ese correo',
        )

    # Verifica el comportamiento de inicio de sesión with valid credentials redirects to panel y sus condiciones relevantes.
    def test_login_with_valid_credentials_redirects_to_dashboard(self):
        user = get_user_model().objects.create_user(username='admin', password='admin123', is_staff=True)

        response = self.client.post(reverse('login'), {
            'username': 'admin',
            'password': 'admin123',
        }, follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.wsgi_request.user.is_authenticated)
        self.assertRedirects(response, reverse('dashboard'))

    # Verifica el comportamiento de inicio de sesión with invalid credentials shows error y sus condiciones relevantes.
    def test_login_with_invalid_credentials_shows_error(self):
        response = self.client.post(reverse('login'), {
            'username': 'admin',
            'password': 'wrongpassword',
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Usuario o contraseña incorrectos')
        self.assertContains(response, 'class="login-message"')

    def test_ajax_login_with_invalid_credentials_returns_error_without_redirect(self):
        response = self.client.post(
            reverse('login'),
            {'username': 'admin', 'password': 'wrongpassword'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {
            'success': False,
            'message': 'Usuario o contraseña incorrectos',
        })
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_ajax_login_with_valid_credentials_returns_dashboard_url(self):
        get_user_model().objects.create_user(username='admin-ajax', password='admin123', is_staff=True)

        response = self.client.post(
            reverse('login'),
            {'username': 'admin-ajax', 'password': 'admin123'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            'success': True,
            'redirect_url': reverse('dashboard'),
        })
        self.assertIn('_auth_user_id', self.client.session)

    # Verifica el comportamiento de inicio de sesión with inactive account is rejected y sus condiciones relevantes.
    def test_login_with_inactive_account_is_rejected(self):
        get_user_model().objects.create_user(
            username='guardia-inactivo',
            password='admin123',
            is_active=False,
        )

        response = self.client.post(reverse('login'), {
            'username': 'guardia-inactivo',
            'password': 'admin123',
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Usuario o contraseña incorrectos')

    # Verifica el comportamiento de cierre de sesión redirects to inicio de sesión y sus condiciones relevantes.
    def test_logout_redirects_to_login(self):
        user = get_user_model().objects.create_user(username='admin', password='admin123', is_staff=True)
        self.client.login(username='admin', password='admin123')

        response = self.client.get(reverse('logout'))

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('login'))
        self.assertFalse(response.wsgi_request.user.is_authenticated)


    # Verifica el comportamiento de perfil actualiza datos sin cambiar usuario y sus condiciones relevantes.
    def test_perfil_actualiza_datos_sin_cambiar_usuario(self):
        user = get_user_model().objects.create_user(
            username='usuario-fijo',
            password='Clave-vieja1!',
            first_name='Ana',
            last_name='Rojas',
        )
        self.client.force_login(user)

        response = self.client.post(reverse('perfil'), {
            'accion': 'perfil',
            'first_name': 'Laura',
            'last_name': 'Mora',
            'email': 'laura.mora@outlook.com',
            'codigo_pais': 'CO',
            'telefono': '3001234567',
        })

        self.assertRedirects(response, reverse('perfil'))
        user.refresh_from_db()
        self.assertEqual(user.username, 'usuario-fijo')
        self.assertEqual(user.first_name, 'Laura')
        self.assertEqual(user.last_name, 'Mora')
        self.assertEqual(user.email, 'laura.mora@outlook.com')
        self.assertEqual(user.perfil_contacto.telefono, '+573001234567')

    def test_perfil_muestra_confirmacion_en_modal(self):
        user = get_user_model().objects.create_user(
            username='perfil-modal',
            password='Clave-segura1!',
            first_name='Ana',
            last_name='Rojas',
            email='ana.rojas@gmail.com',
        )
        self.client.force_login(user)

        response = self.client.post(reverse('perfil'), {
            'accion': 'perfil',
            'first_name': 'Ana',
            'last_name': 'Rojas',
            'email': 'ana.rojas@gmail.com',
            'codigo_pais': 'CO',
            'telefono': '3001234567',
        }, follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="siteNotificationModal"')
        self.assertContains(response, 'Datos personales actualizados correctamente.')
        self.assertNotContains(response, 'class="alert alert-success"')

    def test_perfil_rechaza_telefono_con_digitos_no_ascii(self):
        user = get_user_model().objects.create_user(username='telefono-invalido')
        form = PerfilForm(data={
            'first_name': 'Ana',
            'last_name': 'Perez',
            'email': 'ana@gmail.com',
            'codigo_pais': 'CO',
            'telefono': '１２３４５６７８',
        }, instance=user)

        self.assertFalse(form.is_valid())
        self.assertIn('telefono', form.errors)

    def test_perfil_valida_y_normaliza_telefono_segun_pais(self):
        user = get_user_model().objects.create_user(username='telefono-internacional')
        datos_base = {
            'first_name': 'Ana',
            'last_name': 'Perez',
            'email': 'ana@gmail.com',
        }

        for region, telefono, esperado in (
            ('CO', '300 123 4567', '+573001234567'),
            ('US', '650 253 0000', '+16502530000'),
        ):
            with self.subTest(region=region):
                form = PerfilForm(
                    data={**datos_base, 'codigo_pais': region, 'telefono': telefono},
                    instance=user,
                )
                self.assertTrue(form.is_valid(), form.errors)
                self.assertEqual(form.cleaned_data['telefono'], esperado)

    def test_perfil_rechaza_numero_que_no_corresponde_al_pais(self):
        user = get_user_model().objects.create_user(username='telefono-pais-invalido')
        form = PerfilForm(data={
            'first_name': 'Ana',
            'last_name': 'Perez',
            'email': 'ana@gmail.com',
            'codigo_pais': 'US',
            'telefono': '3001234567',
        }, instance=user)

        self.assertFalse(form.is_valid())
        self.assertIn('telefono', form.errors)

    def test_perfil_carga_telefono_guardado_en_formato_internacional(self):
        user = get_user_model().objects.create_user(username='telefono-guardado')
        perfil = PerfilUsuario.objects.create(usuario=user, telefono='+573001234567')

        form = PerfilForm(instance=user, perfil=perfil)

        self.assertEqual(form.initial['codigo_pais'], 'CO')
        self.assertEqual(form.initial['telefono'], '300-1234567')

    # Verifica el comportamiento de perfil cambia contrasena y conserva la sesion y sus condiciones relevantes.
    def test_perfil_cambia_contrasena_y_conserva_la_sesion(self):
        user = get_user_model().objects.create_user(username='usuario-clave', password='Clave-vieja1!')
        self.client.force_login(user)

        response = self.client.post(reverse('perfil'), {
            'accion': 'password',
            'old_password': 'Clave-vieja1!',
            'new_password1': 'Clave-nueva1!',
            'new_password2': 'Clave-nueva1!',
        })

        self.assertRedirects(response, reverse('perfil'))
        self.assertTrue(self.client.session.get('_auth_user_id'))
        self.assertTrue(self.client.login(username='usuario-clave', password='Clave-nueva1!'))


# Agrupa pruebas automatizadas relacionadas con reseña access pruebas.
class ResenaAccessTests(TestCase):
    def test_novedades_del_inicio_priorizan_fechas_proximas_y_dejan_vencidas_al_final(self):
        ahora = timezone.now()
        novedades = [
            ('Más lejana próxima', ahora + timedelta(days=5)),
            ('Más cercana vencida', ahora - timedelta(days=1)),
            ('Más cercana próxima', ahora + timedelta(days=1)),
            ('Más lejana vencida', ahora - timedelta(days=5)),
            (
                'Fecha de hoy',
                timezone.localtime(ahora).replace(hour=0, minute=0, second=0, microsecond=0),
            ),
        ]
        for titulo, fecha_suceso in novedades:
            Novedad.objects.create(
                titulo=titulo,
                tipo='General',
                nota='Aviso de prueba.',
                fecha_suceso=fecha_suceso,
            )

        response = self.client.get('/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [novedad.titulo for novedad in response.context['novedades']],
            [
                'Fecha de hoy',
                'Más cercana próxima',
                'Más lejana próxima',
                'Más cercana vencida',
                'Más lejana vencida',
            ],
        )

    def test_enlace_de_navegacion_resenas_apunta_a_la_seccion_del_home(self):
        response = self.client.get('/')

        self.assertContains(response, 'href="#testimonials"')
        self.assertContains(response, 'id="testimonials"')

    # Verifica el comportamiento de formulario no se muestra a visitantes y sus condiciones relevantes.
    def test_formulario_no_se_muestra_a_visitantes(self):
        response = self.client.get('/')

        self.assertNotContains(response, 'action="/resenas/enviar/"')

    # Verifica el comportamiento de formulario se muestra a residentes y sus condiciones relevantes.
    def test_formulario_se_muestra_a_residentes(self):
        user = get_user_model().objects.create_user(username='residente', password='clave')
        user.groups.add(Group.objects.create(name='Residente'))
        self.client.force_login(user)

        response = self.client.get('/')

        self.assertContains(response, 'Comparte tu experiencia')

    # Verifica el comportamiento de envio directo se rechaza para visitantes y sus condiciones relevantes.
    def test_envio_directo_se_rechaza_para_visitantes(self):
        response = self.client.post(reverse('enviar_resena'), {
            'nombre': 'Visitante',
            'calificacion': 5,
            'comentario': 'Buena experiencia.',
        })

        self.assertRedirects(response, '/#testimonials')
        self.assertFalse(Resena.objects.exists())

    # Verifica el comportamiento de reseña guarda automaticamente el rol del usuario y sus condiciones relevantes.
    def test_resena_guarda_automaticamente_el_rol_del_usuario(self):
        for rol in ('Administrador', 'Guardia', 'Propietario', 'Residente'):
            with self.subTest(rol=rol):
                user = get_user_model().objects.create_user(username=rol.lower(), password='clave')
                user.groups.add(Group.objects.get_or_create(name=rol)[0])
                self.client.force_login(user)

                response = self.client.post(reverse('enviar_resena'), {
                    'nombre': 'Usuario de prueba',
                    'calificacion': 5,
                    'comentario': 'Buena experiencia.',
                })

                self.assertRedirects(response, '/#testimonials')
                resena = Resena.objects.get(usuario=user)
                self.assertEqual(resena.rol_usuario, rol)


# Agrupa pruebas automatizadas relacionadas con panel bitácora pruebas.
class DashboardBitacoraTests(TestCase):
    def test_dashboard_profile_button_remains_visible_and_links_to_profile(self):
        user = get_user_model().objects.create_user(
            username='jose-dashboard',
            password='clave-segura',
            is_staff=True,
        )
        self.client.force_login(user)

        response = self.client.get(reverse('dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'dashboard-page-heading')
        self.assertContains(response, 'dashboard-profile-toggle')
        self.assertContains(response, f'Bienvenido {user}')
        self.assertContains(response, reverse('perfil'))
        self.assertContains(response, 'dashboard-profile-menu')
    # Verifica el comportamiento de panel y historial muestran registros de todos los modulos y sus condiciones relevantes.
    def test_dashboard_y_historial_muestran_registros_de_todos_los_modulos(self):
        user = get_user_model().objects.create_user(
            username='admin-bitacora',
            password='clave',
            is_staff=True,
            first_name='Ana',
            last_name='Mora',
        )
        RegistroBitacora.objects.create(
            modulo='Casa',
            accion='Registro',
            registro='Casa 503',
            descripcion='Casa registrada con estado Activa.',
            usuario=user,
        )
        RegistroBitacora.objects.create(
            modulo='Propietario',
            registro='Carlos Perez',
            descripcion='Propietario registrado.',
            usuario=user,
        )
        Novedad.objects.create(
            titulo='Corte zona común',
            tipo='Corte de luz',
            nota='Mantenimiento programado.',
            registrado_por=user,
        )
        Resena.objects.create(
            nombre='Laura',
            comentario='Todo muy bien.',
            calificacion=5,
            usuario=user,
        )
        self.client.force_login(user)

        dashboard = self.client.get(reverse('dashboard'))
        self.assertEqual(dashboard.status_code, 200)
        self.assertContains(dashboard, 'Últimos movimientos')
        self.assertNotContains(dashboard, '<th>Acción</th>', html=True)
        self.assertContains(dashboard, 'Casa 503')
        self.assertContains(dashboard, 'Registro')
        self.assertContains(dashboard, 'Carlos Perez')
        self.assertContains(dashboard, 'Corte zona común')
        self.assertContains(dashboard, 'Laura')
        self.assertContains(dashboard, 'Todos los módulos')

        historial = self.client.get(reverse('movimientos'))
        self.assertEqual(historial.status_code, 200)
        self.assertNotContains(historial, '<th>Acción</th>', html=True)
        self.assertContains(historial, 'Casa 503')
        self.assertContains(historial, 'Carlos Perez')
        self.assertContains(historial, 'Corte zona común')
        self.assertContains(historial, 'Laura')

    # Verifica el comportamiento de filtro de modulo en panel filtra la bitácora y sus condiciones relevantes.
    def test_filtro_de_modulo_en_dashboard_filtra_la_bitacora(self):
        user = get_user_model().objects.create_user(
            username='admin-filtro-bitacora',
            password='clave',
            is_staff=True,
        )
        RegistroBitacora.objects.create(modulo='Casa', registro='Casa 504')
        RegistroBitacora.objects.create(modulo='Propietario', registro='Maria Rojas')
        self.client.force_login(user)

        response = self.client.get(reverse('dashboard'), {'tipo': 'Casa'})

        self.assertContains(response, 'Casa 504')
        self.assertNotContains(response, 'Maria Rojas')
