# Módulo: Asocia las rutas HTTP del proyecto con las vistas correspondientes.
from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.urls import path
from django.contrib.auth import views as auth_views
from django.views.static import serve
from core import views
from core.views import dashboard_view
from BD import views as bd_views

urlpatterns = [

    # Consola administrativa, inicio público y autenticación de usuarios.
    path('admin/', admin.site.urls),
    path('', views.index),
    path('manual-usuario/', views.manual_usuario_view, name='manual_usuario'),
    path('manual-roles/', views.manual_roles_view, name='manual_roles'),
    path('login/', views.login, name='login'),
    path('password-reset/', views.PasswordResetEmailView.as_view(
        template_name='core/password_recovery/password_reset_form.html',
        email_template_name='core/password_recovery/password_reset_email.txt',
        html_email_template_name='core/password_recovery/password_reset_email.html',
        subject_template_name='core/password_recovery/password_reset_subject.txt',
        success_url='/password-reset/done/',
    ), name='password_reset'),
    path('password-reset/done/', auth_views.PasswordResetDoneView.as_view(
        template_name='core/password_recovery/password_reset_done.html',
    ), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        template_name='core/password_recovery/password_reset_confirm.html',
        success_url='/reset/done/',
    ), name='password_reset_confirm'),
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(
        template_name='core/password_recovery/password_reset_complete.html',
    ), name='password_reset_complete'),
    path('logout/', views.logout_view, name='logout'),
    path('perfil/', views.perfil_view, name='perfil'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('guardia/', views.dashboard_view_guardia, name='dashboard_guardia'),
    path('movimientos/', views.movimientos_view, name='movimientos'),
    # Reportes, saldos y parámetros de cartera.
    path('reportes/', bd_views.reportes_view, name='reportes'),
    path('reportes/pdf/', bd_views.reporte_pdf_view, name='reporte_pdf'),
    path('reportes/pagos/excel/', bd_views.reporte_excel_pagos_view, name='reporte_excel_pagos'),
    path('configuracion/cartera/', bd_views.configuracion_cartera_view, name='configuracion_cartera'),
    path('copias-seguridad/', bd_views.copias_seguridad_view, name='copias_seguridad'),
    path('copias-seguridad/carpetas/', bd_views.explorar_carpetas_copias_seguridad_view, name='explorar_carpetas_copias_seguridad'),
    path('copias-seguridad/restaurar-informacion/', bd_views.restaurar_copia_informacion_view, name='restaurar_copia_informacion'),
    path('copias-seguridad/subir-proyecto/', bd_views.subir_copia_proyecto_view, name='subir_copia_proyecto'),
    path('copias-seguridad/<int:copia_id>/descargar/', bd_views.descargar_copia_seguridad_view, name='descargar_copia_seguridad'),
    path('copias-seguridad/<int:copia_id>/eliminar/', bd_views.eliminar_copia_seguridad_view, name='eliminar_copia_seguridad'),
    path('cartera/saldos/', bd_views.actualizar_saldos_cartera_view, name='actualizar_saldos_cartera'),
    # Operaciones de gestión de residentes, casas, personal y cuentas.
    path('residentes/', bd_views.residentes_view, name='residentes'),
    path('residentes/<int:residente_id>/editar/', bd_views.residentes_view, name='editar_residente'),
    path('visitantes/registrar/', bd_views.visitante_ingreso_view, name='registrar_visitante'),
    path('casas/registrar/', bd_views.registrar_casa_view, name='registrar_casa'),
    path('casas/<int:casa_id>/editar/', bd_views.registrar_casa_view, name='editar_casa'),
    path('guardias/registrar/', bd_views.registrar_guardia_view, name='registrar_guardia'),
    path('guardias/<int:guardia_id>/editar/', bd_views.registrar_guardia_view, name='editar_guardia'),
    path('usuarios/', bd_views.usuarios_view, name='usuarios'),
    path(
        'usuarios/<int:usuario_id>/restablecer-contrasena/',
        bd_views.restablecer_contrasena_usuario_view,
        name='restablecer_contrasena_usuario',
    ),
    path('propietarios/registrar/', bd_views.registrar_propietario_view, name='registrar_propietario'),
    path('propietarios/<int:propietario_id>/editar/', bd_views.registrar_propietario_view, name='editar_propietario'),
    path('propietarios/residentes/<int:residente_id>/editar/', bd_views.registrar_propietario_view, name='editar_residente_directorio'),
    # Registros operativos de acceso, entregas, novedades y notas.
    path('visitantes/<int:visitante_id>/editar/', bd_views.visitante_ingreso_view, name='editar_visitante'),
    path('domicilios/registrar/', bd_views.domicilio_ingreso_view, name='registrar_domicilio'),
    path('domicilios/<int:domicilio_id>/editar/', bd_views.domicilio_ingreso_view, name='editar_domicilio'),
    path('domicilios/demorados/', bd_views.domicilios_demorados_view, name='domicilios_demorados'),
    path('paquetes/registrar/', bd_views.paquete_ingreso_view, name='registrar_paquete'),
    path('paquetes/<int:paquete_id>/editar/', bd_views.paquete_ingreso_view, name='editar_paquete'),
    path('novedades/registrar/', bd_views.novedad_view, name='registrar_novedad'),
    path('novedades/<int:nota_id>/editar/', bd_views.novedad_view, name='editar_novedad'),
    # Gestión de reseñas, notas y pagos, incluido el acceso al recibo individual.
    path('resenas/enviar/', bd_views.resena_submit, name='enviar_resena'),
    path('resenas/', bd_views.resenas_view, name='resenas'),
    path('notas/registrar/', bd_views.nota_view, name='registrar_nota'),
    path('notas/<int:nota_id>/editar/', bd_views.nota_view, name='editar_nota'),
    path('pagos/registrar/', bd_views.pago_view, name='registrar_pago'),
    path('pagos/<int:pago_id>/editar/', bd_views.pago_view, name='editar_pago'),
    path('pagos/<int:pago_id>/recibo/', bd_views.recibo_pago_view, name='recibo_pago'),
]

if settings.DEBUG:
    # Durante desarrollo, sirve multimedia directamente desde el directorio configurado.
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
elif settings.SERVE_MEDIA:
    # En despliegues que habilitan esta opción explícitamente, añade la ruta de lectura de archivos multimedia.
    urlpatterns.append(
        path(
            f"{settings.MEDIA_URL.lstrip('/')}<path:path>",
            serve,
            {'document_root': settings.MEDIA_ROOT},
        )
    )