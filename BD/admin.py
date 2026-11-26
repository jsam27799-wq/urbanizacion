# Módulo: Configura los modelos disponibles y sus opciones de administración en Django.
from django.contrib import admin
from .models import (
    Propietario,
    Residente,
    Casa,
    Guardia,
    Domicilio,
    Visitante,
    Paquete,
    Proceso,
    Pago,
    Notas,
    Novedad,
    Resena,
)


# Configura la consulta y presentación administrativa de propietario administración.
@admin.register(Propietario)
class PropietarioAdmin(admin.ModelAdmin):
    list_display = ('id_propietario', 'cedula', 'nombre', 'apellido', 'telefono', 'rol')
    search_fields = ('cedula', 'nombre', 'apellido')
    list_filter = ('rol',)


# Configura la consulta y presentación administrativa de residente administración.
@admin.register(Residente)
class ResidenteAdmin(admin.ModelAdmin):
    list_display = ('id_residente', 'cedula', 'nombre', 'apellido', 'telefono')
    search_fields = ('cedula', 'nombre', 'apellido')


# Configura la consulta y presentación administrativa de casa administración.
@admin.register(Casa)
class CasaAdmin(admin.ModelAdmin):
    list_display = ('id_casa', 'numero_casa', 'cantidad_personas', 'estado', 'id_residente', 'id_propietario')
    search_fields = ('numero_casa', 'estado')
    list_filter = ('estado',)


# Configura la consulta y presentación administrativa de guardia administración.
@admin.register(Guardia)
class GuardiaAdmin(admin.ModelAdmin):
    list_display = ('id_guardia', 'cedula', 'nombre', 'apellido', 'turno')
    search_fields = ('cedula', 'nombre', 'apellido')
    list_filter = ('turno',)


# Configura la consulta y presentación administrativa de domicilio administración.
@admin.register(Domicilio)
class DomicilioAdmin(admin.ModelAdmin):
    list_display = ('id_domicilio', 'nombre', 'apellido', 'telefono_negocio', 'vehiculo_tipo')
    search_fields = ('nombre', 'apellido', 'telefono_negocio')


# Configura la consulta y presentación administrativa de visitante administración.
@admin.register(Visitante)
class VisitanteAdmin(admin.ModelAdmin):
    list_display = ('id_visitante', 'cedula', 'nombre', 'apellido', 'vehiculo_trae')
    search_fields = ('cedula', 'nombre', 'apellido')
    list_filter = ('vehiculo_trae',)


# Configura la consulta y presentación administrativa de paquete administración.
@admin.register(Paquete)
class PaqueteAdmin(admin.ModelAdmin):
    list_display = ('id_paquete', 'nombre', 'apellido', 'transportadora', 'guia')
    search_fields = ('nombre', 'apellido', 'transportadora', 'guia')


# Configura la consulta y presentación administrativa de proceso administración.
@admin.register(Proceso)
class ProcesoAdmin(admin.ModelAdmin):
    list_display = ('id_proceso', 'tipo', 'cedula', 'nombre', 'fecha', 'id_guardia', 'id_casa')
    search_fields = ('tipo', 'cedula', 'nombre')
    list_filter = ('tipo', 'fecha')


# Configura la consulta y presentación administrativa de pago administración.
@admin.register(Pago)
class PagoAdmin(admin.ModelAdmin):
    list_display = ('id_pago', 'id_casa', 'valor', 'estado', 'fecha')
    search_fields = ('estado',)
    list_filter = ('estado', 'fecha')


# Configura la consulta y presentación administrativa de notas administración.
@admin.register(Notas)
class NotasAdmin(admin.ModelAdmin):
    list_display = ('id_nota', 'nombre', 'apellido', 'telefono', 'id_guardia')
    search_fields = ('nombre', 'apellido', 'telefono')


# Configura la consulta y presentación administrativa de novedad administración.
@admin.register(Novedad)
class NovedadAdmin(admin.ModelAdmin):
    list_display = ('id_novedad', 'titulo', 'tipo', 'fecha_creacion', 'fecha_suceso', 'registrado_por')
    search_fields = ('titulo', 'tipo', 'nota')
    list_filter = ('tipo', 'fecha_creacion', 'fecha_suceso')


# Configura la consulta y presentación administrativa de reseña administración.
@admin.register(Resena)
class ResenaAdmin(admin.ModelAdmin):
    list_display = ('id_resena', 'nombre', 'calificacion', 'aprobada', 'fecha_creacion')
    list_filter = ('aprobada', 'calificacion', 'fecha_creacion')
    search_fields = ('nombre', 'comentario')
