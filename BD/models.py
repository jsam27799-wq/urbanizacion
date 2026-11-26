# Módulo: Define las entidades de persistencia y sus relaciones en la base de datos.
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.utils import timezone

MAX_CEDULA = 9_999_999_999


def validar_cedula_maxima_texto(value):
    valor = str(value)
    if valor.isascii() and valor.isdigit() and int(valor) > MAX_CEDULA:
        raise ValidationError(
            'Asegúrese de que este valor es menor o igual a %(limit_value)s.',
            code='max_value',
            params={'limit_value': MAX_CEDULA},
        )


# Representa propietario y define sus datos y relaciones persistentes.
class Propietario(models.Model):
    id_propietario = models.AutoField(primary_key=True, db_column='Id_propietario')
    cedula = models.BigIntegerField(
        db_column='Cedula',
        validators=[MaxValueValidator(MAX_CEDULA)],
    )
    nombre = models.CharField(max_length=100, db_column='Nombre')
    apellido = models.CharField(max_length=100, db_column='Apellido')
    telefono = models.CharField(max_length=20, db_column='Telefono')
    correo = models.EmailField(max_length=100, db_column='Correo')
    rol = models.CharField(max_length=15, db_column='Rol')
    casas_historicas = models.JSONField(default=list, blank=True, db_column='Casas_Historicas')
    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='propietario',
    )

    # Agrupa las opciones de configuración del modelo o formulario que contiene.
    class Meta:
        db_table = 'propietario'
        verbose_name = 'Propietario'
        verbose_name_plural = 'Propietarios'

    # Construye la representación textual legible del objeto.
    def __str__(self):
        return f"{self.nombre} {self.apellido} - C.I. {self.cedula}"


# Representa residente y define sus datos y relaciones persistentes.
class Residente(models.Model):
    id_residente = models.AutoField(primary_key=True, db_column='Id_residente')
    cedula = models.BigIntegerField(
        db_column='Cedula',
        validators=[MaxValueValidator(MAX_CEDULA)],
    )
    nombre = models.CharField(max_length=100, db_column='Nombre')
    apellido = models.CharField(max_length=100, db_column='Apellido')
    telefono = models.CharField(max_length=20, blank=True, null=True, db_column='Telefono')
    correo = models.EmailField(max_length=100, blank=True, null=True, db_column='Correo')

    # Agrupa las opciones de configuración del modelo o formulario que contiene.
    class Meta:
        db_table = 'residente'
        verbose_name = 'Residente'
        verbose_name_plural = 'Residentes'

    # Construye la representación textual legible del objeto.
    def __str__(self):
        return f"{self.nombre} {self.apellido}"


# Representa casa y define sus datos y relaciones persistentes.
class Casa(models.Model):
    id_casa = models.AutoField(primary_key=True, db_column='Id_casa')
    numero_casa = models.IntegerField(db_column='Numero_casa')
    cantidad_personas = models.IntegerField(db_column='Cantidad_personas')
    cantidad_residentes = models.IntegerField(default=1, db_column='Cantidad_residentes')
    estado = models.CharField(max_length=50, db_column='Estado')
    cartera = models.DecimalField(max_digits=16, decimal_places=2, default=0, db_column='Cartera')
    saldo_mora = models.DecimalField(max_digits=16, decimal_places=2, default=0, db_column='Saldo_Mora')
    saldo_favor = models.DecimalField(max_digits=16, decimal_places=2, default=0, db_column='Saldo_Favor')
    ultima_mora_aplicada = models.DateField(default=timezone.localdate, db_column='Ultima_Mora_Aplicada')
    ultima_mora_calculada = models.DateTimeField(default=timezone.now, db_column='Ultima_Mora_Calculada')

    # Relaciones
    id_residente = models.ForeignKey(
        Residente,
        on_delete=models.SET_NULL,
        db_column='Id_residente',
        related_name='casas',
        null=True,
        blank=True,
    )
    id_propietario = models.ForeignKey(
        Propietario,
        on_delete=models.SET_NULL,
        db_column='Id_propietario',
        related_name='casas',
        null=True,
        blank=True,
    )
    # El residente principal se conserva aparte; esta relación intermedia permite asociar residentes secundarios.
    residentes_secundarios = models.ManyToManyField(
        Residente,
        through='CasaResidente',
        related_name='casas_secundarias',
        blank=True,
    )

    # Agrupa las opciones de configuración del modelo o formulario que contiene.
    class Meta:
        db_table = 'casa'
        verbose_name = 'Casa'
        verbose_name_plural = 'Casas'
        constraints = [
            models.UniqueConstraint(fields=['numero_casa'], name='unique_numero_casa'),
        ]

    # Construye la representación textual legible del objeto.
    def __str__(self):
        return f"Casa N° {self.numero_casa}"


# Representa configuración cartera y define sus datos y relaciones persistentes.
class ConfiguracionCartera(models.Model):
    FRECUENCIAS_MORA = (
        ('mensual', 'Una vez al mes después del vencimiento'),
        ('minuto', 'Modo de prueba: cada minuto'),
    )
    porcentaje_mora = models.DecimalField(max_digits=5, decimal_places=2, default=2)
    monto_aumento_mensual = models.DecimalField(max_digits=16, decimal_places=2, default=0, db_column='Monto_Aumento_Mensual')
    dia_vencimiento = models.PositiveSmallIntegerField(default=30)
    frecuencia_mora = models.CharField(max_length=10, choices=FRECUENCIAS_MORA, default='mensual')
    tiempo_domiciliario_minutos = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    estados_visualizacion = models.JSONField(default=dict, blank=True)

    # Agrupa las opciones de configuración del modelo o formulario que contiene.
    class Meta:
        db_table = 'configuracion_cartera'
        verbose_name = 'Configuración de cartera'
        verbose_name_plural = 'Configuración de cartera'


# Representa casa residente y define sus datos y relaciones persistentes.
class CasaResidente(models.Model):
    ROLES = (
        ('SECUNDARIO', 'Secundario'),
    )
    casa = models.ForeignKey(Casa, on_delete=models.CASCADE, related_name='residentes_asociados')
    residente = models.ForeignKey(Residente, on_delete=models.CASCADE, related_name='asignaciones_secundarias')
    rol = models.CharField(max_length=20, choices=ROLES, default='SECUNDARIO')

    # Agrupa las opciones de configuración del modelo o formulario que contiene.
    class Meta:
        db_table = 'casa_residente'
        constraints = [
            models.UniqueConstraint(fields=('casa', 'residente'), name='unique_casa_residente'),
        ]


# Representa guardia y define sus datos y relaciones persistentes.
class Guardia(models.Model):
    id_guardia = models.AutoField(primary_key=True, db_column='Id_guardia')
    cedula = models.BigIntegerField(
        db_column='Cedula',
        validators=[MaxValueValidator(MAX_CEDULA)],
    )
    nombre = models.CharField(max_length=100, db_column='Nombre')
    apellido = models.CharField(max_length=100, db_column='Apellido')
    telefono = models.CharField(max_length=20, blank=True, null=True, db_column='Telefono')
    turno = models.CharField(max_length=20, blank=True, null=True, db_column='Turno')
    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='guardia',
    )

    # Agrupa las opciones de configuración del modelo o formulario que contiene.
    class Meta:
        db_table = 'guardia'
        verbose_name = 'Guardia'
        verbose_name_plural = 'Guardias'

    # Construye la representación textual legible del objeto.
    def __str__(self):
        return f"{self.nombre} {self.apellido} ({self.turno})"


# Representa domicilio y define sus datos y relaciones persistentes.
class Domicilio(models.Model):
    id_domicilio = models.AutoField(primary_key=True, db_column='Id_domicilio')
    nombre = models.CharField(max_length=100, db_column='Nombre')
    apellido = models.CharField(max_length=100, db_column='Apellido')
    telefono_negocio = models.CharField(max_length=20, db_column='Telefono_Negocio')
    descripcion_negocio = models.CharField(max_length=200, blank=True, null=True, db_column='Descripcion_Negocio')
    vehiculo_tipo = models.CharField(max_length=50, blank=True, null=True, db_column='Vehiculo_Tipo')
    vehiculo_placa = models.CharField(max_length=20, blank=True, null=True, db_column='Vehiculo_Placa')
    residente_secundario = models.ForeignKey(
        Residente,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='domicilios_autorizados',
        db_column='Id_residente_secundario',
    )
    propietario_autorizador = models.ForeignKey(
        Propietario,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='domicilios_autorizados',
        db_column='Id_propietario_autorizador',
    )
    autoriza = models.CharField(
        max_length=2,
        choices=(('SI', 'Sí'), ('NO', 'No')),
        default='NO',
        db_column='Autoriza',
    )

    # Agrupa las opciones de configuración del modelo o formulario que contiene.
    class Meta:
        db_table = 'domicilio'
        verbose_name = 'Domicilio'
        verbose_name_plural = 'Domicilios'

    # Construye la representación textual legible del objeto.
    def __str__(self):
        return f"Domicilio: {self.nombre} {self.apellido}"


# Representa visitante y define sus datos y relaciones persistentes.
class Visitante(models.Model):
    id_visitante = models.AutoField(primary_key=True, db_column='Id_visitante')
    nombre = models.CharField(max_length=100, db_column='Nombre')
    apellido = models.CharField(max_length=100, db_column='Apellido')
    cedula = models.CharField(
        max_length=20,
        db_column='Cedula',
        validators=[validar_cedula_maxima_texto],
    )
    vehiculo_trae = models.CharField(max_length=2, db_column='Vehiculo_Trae')  # Ej: 'SI', 'NO'
    tipo_v = models.CharField(max_length=50, blank=True, null=True, db_column='Tipo_V')
    tipo_residente = models.CharField(max_length=50, blank=True, null=True, db_column='Tipo_Residente')
    placa_v = models.CharField(max_length=20, blank=True, null=True, db_column='Placa_V')
    vehiculo_tipo = models.CharField(max_length=50, blank=True, null=True, db_column='Vehiculo_Tipo')
    conductor = models.CharField(max_length=100, blank=True, null=True, db_column='Conductor')
    cantidad_personas = models.PositiveIntegerField(default=1, db_column='Cantidad_Personas')
    residente_secundario = models.ForeignKey(
        Residente,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='visitantes_autorizados',
        db_column='Id_residente_secundario',
    )
    propietario_autorizador = models.ForeignKey(
        Propietario,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='visitantes_autorizados',
        db_column='Id_propietario_autorizador',
    )
    autoriza = models.CharField(
        max_length=2,
        choices=(('SI', 'Sí'), ('NO', 'No')),
        default='NO',
        db_column='Autoriza',
    )

    # Agrupa las opciones de configuración del modelo o formulario que contiene.
    class Meta:
        db_table = 'visitante'
        verbose_name = 'Visitante'
        verbose_name_plural = 'Visitantes'

    # Construye la representación textual legible del objeto.
    def __str__(self):
        return f"Visitante: {self.nombre} {self.apellido} ({self.cedula})"


# Representa paquete y define sus datos y relaciones persistentes.
class Paquete(models.Model):
    id_paquete = models.AutoField(primary_key=True, db_column='Id_paquete')
    nombre = models.CharField(max_length=100, db_column='Nombre')
    apellido = models.CharField(max_length=100, db_column='Apellido')
    transportadora = models.CharField(max_length=100, db_column='Transportadora')
    telefono_t = models.CharField(max_length=20, blank=True, null=True, db_column='Telefono_T')
    desc_tipo = models.CharField(max_length=200, blank=True, null=True, db_column='Desc_Tipo')
    guia = models.CharField(max_length=100, blank=True, null=True, db_column='Guia')
    evidencia = models.FileField(upload_to='evidencias_paquetes/', max_length=255, blank=True, null=True, db_column='Evidencia')
    residente_secundario = models.ForeignKey(Residente, on_delete=models.SET_NULL, blank=True, null=True, related_name='paquetes_autorizados', db_column='Id_residente_secundario')
    propietario_autorizador = models.ForeignKey(Propietario, on_delete=models.SET_NULL, blank=True, null=True, related_name='paquetes_autorizados', db_column='Id_propietario_autorizador')
    llamada = models.CharField(max_length=15, choices=(('CONTESTO', 'Sí contestó'), ('NO_CONTESTO', 'No contestó')), default='NO_CONTESTO', db_column='Llamada')
    informacion_adicional = models.CharField(max_length=300, blank=True, null=True, db_column='Informacion_Adicional')

    # Agrupa las opciones de configuración del modelo o formulario que contiene.
    class Meta:
        db_table = 'paquete'
        verbose_name = 'Paquete'
        verbose_name_plural = 'Paquetes'

    # Construye la representación textual legible del objeto.
    def __str__(self):
        return f"Paquete {self.guia or ''} - {self.transportadora}"


# Representa proceso y define sus datos y relaciones persistentes.
class Proceso(models.Model):
    ESTADOS_DOMICILIO = (
        ('PENDIENTE', 'Pendiente'),
        ('ENTREGADO', 'ENTREGA OPORTUNA'),
        ('ENTREGADO_TARDE', 'ENTREGA TARDIA'),
        ('DEMORADO', 'Demorado'),
        ('SALIDO', 'Salido'),
    )
    id_proceso = models.AutoField(primary_key=True, db_column='Id_proceso')
    tipo = models.CharField(max_length=20, db_column='Tipo')
    estado = models.CharField(max_length=20, choices=ESTADOS_DOMICILIO, default='PENDIENTE', db_column='Estado')
    tiempo_restante = models.PositiveIntegerField(default=60, db_column='Tiempo_Restante')
    cedula = models.CharField(max_length=20, blank=True, null=True, db_column='Cedula')
    nombre = models.CharField(max_length=100, db_column='Nombre')
    vehiculo_tiene = models.CharField(max_length=2, blank=True, null=True, db_column='Vehiculo_Tiene')
    vehiculo_tipo = models.CharField(max_length=50, blank=True, null=True, db_column='Vehiculo_Tipo')
    placa = models.CharField(max_length=20, blank=True, null=True, db_column='Placa')
    descripcion = models.CharField(max_length=200, blank=True, null=True, db_column='Descripcion')
    fecha = models.DateTimeField(db_column='Fecha')
    fecha_salida = models.DateTimeField(blank=True, null=True, db_column='Fecha_Salida')

    # Relaciones obligatorias
    id_guardia = models.ForeignKey(
        Guardia,
        on_delete=models.CASCADE,
        db_column='Id_guardia',
        related_name='procesos'
    )
    id_casa = models.ForeignKey(
        Casa,
        on_delete=models.CASCADE,
        db_column='Id_casa',
        related_name='procesos'
    )

    # Relaciones opcionales (ON DELETE SET NULL)
    id_domicilio = models.ForeignKey(
        Domicilio,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        db_column='Id_domicilio',
        related_name='procesos'
    )
    id_visitante = models.ForeignKey(
        Visitante,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        db_column='Id_visitante',
        related_name='procesos'
    )
    id_paquete = models.ForeignKey(
        Paquete,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        db_column='Id_paquete',
        related_name='procesos'
    )

    # Agrupa las opciones de configuración del modelo o formulario que contiene.
    class Meta:
        db_table = 'proceso'
        verbose_name = 'Proceso / Movimiento'
        verbose_name_plural = 'Procesos / Movimientos'

    # Construye la representación textual legible del objeto.
    def __str__(self):
        return f"Proceso {self.tipo} - {self.fecha.strftime('%Y-%m-%d %H:%M')}"


# Representa registro bitácora y define sus datos y relaciones persistentes.
class RegistroBitacora(models.Model):
    modulo = models.CharField(max_length=50)
    accion = models.CharField(max_length=30, default='Registro')
    registro = models.CharField(max_length=150)
    descripcion = models.TextField(blank=True)
    fecha = models.DateTimeField(default=timezone.now, db_index=True)
    casa = models.ForeignKey(
        Casa,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='registros_bitacora',
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='registros_bitacora',
    )

    # Agrupa las opciones de configuración del modelo o formulario que contiene.
    class Meta:
        db_table = 'registro_bitacora'
        ordering = ('-fecha', '-id')
        verbose_name = 'Registro de bitácora'
        verbose_name_plural = 'Registros de bitácora'

    # Construye la representación textual legible del objeto.
    def __str__(self):
        return f'{self.modulo}: {self.registro}'


# Representa pago y define sus datos y relaciones persistentes.
class Pago(models.Model):
    id_pago = models.AutoField(primary_key=True, db_column='Id_pago')
    valor = models.DecimalField(max_digits=10, decimal_places=2, db_column='Valor')
    valor_mora_aplicada = models.DecimalField(max_digits=12, decimal_places=2, default=0, db_column='Valor_Mora_Aplicada')
    valor_cartera_aplicada = models.DecimalField(max_digits=12, decimal_places=2, default=0, db_column='Valor_Cartera_Aplicada')
    valor_saldo_favor_aplicado = models.DecimalField(max_digits=12, decimal_places=2, default=0, db_column='Valor_Saldo_Favor_Aplicado')
    saldo_pendiente_despues = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        blank=True,
        null=True,
        db_column='Saldo_Pendiente_Despues',
    )
    fecha = models.DateField(db_column='Fecha')
    estado = models.CharField(max_length=50, default='Pendiente', db_column='Estado')
    evidencia = models.FileField(upload_to='evidencias_pagos/', max_length=100, db_column='Evidencia')

    # Relación
    id_casa = models.ForeignKey(
        Casa,
        on_delete=models.PROTECT,
        db_column='Id_casa',
        related_name='pagos'
    )

    # Agrupa las opciones de configuración del modelo o formulario que contiene.
    class Meta:
        db_table = 'pago'
        verbose_name = 'Pago'
        verbose_name_plural = 'Pagos'

    # Construye la representación textual legible del objeto.
    def __str__(self):
        return f"Pago Casa {self.id_casa.numero_casa} - ${self.valor}"


# Representa notas y define sus datos y relaciones persistentes.
class Notas(models.Model):
    id_nota = models.AutoField(primary_key=True, db_column='Id_nota')
    nombre = models.CharField(max_length=100, db_column='Nombre')
    apellido = models.CharField(max_length=100, db_column='Apellido')
    telefono = models.CharField(max_length=20, blank=True, null=True, db_column='Telefono')
    nota = models.CharField(max_length=200, db_column='Nota')
    evidencia = models.FileField(upload_to='evidencias_notas/', max_length=255, blank=True, null=True, db_column='Evidencia')
    fecha = models.DateTimeField(default=timezone.now, db_column='Fecha')

    # Relación
    id_guardia = models.ForeignKey(
        Guardia,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        db_column='Id_guardia',
        related_name='notas'
    )

    # Agrupa las opciones de configuración del modelo o formulario que contiene.
    class Meta:
        db_table = 'notas'
        verbose_name = 'Nota'
        verbose_name_plural = 'Notas'

    # Construye la representación textual legible del objeto.
    def __str__(self):
        return f"Nota por {self.nombre} {self.apellido}"


# Representa novedad y define sus datos y relaciones persistentes.
class Novedad(models.Model):
    id_novedad = models.AutoField(primary_key=True, db_column='Id_novedad')
    titulo = models.CharField(max_length=120, db_column='Titulo')
    tipo = models.CharField(max_length=80, default='General', db_column='Tipo')
    nota = models.CharField(max_length=200, db_column='Nota')
    evidencia = models.FileField(upload_to='evidencias_novedades/', max_length=255, blank=True, null=True, db_column='Evidencia')
    fecha_creacion = models.DateTimeField(auto_now_add=True, db_column='Fecha_Creacion')
    fecha_suceso = models.DateTimeField(default=timezone.now, db_column='Fecha')
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='novedades_publicadas',
        db_column='Registrado_por',
    )

    # Agrupa las opciones de configuración del modelo o formulario que contiene.
    class Meta:
        db_table = 'novedad'
        verbose_name = 'Novedad'
        verbose_name_plural = 'Novedades'
        ordering = ('fecha_suceso', 'id_novedad')

    # Construye la representación textual legible del objeto.
    def __str__(self):
        return self.titulo


# Representa reseña y define sus datos y relaciones persistentes.
class Resena(models.Model):
    CALIFICACIONES = tuple((valor, f'{valor} estrella' if valor == 1 else f'{valor} estrellas') for valor in range(1, 6))
    id_resena = models.AutoField(primary_key=True, db_column='Id_resena')
    nombre = models.CharField(max_length=100, db_column='Nombre')
    comentario = models.TextField(max_length=500, db_column='Comentario')
    calificacion = models.PositiveSmallIntegerField(choices=CALIFICACIONES, db_column='Calificacion')
    rol_usuario = models.CharField(max_length=20, blank=True, default='', db_column='Rol_Usuario')
    fecha_creacion = models.DateTimeField(auto_now_add=True, db_column='Fecha_Creacion')
    aprobada = models.BooleanField(default=False, db_column='Aprobada')
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='resenas',
        db_column='Usuario',
    )

    # Agrupa las opciones de configuración del modelo o formulario que contiene.
    class Meta:
        db_table = 'resena'
        ordering = ('-fecha_creacion', 'id_resena')
        verbose_name = 'Reseña'
        verbose_name_plural = 'Reseñas'

    # Construye la representación textual legible del objeto.
    def __str__(self):
        return f'{self.nombre} - {self.calificacion} estrellas'


# Representa configuración copias seguridad y define sus datos y relaciones persistentes.
class ConfiguracionCopiasSeguridad(models.Model):
    UNIDADES_INTERVALO = (
        ('minutos', 'Minutos'),
        ('horas', 'Horas'),
        ('dias', 'Días'),
    )
    intervalo = models.PositiveIntegerField(default=1)
    unidad_intervalo = models.CharField(max_length=10, choices=UNIDADES_INTERVALO, default='dias')
    automaticas_activas = models.BooleanField(default=True)
    ruta_destino = models.CharField(max_length=1000, blank=True, default='')
    ultima_automatica = models.DateTimeField(blank=True, null=True)
    proxima_automatica = models.DateTimeField(blank=True, null=True)

    # Agrupa las opciones de configuración del modelo o formulario que contiene.
    class Meta:
        db_table = 'configuracion_copias_seguridad'
        verbose_name = 'Configuración de copias de seguridad'
        verbose_name_plural = 'Configuración de copias de seguridad'

    # Construye la representación textual legible del objeto.
    def __str__(self):
        return 'Programación de copias de seguridad'


# Representa copia seguridad y define sus datos y relaciones persistentes.
class CopiaSeguridad(models.Model):
    TIPOS = (
        ('manual', 'Manual'),
        ('automatica', 'Automática'),
    )
    ALCANCES = (
        ('proyecto', 'Proyecto completo'),
        ('informacion', 'Solo información'),
    )
    archivo = models.CharField(max_length=255, unique=True)
    ruta_archivo = models.CharField(max_length=1000, blank=True, default='')
    sha256 = models.CharField(max_length=64)
    tipo = models.CharField(max_length=12, choices=TIPOS)
    alcance = models.CharField(max_length=12, choices=ALCANCES, default='proyecto')
    creado_en = models.DateTimeField(default=timezone.now)
    tamano_bytes = models.PositiveBigIntegerField()
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='copias_seguridad_creadas',
    )

    # Agrupa las opciones de configuración del modelo o formulario que contiene.
    class Meta:
        db_table = 'copia_seguridad'
        ordering = ('-creado_en', '-pk')
        verbose_name = 'Copia de seguridad'
        verbose_name_plural = 'Copias de seguridad'

    # Construye la representación textual legible del objeto.
    def __str__(self):
        return f'{self.get_tipo_display()} - {self.creado_en:%Y-%m-%d %H:%M}'