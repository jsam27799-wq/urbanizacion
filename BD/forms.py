# Módulo: Define formularios, presentación de campos y reglas de validación de los datos recibidos.
from pathlib import Path

from django import forms
from django.conf import settings
from django.forms import formset_factory
from django.contrib.auth.forms import SetPasswordForm
from django.contrib.auth.models import User
from django.core.validators import MinLengthValidator, RegexValidator
from django.utils import timezone

from .models import MAX_CEDULA, Casa, ConfiguracionCartera, ConfiguracionCopiasSeguridad, Domicilio, Guardia, Notas, Novedad, Paquete, Pago, Propietario, Resena, Residente, Visitante
from .estados import ESTADOS_CONFIGURABLES, color_texto, normalizar_estados


# Organiza el flujo de opciones estado configuradas dentro de este módulo.
def opciones_estado_configuradas(modulo, opciones):
    configurados = ConfiguracionCartera.objects.filter(pk=1).values_list(
        'estados_visualizacion', flat=True,
    ).first()
    estados = normalizar_estados(configurados).get(modulo, {})
    return tuple(
        (valor, estados.get(valor, {}).get('nombre', etiqueta))
        for valor, etiqueta in opciones
    )


# Define campos y reglas reutilizables para cédula unica mixin.
class CedulaUnicaMixin:
    MODELOS_CON_CEDULA = (Propietario, Residente, Guardia, Visitante)

    # Valida y normaliza el campo cédula antes de aceptar el formulario.
    def clean_cedula(self):
        cedula = self.cleaned_data.get('cedula')
        if cedula in (None, ''):
            return cedula
        # Solo se consulta unicidad para una cédula compuesta por dígitos ASCII; en edición se excluye el registro actual.
        if not str(cedula).isascii() or not str(cedula).isdigit():
            return cedula

        for modelo in self.MODELOS_CON_CEDULA:
            registros = modelo.objects.filter(cedula=cedula)
            if modelo is self._meta.model and self.instance and self.instance.pk:
                registros = registros.exclude(pk=self.instance.pk)
            if registros.exists():
                raise forms.ValidationError('Ya existe una persona registrada con esta cédula.')
        return cedula


# Define campos y reglas reutilizables para solo texto mixin.
class SoloTextoMixin:
    CAMPOS_TEXTO = {'nombre', 'apellido'}

    # Inicializa el objeto y configura los valores necesarios para su uso.
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for nombre, field in self.fields.items():
            if nombre in self.CAMPOS_TEXTO:
                field.widget.attrs.update({
                    'pattern': r'[\p{L} ]+',
                    'oninput': "this.value = this.value.replace(/[^\\p{L} ]/gu, '')",
                })

    # Aplica validaciones relacionadas entre los campos y devuelve los datos depurados.
    def clean(self):
        cleaned_data = super().clean()
        for nombre in self.CAMPOS_TEXTO:
            valor = cleaned_data.get(nombre)
            if valor not in (None, ''):
                # Se eliminan espacios laterales antes de comprobar que el nombre solo contenga letras y espacios.
                valor = str(valor).strip()
                if not valor or not all(caracter.isalpha() or caracter.isspace() for caracter in valor):
                    self.add_error(nombre, 'Este campo solo puede contener letras y espacios.')
                else:
                    cleaned_data[nombre] = valor
        return cleaned_data


# Define campos y reglas reutilizables para solo digitos mixin.
class SoloDigitosMixin(SoloTextoMixin):
    CAMPOS_NUMERICOS = {'cedula', 'telefono', 'telefono_negocio', 'telefono_t'}

    # Inicializa el objeto y configura los valores necesarios para su uso.
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for nombre, field in self.fields.items():
            if nombre in self.CAMPOS_NUMERICOS:
                field.widget.attrs.update({
                    'inputmode': 'numeric',
                    'pattern': '[0-9]*',
                    'oninput': "this.value = this.value.replace(/[^0-9]/g, '')",
                })

    # Aplica validaciones relacionadas entre los campos y devuelve los datos depurados.
    def clean(self):
        cleaned_data = super().clean()
        for nombre in self.CAMPOS_NUMERICOS:
            valor = cleaned_data.get(nombre)
            if valor not in (None, '') and (not str(valor).isascii() or not str(valor).isdigit()):
                self.add_error(nombre, 'Este campo solo puede contener números.')
        return cleaned_data


# Define campos y reglas reutilizables para guardia automatico mixin.
class GuardiaAutomaticoMixin:
    # Inicializa el objeto y configura los valores necesarios para su uso.
    def __init__(self, *args, guardia=None, **kwargs):
        super().__init__(*args, **kwargs)
        nombre_campo = 'guardia' if 'guardia' in self.fields else 'id_guardia'
        if guardia and nombre_campo in self.fields:
            campo = self.fields[nombre_campo]
            campo.queryset = Guardia.objects.filter(pk=guardia.pk)
            campo.initial = guardia
            campo.disabled = True


# Define campos y reglas reutilizables para evidencia obligatoria mixin.
class EvidenciaObligatoriaMixin:
    # Inicializa el objeto y configura los valores necesarios para su uso.
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'evidencia' in self.fields:
            tiene_evidencia = bool(self.instance and self.instance.pk and self.instance.evidencia)
            self.fields['evidencia'].required = not tiene_evidencia


# Define campos y reglas reutilizables para reseña formulario.
class ResenaForm(SoloTextoMixin, forms.ModelForm):
    # Agrupa las opciones de configuración del modelo o formulario que contiene.
    class Meta:
        model = Resena
        fields = ('nombre', 'calificacion', 'comentario')
        labels = {
            'nombre': 'Tu nombre',
            'calificacion': 'Calificación',
            'comentario': 'Cuéntanos tu experiencia',
        }
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre'}),
            'calificacion': forms.Select(attrs={'class': 'form-select'}),
            'comentario': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Escribe tu reseña'}),
        }


# Define campos y reglas reutilizables para residente formulario.
class ResidenteForm(CedulaUnicaMixin, SoloDigitosMixin, forms.ModelForm):
    # Agrupa las opciones de configuración del modelo o formulario que contiene.
    class Meta:
        model = Residente
        fields = ('cedula', 'nombre', 'apellido', 'telefono')
        labels = {
            'cedula': 'Cédula',
            'nombre': 'Nombre',
            'apellido': 'Apellido',
            'telefono': 'Teléfono',
        }
        widgets = {
            'cedula': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': MAX_CEDULA}),
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'apellido': forms.TextInput(attrs={'class': 'form-control'}),
            'telefono': forms.TextInput(attrs={'class': 'form-control'}),
        }

    # Valida y normaliza el campo cédula antes de aceptar el formulario.
    def clean_cedula(self):
        cedula = super().clean_cedula()
        if cedula is None:
            return cedula
        if cedula <= 0:
            raise forms.ValidationError('La cédula debe ser mayor que cero.')
        return cedula


class ResidenteDirectorioForm(ResidenteForm):
    class Meta(ResidenteForm.Meta):
        fields = ('cedula', 'nombre', 'apellido', 'telefono', 'correo')
        labels = {
            **ResidenteForm.Meta.labels,
            'correo': 'Correo electrónico',
        }
        widgets = {
            **ResidenteForm.Meta.widgets,
            'correo': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'nombre@correo.com',
            }),
        }

    def clean_correo(self):
        correo = (self.cleaned_data.get('correo') or '').strip()
        return correo.lower() or None


TIPOS_VISITANTE = (('Familiar', 'Familiar'), ('Amigo', 'Amigo'), ('Proveedor', 'Proveedor'), ('Contratista', 'Contratista'), ('Otro', 'Otro'))


# Define campos y reglas reutilizables para residente secundario field.
class ResidenteSecundarioField(forms.ModelChoiceField):
    # Organiza el flujo de label from instance dentro de este módulo.
    def label_from_instance(self, obj):
        return f'{obj.nombre} {obj.apellido} - Tel: {obj.telefono or "Sin teléfono"}'


class ResidenteAsignacionField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return f'{obj.nombre} {obj.apellido} - Cédula: {obj.cedula}'


# Define campos y reglas reutilizables para visitante ingreso formulario.
class VisitanteIngresoForm(GuardiaAutomaticoMixin, CedulaUnicaMixin, SoloDigitosMixin, forms.ModelForm):
    TIPO_ENTRADA = (('NO', 'Peatonal'), ('SI', 'Vehicular'))
    AUTORIZA = (('SI', 'Sí'), ('NO', 'No'))
    vehiculo_trae = forms.ChoiceField(choices=TIPO_ENTRADA, label='Tipo de entrada', widget=forms.Select(attrs={'class': 'form-select'}))
    vivienda = forms.ModelChoiceField(
        queryset=Casa.objects.order_by('numero_casa'),
        label='Casa visitada',
        empty_label='Seleccione una casa',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    guardia = forms.ModelChoiceField(
        queryset=Guardia.objects.order_by('apellido', 'nombre'),
        label='Guardia que registra',
        empty_label='Seleccione un guardia',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    persona_autorizante = forms.ChoiceField(
        choices=(),
        required=False,
        label='Residente o propietario que autoriza',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    tipo_visitante_otro = forms.CharField(
        required=False,
        label='Especifique el tipo de visitante',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Escriba el tipo de visitante'}),
    )
    autoriza = forms.ChoiceField(
        choices=AUTORIZA,
        label='Autoriza',
        initial='NO',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )

    # Inicializa el objeto y configura los valores necesarios para su uso.
    def __init__(self, *args, casa_id=None, **kwargs):
        super().__init__(*args, **kwargs)
        casa_id = casa_id or (self.data.get('vivienda') if self.is_bound else None)
        # Limita las opciones de autorización a las personas vinculadas con la casa seleccionada.
        if casa_id:
            casa = Casa.objects.prefetch_related('residentes_secundarios').select_related(
                'id_residente', 'id_propietario',
            ).filter(pk=casa_id).first()
            personas = []
            if casa:
                if casa.id_residente:
                    personas.append((
                        f'residente:{casa.id_residente.pk}',
                        f'{casa.id_residente.nombre} {casa.id_residente.apellido} - Tel: {casa.id_residente.telefono or "Sin teléfono"}',
                    ))
                # El residente principal se omite del listado secundario cuando también figura en esa relación.
                personas.extend(
                    (
                        f'residente:{residente.pk}',
                        f'{residente.nombre} {residente.apellido} - Tel: {residente.telefono or "Sin teléfono"}',
                    )
                    for residente in casa.residentes_secundarios.all()
                    if not casa.id_residente or residente.pk != casa.id_residente.pk
                )
                if casa.id_propietario:
                    personas.append((
                        f'propietario:{casa.id_propietario.pk}',
                        f'{casa.id_propietario.nombre} {casa.id_propietario.apellido} - Tel: {casa.id_propietario.telefono or "Sin teléfono"}',
                    ))
            self.fields['persona_autorizante'].choices = [('', 'Seleccione una persona')] + personas
            self.initial['vivienda'] = casa_id
        if self.instance and self.instance.pk:
            if self.instance.propietario_autorizador_id:
                self.initial['persona_autorizante'] = f'propietario:{self.instance.propietario_autorizador_id}'
            elif self.instance.residente_secundario_id:
                self.initial['persona_autorizante'] = f'residente:{self.instance.residente_secundario_id}'
        tipos_visitante = {valor for valor, _ in TIPOS_VISITANTE}
        if self.instance and self.instance.pk and self.instance.tipo_v not in tipos_visitante:
            self.initial['tipo_v'] = 'Otro'
            self.initial['tipo_visitante_otro'] = self.instance.tipo_v
        self.order_fields([
            'nombre', 'apellido', 'cedula', 'tipo_v', 'tipo_visitante_otro',
            'vivienda', 'persona_autorizante', 'autoriza', 'guardia',
            'vehiculo_trae', 'vehiculo_tipo', 'placa_v', 'conductor',
            'cantidad_personas',
        ])

    # Agrupa las opciones de configuración del modelo o formulario que contiene.
    class Meta:
        model = Visitante
        fields = ('nombre', 'apellido', 'cedula', 'tipo_v', 'vivienda', 'autoriza', 'vehiculo_trae', 'vehiculo_tipo', 'placa_v', 'conductor', 'cantidad_personas')
        labels = {
            'nombre': 'Nombre',
            'apellido': 'Apellido',
            'cedula': 'Documento de identidad',
            'vehiculo_trae': 'Tipo de entrada',
            'tipo_v': 'Tipo de visitante',
            'vehiculo_tipo': 'Tipo de vehículo',
            'placa_v': 'Placa',
            'conductor': 'Conductor',
            'cantidad_personas': 'Cantidad de personas',
        }
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'apellido': forms.TextInput(attrs={'class': 'form-control'}),
            'cedula': forms.TextInput(attrs={'class': 'form-control', 'inputmode': 'numeric', 'pattern': '[0-9]*'}),
            'tipo_v': forms.Select(choices=TIPOS_VISITANTE, attrs={'class': 'form-select'}),
            'vehiculo_tipo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Moto, carro...'}),
            'placa_v': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ABC-123'}),
            'conductor': forms.TextInput(attrs={'class': 'form-control'}),
            'cantidad_personas': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
        }

    # Aplica validaciones relacionadas entre los campos y devuelve los datos depurados.
    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('tipo_v') == 'Otro':
            tipo_visitante_otro = (cleaned_data.get('tipo_visitante_otro') or '').strip()
            if not tipo_visitante_otro:
                self.add_error('tipo_visitante_otro', 'Especifique el tipo de visitante.')
            else:
                cleaned_data['tipo_v'] = tipo_visitante_otro
        if cleaned_data.get('vehiculo_trae') == 'SI':
            for field in ('vehiculo_tipo', 'placa_v', 'conductor'):
                if not cleaned_data.get(field):
                    self.add_error(field, 'Este campo es obligatorio para una entrada vehicular.')
        return cleaned_data

    # Persiste los datos del formulario y completa las actualizaciones asociadas.
    def save(self, commit=True):
        visitante = super().save(commit=False)
        visitante.residente_secundario = None
        visitante.propietario_autorizador = None
        persona = self.cleaned_data.get('persona_autorizante') or ''
        # El prefijo del valor del selector determina cuál de las dos relaciones de autorización debe guardarse.
        tipo, _, persona_id = persona.partition(':')
        if tipo == 'residente' and persona_id.isdigit():
            visitante.residente_secundario_id = int(persona_id)
        elif tipo == 'propietario' and persona_id.isdigit():
            visitante.propietario_autorizador_id = int(persona_id)
        if commit:
            visitante.save()
        return visitante


class VisitanteEstadoForm(forms.Form):
    estado = forms.ChoiceField(
        choices=(),
        label='Estado',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['estado'].choices = opciones_estado_configuradas(
            'visitante',
            (('PENDIENTE', 'Ingresado'), ('SALIDO', 'Salido')),
        )


# Define campos y reglas reutilizables para casa formulario.
class CasaForm(forms.ModelForm):
    ESTADOS_CASA = (
        ('Para Arrendar', 'Para Arrendar'),
        ('Ocupada', 'Ocupada'),
        ('Deshabilitada', 'Deshabilitada'),
        ('Otros', 'Otros'),
    )

    numero_casa = forms.IntegerField(
        label='Número de casa',
        min_value=1,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'step': 1, 'placeholder': 'Ej. 100'})
    )
    cantidad_personas = forms.IntegerField(
        label='Cantidad de habitaciones',
        min_value=1,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'step': 1})
    )
    cantidad_residentes = forms.IntegerField(
        label='Cantidad de residentes',
        min_value=1,
        initial=1,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'step': 1})
    )
    estado = forms.ChoiceField(
        choices=ESTADOS_CASA,
        label='Estado',
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    estado_otro = forms.CharField(
        required=False,
        label='Especifique otro estado',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. En remodelación'})
    )
    crear_en_lote = forms.BooleanField(
        required=False,
        label='Registrar casa vacía',
    )
    cantidad_casas = forms.IntegerField(
        required=False,
        min_value=1,
        label='Cantidad de casas a crear',
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'step': 1})
    )
    numero_inicial = forms.IntegerField(
        required=False,
        min_value=1,
        label='Número inicial',
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'step': 1})
    )

    # Agrupa las opciones de configuración del modelo o formulario que contiene.
    class Meta:
        model = Casa
        fields = ('numero_casa', 'cantidad_personas', 'cantidad_residentes', 'estado', 'estado_otro', 'cartera', 'id_residente')
        labels = {
            'cartera': 'Cartera pendiente',
            'id_residente': 'Residente principal',
        }
        widgets = {
            'cartera': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'step': 1}),
            'id_residente': forms.Select(attrs={'class': 'form-select'}),
        }

    # Inicializa el objeto y configura los valores necesarios para su uso.
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['id_residente'].queryset = Residente.objects.order_by('apellido', 'nombre')
        configurados = ConfiguracionCartera.objects.filter(pk=1).values_list(
            'estados_visualizacion', flat=True,
        ).first()
        estados_configurados = normalizar_estados(configurados).get('casa', {})
        opciones_estado = [
            (valor, estados_configurados.get(valor, {}).get('nombre', etiqueta))
            for valor, etiqueta in self.ESTADOS_CASA
        ]
        valores_estado = {valor for valor, _ in opciones_estado}
        estados_existentes = set(Casa.objects.values_list('estado', flat=True).distinct())
        if self.instance and self.instance.pk:
            estados_existentes.add(self.instance.estado)
        opciones_estado.extend(
            (estado, estados_configurados.get(estado, {}).get('nombre', estado))
            for estado in sorted(estados_existentes - valores_estado - {'Otros'})
        )
        self.fields['estado'].choices = opciones_estado

        if self.data and self.data.get('crear_en_lote'):
            for field_name in ('numero_casa', 'cantidad_personas', 'cantidad_residentes', 'estado', 'estado_otro', 'cartera', 'id_residente'):
                if field_name in self.fields:
                    self.fields[field_name].required = False

        if self.instance and self.instance.estado in {valor for valor, _ in opciones_estado}:
            self.fields['estado'].initial = self.instance.estado
        elif self.instance and self.instance.pk:
            self.fields['estado'].initial = 'Otros'
            self.fields['estado_otro'].initial = self.instance.estado

    # Valida y normaliza el campo numero casa antes de aceptar el formulario.
    def clean_numero_casa(self):
        numero_casa = self.cleaned_data.get('numero_casa')
        if numero_casa is None:
            return numero_casa
        if Casa.objects.filter(numero_casa=numero_casa).exclude(pk=self.instance.pk if self.instance else None).exists():
            raise forms.ValidationError('Ya existe una casa con este número. Elija otro número de casa.')
        return numero_casa

    # Aplica validaciones relacionadas entre los campos y devuelve los datos depurados.
    def clean(self):
        cleaned_data = super().clean()
        estado = cleaned_data.get('estado')
        estado_otro = (cleaned_data.get('estado_otro') or '').strip()
        if estado == 'Otros':
            if not estado_otro:
                self.add_error('estado_otro', 'Especifique el estado de la casa.')
            else:
                cleaned_data['estado'] = estado_otro
        if cleaned_data.get('crear_en_lote'):
            if cleaned_data.get('cantidad_personas') is None:
                cleaned_data['cantidad_personas'] = 1
            if cleaned_data.get('cantidad_residentes') is None:
                cleaned_data['cantidad_residentes'] = 1
            if not cleaned_data.get('estado'):
                cleaned_data['estado'] = 'Activa'
            if cleaned_data.get('cartera') is None:
                cleaned_data['cartera'] = 0
            if cleaned_data.get('id_residente') is None:
                cleaned_data['id_residente'] = None

            cantidad = cleaned_data.get('cantidad_casas')
            numero_inicial = cleaned_data.get('numero_inicial')
            if not cantidad:
                self.add_error('cantidad_casas', 'Debe indicar cuántas casas quiere crear.')
            if not numero_inicial:
                self.add_error('numero_inicial', 'Debe indicar desde qué número iniciar.')
            if cantidad and numero_inicial:
                numeros = list(range(numero_inicial, numero_inicial + cantidad))
                duplicados = [n for n in numeros if Casa.objects.filter(numero_casa=n).exclude(pk=self.instance.pk if self.instance else None).exists()]
                if duplicados:
                    self.add_error('numero_inicial', f'Ya existen casas en ese rango: {duplicados[:10]}')
        return cleaned_data


# Define campos y reglas reutilizables para residente secundario formulario.
class ResidenteSecundarioForm(ResidenteForm):
    residente_existente = ResidenteAsignacionField(
        queryset=Residente.objects.none(),
        required=False,
        label='Residente ya registrado',
        empty_label='Registrar un residente nuevo',
        widget=forms.Select(attrs={
            'class': 'form-select',
            'data-residente-existente': '',
        }),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['residente_existente'].queryset = Residente.objects.order_by('apellido', 'nombre')
        self.order_fields(('residente_existente', 'cedula', 'nombre', 'apellido', 'telefono'))
        if self.is_bound and self.data.get(self.add_prefix('residente_existente')):
            for field_name in ('cedula', 'nombre', 'apellido', 'telefono'):
                self.fields[field_name].required = False

    # Si se inicia el registro opcional, exige completar también el teléfono.
    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('residente_existente'):
            return cleaned_data
        if self.has_changed() and not cleaned_data.get('telefono'):
            self.add_error('telefono', 'Complete el teléfono para registrar al residente.')
        return cleaned_data


ResidenteSecundarioFormSet = formset_factory(ResidenteSecundarioForm, extra=1)


TURNOS_GUARDIA = (('Mañana', 'Mañana'), ('Tarde', 'Tarde'))
REQUISITOS_CONTRASENA = 'Mínimo 8 caracteres, una mayúscula y un carácter especial.'
VALIDADORES_CONTRASENA = [
    MinLengthValidator(8, 'La contraseña debe tener al menos 8 caracteres.'),
    RegexValidator(r'(?=.*[A-Z])', 'La contraseña debe incluir al menos una mayúscula.'),
    RegexValidator(r'(?=.*[^A-Za-z0-9])', 'La contraseña debe incluir al menos un carácter especial.'),
]


class AdminResetPasswordForm(SetPasswordForm):
    admin_password = forms.CharField(
        label='Contraseña actual del administrador',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'autocomplete': 'current-password',
        }),
    )
    new_password1 = forms.CharField(
        label='Nueva contraseña',
        validators=VALIDADORES_CONTRASENA,
        help_text=REQUISITOS_CONTRASENA,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'autocomplete': 'new-password',
        }),
    )
    new_password2 = forms.CharField(
        label='Confirmar nueva contraseña',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'autocomplete': 'new-password',
        }),
    )

    def __init__(self, admin_user, user, *args, **kwargs):
        self.admin_user = admin_user
        super().__init__(user, *args, **kwargs)

    def clean_admin_password(self):
        password = self.cleaned_data['admin_password']
        if not self.admin_user.check_password(password):
            raise forms.ValidationError('La contraseña del administrador no es correcta.')
        return password


# Define campos y reglas reutilizables para guardia formulario.
class GuardiaForm(CedulaUnicaMixin, SoloDigitosMixin, forms.ModelForm):
    activo = forms.BooleanField(label='Cuenta activa', required=False, initial=True)
    turno = forms.ChoiceField(
        choices=TURNOS_GUARDIA,
        label='Turno',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    password = forms.CharField(
        label='Contraseña de acceso',
        validators=VALIDADORES_CONTRASENA,
        help_text=REQUISITOS_CONTRASENA,
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
    )
    password_confirmacion = forms.CharField(
        label='Confirmar contraseña',
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
    )
    # Agrupa las opciones de configuración del modelo o formulario que contiene.
    class Meta:
        model = Guardia
        fields = ('cedula', 'nombre', 'apellido', 'telefono', 'turno', 'activo', 'password', 'password_confirmacion')
        labels = {
            'cedula': 'Cédula',
            'nombre': 'Nombre',
            'apellido': 'Apellido',
            'telefono': 'Teléfono',
            'turno': 'Turno',
        }
        widgets = {
            'cedula': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': MAX_CEDULA}),
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'apellido': forms.TextInput(attrs={'class': 'form-control'}),
            'telefono': forms.TextInput(attrs={'class': 'form-control'}),
        }

    # Aplica validaciones relacionadas entre los campos y devuelve los datos depurados.
    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('password') and cleaned_data.get('password') != cleaned_data.get('password_confirmacion'):
            self.add_error('password_confirmacion', 'Las contraseñas no coinciden.')
        return cleaned_data


# Define campos y reglas reutilizables para visitante formulario.
class VisitanteForm(VisitanteIngresoForm):
    # Agrupa las opciones de configuración del modelo o formulario que contiene.
    class Meta(VisitanteIngresoForm.Meta):
        fields = VisitanteIngresoForm.Meta.fields

    # Inicializa el objeto y configura los valores necesarios para su uso.
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields.pop('vivienda')
        self.fields.pop('guardia')


# Define campos y reglas reutilizables para domicilio ingreso formulario.
class DomicilioIngresoForm(GuardiaAutomaticoMixin, SoloDigitosMixin, forms.ModelForm):
    vivienda = forms.ModelChoiceField(queryset=Casa.objects.order_by('numero_casa'), label='Casa visitada', empty_label='Seleccione una casa', widget=forms.Select(attrs={'class': 'form-select'}))
    guardia = forms.ModelChoiceField(queryset=Guardia.objects.order_by('apellido', 'nombre'), label='Guardia que registra', empty_label='Seleccione un guardia', widget=forms.Select(attrs={'class': 'form-select'}))
    persona_autorizante = forms.ChoiceField(
        choices=(),
        required=False,
        label='Persona autorizante',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    autoriza = forms.ChoiceField(
        choices=(('SI', 'Sí'), ('NO', 'No')),
        label='Autoriza',
        initial='NO',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )

    # Inicializa el objeto y configura los valores necesarios para su uso.
    def __init__(self, *args, casa_id=None, **kwargs):
        super().__init__(*args, **kwargs)
        casa_id = casa_id or (self.data.get('vivienda') if self.is_bound else None)
        if casa_id:
            casa = Casa.objects.select_related('id_residente', 'id_propietario').prefetch_related('residentes_secundarios').filter(pk=casa_id).first()
            if casa:
                self.initial['vivienda'] = casa.pk
            personas = []
            if casa:
                residentes = ([casa.id_residente] if casa.id_residente else []) + list(casa.residentes_secundarios.all())
                vistos = set()
                for residente in residentes:
                    if residente.pk in vistos:
                        continue
                    vistos.add(residente.pk)
                    personas.append((f'residente:{residente.pk}', f'{residente.nombre} {residente.apellido} - Tel: {residente.telefono or "Sin teléfono"}'))
                if casa.id_propietario:
                    personas.append((f'propietario:{casa.id_propietario.pk}', f'{casa.id_propietario.nombre} {casa.id_propietario.apellido} - Tel: {casa.id_propietario.telefono or "Sin teléfono"}'))
            self.fields['persona_autorizante'].choices = [('', 'Seleccione una persona')] + personas
        if self.instance and self.instance.pk:
            if self.instance.propietario_autorizador_id:
                self.initial['persona_autorizante'] = f'propietario:{self.instance.propietario_autorizador_id}'
            elif self.instance.residente_secundario_id:
                self.initial['persona_autorizante'] = f'residente:{self.instance.residente_secundario_id}'
            self.initial['autoriza'] = self.instance.autoriza

    # Persiste los datos del formulario y completa las actualizaciones asociadas.
    def save(self, commit=True):
        domicilio = super().save(commit=False)
        domicilio.residente_secundario = None
        domicilio.propietario_autorizador = None
        persona = self.cleaned_data.get('persona_autorizante') or ''
        tipo, _, persona_id = persona.partition(':')
        if tipo == 'residente' and persona_id.isdigit():
            domicilio.residente_secundario_id = int(persona_id)
        elif tipo == 'propietario' and persona_id.isdigit():
            domicilio.propietario_autorizador_id = int(persona_id)
        domicilio.autoriza = self.cleaned_data.get('autoriza') or 'NO'
        if commit:
            domicilio.save()
        return domicilio

    # Agrupa las opciones de configuración del modelo o formulario que contiene.
    class Meta:
        model = Domicilio
        fields = ('nombre', 'apellido', 'telefono_negocio', 'descripcion_negocio', 'vehiculo_tipo', 'vehiculo_placa')
        labels = {'nombre': 'Nombre', 'apellido': 'Apellido', 'telefono_negocio': 'Teléfono del negocio', 'descripcion_negocio': 'Descripción del negocio', 'vehiculo_tipo': 'Tipo de vehículo', 'vehiculo_placa': 'Placa del vehículo'}
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'apellido': forms.TextInput(attrs={'class': 'form-control'}),
            'telefono_negocio': forms.TextInput(attrs={'class': 'form-control'}),
            'descripcion_negocio': forms.TextInput(attrs={'class': 'form-control'}),
            'vehiculo_tipo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Moto, carro...'}),
            'vehiculo_placa': forms.TextInput(attrs={'class': 'form-control'}),
        }


# Define campos y reglas reutilizables para domicilio formulario.
class DomicilioForm(DomicilioIngresoForm):
    # Agrupa las opciones de configuración del modelo o formulario que contiene.
    class Meta(DomicilioIngresoForm.Meta):
        fields = DomicilioIngresoForm.Meta.fields

    # Inicializa el objeto y configura los valores necesarios para su uso.
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields.pop('guardia')
        for campo in self.fields.values():
            campo.disabled = True


# Define campos y reglas reutilizables para paquete ingreso formulario.
class PaqueteIngresoForm(EvidenciaObligatoriaMixin, GuardiaAutomaticoMixin, SoloDigitosMixin, forms.ModelForm):
    ESTADOS_PAQUETE = (('PENDIENTE', 'En portería'), ('ENTREGADO', 'Entregado'), ('DEVUELTO', 'Devuelto'))
    vivienda = forms.ModelChoiceField(queryset=Casa.objects.order_by('numero_casa'), label='Casa destinataria', empty_label='Seleccione una casa', widget=forms.Select(attrs={'class': 'form-select'}))
    guardia = forms.ModelChoiceField(queryset=Guardia.objects.order_by('apellido', 'nombre'), label='Guardia que registra', empty_label='Seleccione un guardia', widget=forms.Select(attrs={'class': 'form-select'}))
    estado_paquete = forms.ChoiceField(choices=ESTADOS_PAQUETE, label='Estado', widget=forms.Select(attrs={'class': 'form-select'}))
    persona_autorizante = forms.ChoiceField(choices=(), required=False, label='Destinatario', widget=forms.Select(attrs={'class': 'form-select'}))
    llamada = forms.ChoiceField(choices=(('CONTESTO', 'Sí contestó'), ('NO_CONTESTO', 'No contestó')), label='Llamada', initial='NO_CONTESTO', widget=forms.Select(attrs={'class': 'form-select'}))
    informacion_adicional = forms.CharField(required=False, label='Nota', widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2}))

    # Inicializa el objeto y configura los valores necesarios para su uso.
    def __init__(self, *args, casa_id=None, estado_actual=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['estado_paquete'].choices = opciones_estado_configuradas(
            'paquete', self.ESTADOS_PAQUETE,
        )
        self.initial['estado_paquete'] = estado_actual or 'PENDIENTE'
        casa_id = casa_id or (self.data.get('vivienda') if self.is_bound else None)
        if casa_id:
            casa = Casa.objects.select_related('id_residente', 'id_propietario').prefetch_related('residentes_secundarios').filter(pk=casa_id).first()
            personas = []
            if casa:
                residentes = ([casa.id_residente] if casa.id_residente else []) + list(casa.residentes_secundarios.all())
                vistos = set()
                for residente in residentes:
                    if residente.pk in vistos:
                        continue
                    vistos.add(residente.pk)
                    personas.append((f'residente:{residente.pk}', f'{residente.nombre} {residente.apellido} - Tel: {residente.telefono or "Sin teléfono"}'))
                if casa.id_propietario:
                    personas.append((f'propietario:{casa.id_propietario.pk}', f'{casa.id_propietario.nombre} {casa.id_propietario.apellido} - Tel: {casa.id_propietario.telefono or "Sin teléfono"}'))
            self.fields['persona_autorizante'].choices = [('', 'Seleccione una persona')] + personas
        if self.instance and self.instance.pk:
            if self.instance.propietario_autorizador_id:
                self.initial['persona_autorizante'] = f'propietario:{self.instance.propietario_autorizador_id}'
            elif self.instance.residente_secundario_id:
                self.initial['persona_autorizante'] = f'residente:{self.instance.residente_secundario_id}'
            self.initial['llamada'] = self.instance.llamada
            self.initial['informacion_adicional'] = self.instance.informacion_adicional

    # Aplica validaciones relacionadas entre los campos y devuelve los datos depurados.
    def clean(self):
        return super().clean()

    # Persiste los datos del formulario y completa las actualizaciones asociadas.
    def save(self, commit=True):
        paquete = super().save(commit=False)
        paquete.residente_secundario = None
        paquete.propietario_autorizador = None
        persona = self.cleaned_data.get('persona_autorizante') or ''
        tipo, _, persona_id = persona.partition(':')
        if tipo == 'residente' and persona_id.isdigit():
            paquete.residente_secundario_id = int(persona_id)
        elif tipo == 'propietario' and persona_id.isdigit():
            paquete.propietario_autorizador_id = int(persona_id)
        paquete.llamada = self.cleaned_data.get('llamada') or 'NO_CONTESTO'
        paquete.informacion_adicional = (self.cleaned_data.get('informacion_adicional') or '').strip() or None
        if commit:
            paquete.save()
        return paquete

    # Agrupa las opciones de configuración del modelo o formulario que contiene.
    class Meta:
        model = Paquete
        fields = ('nombre', 'apellido', 'transportadora', 'telefono_t', 'desc_tipo', 'guia', 'evidencia')
        labels = {'nombre': 'Nombre del remitente', 'apellido': 'Apellido del remitente', 'transportadora': 'Transportadora', 'telefono_t': 'Teléfono', 'desc_tipo': 'Descripción del paquete', 'guia': 'Número de guía', 'evidencia': 'Evidencia'}
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'apellido': forms.TextInput(attrs={'class': 'form-control'}),
            'transportadora': forms.TextInput(attrs={'class': 'form-control'}),
            'telefono_t': forms.TextInput(attrs={'class': 'form-control'}),
            'desc_tipo': forms.TextInput(attrs={'class': 'form-control'}),
            'guia': forms.TextInput(attrs={'class': 'form-control'}),
            'evidencia': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }


# Define campos y reglas reutilizables para paquete formulario.
class PaqueteForm(PaqueteIngresoForm):
    # Agrupa las opciones de configuración del modelo o formulario que contiene.
    class Meta(PaqueteIngresoForm.Meta):
        fields = PaqueteIngresoForm.Meta.fields

    # Inicializa el objeto y configura los valores necesarios para su uso.
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields.pop('vivienda')
        self.fields.pop('guardia')
        for nombre, campo in self.fields.items():
            if nombre != 'estado_paquete':
                campo.disabled = True


# Define campos y reglas reutilizables para novedad formulario.
class NovedadForm(EvidenciaObligatoriaMixin, forms.ModelForm):
    TIPO_NOVEDAD = (
        ('Corte de luz', 'Corte de luz'),
        ('Corte de agua', 'Corte de agua'),
        ('Corte de gas', 'Corte de gas'),
        ('Otros', 'Otros'),
    )
    tipo = forms.ChoiceField(
        choices=TIPO_NOVEDAD,
        label='Tipo de novedad',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    tipo_personalizado = forms.CharField(
        required=False,
        label='Especifique el tipo de novedad',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. Mantenimiento de zonas comunes'}),
    )
    fecha_suceso = forms.DateTimeField(
        required=False,
        label='Fecha del suceso (opcional)',
        input_formats=('%Y-%m-%dT%H:%M',),
        widget=forms.DateTimeInput(format='%Y-%m-%dT%H:%M', attrs={'class': 'form-control', 'type': 'datetime-local'}),
    )

    # Agrupa las opciones de configuración del modelo o formulario que contiene.
    class Meta:
        model = Novedad
        fields = ('titulo', 'tipo', 'tipo_personalizado', 'nota', 'evidencia', 'fecha_suceso')
        labels = {'titulo': 'Título de la novedad', 'tipo': 'Tipo de novedad', 'nota': 'Descripción de la novedad', 'evidencia': 'Foto'}
        widgets = {
            'titulo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. Jornada de mantenimiento'}),
            'nota': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'evidencia': forms.ClearableFileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
        }

    # Inicializa el objeto y configura los valores necesarios para su uso.
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        valid_types = {value for value, _ in self.TIPO_NOVEDAD}
        if self.instance and self.instance.tipo not in valid_types:
            self.initial['tipo'] = 'Otros'
            self.initial['tipo_personalizado'] = self.instance.tipo
        fecha_minima = timezone.localdate()
        if self.instance and self.instance.pk and self.instance.fecha_suceso:
            fecha_minima = timezone.localdate(self.instance.fecha_suceso)
        self.fields['fecha_suceso'].widget.attrs['min'] = f"{fecha_minima.isoformat()}T00:00"

    # Aplica validaciones relacionadas entre los campos y devuelve los datos depurados.
    def clean(self):
        cleaned_data = super().clean()
        tipo = cleaned_data.get('tipo')
        personalizado = (cleaned_data.get('tipo_personalizado') or '').strip()
        if tipo == 'Otros':
            if not personalizado:
                self.add_error('tipo_personalizado', 'Especifique el tipo de novedad.')
            else:
                cleaned_data['tipo'] = personalizado
        return cleaned_data

    # Valida y normaliza el campo fecha suceso antes de aceptar el formulario.
    def clean_fecha_suceso(self):
        fecha_suceso = self.cleaned_data.get('fecha_suceso')
        if not fecha_suceso:
            return timezone.now()
        if timezone.localdate(fecha_suceso) < timezone.localdate():
            fecha_original = timezone.localdate(self.instance.fecha_suceso) if self.instance and self.instance.pk else None
            if fecha_original == timezone.localdate(fecha_suceso):
                return fecha_suceso
            raise forms.ValidationError('La fecha no puede ser anterior a hoy.')
        return fecha_suceso


# Define campos y reglas reutilizables para nota formulario.
class NotaForm(EvidenciaObligatoriaMixin, GuardiaAutomaticoMixin, SoloDigitosMixin, forms.ModelForm):
    # Agrupa las opciones de configuración del modelo o formulario que contiene.
    class Meta:
        model = Notas
        fields = ('nombre', 'apellido', 'telefono', 'nota', 'evidencia', 'id_guardia')
        labels = {'nombre': 'Nombre', 'apellido': 'Apellido', 'telefono': 'Teléfono', 'nota': 'Nota', 'evidencia': 'Evidencia', 'id_guardia': 'Guardia que registra'}
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'apellido': forms.TextInput(attrs={'class': 'form-control'}),
            'telefono': forms.TextInput(attrs={'class': 'form-control'}),
            'nota': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'evidencia': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'id_guardia': forms.Select(attrs={'class': 'form-select'}),
        }

    # Inicializa el objeto y configura los valores necesarios para su uso.
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['telefono'].required = True
        if not (self.instance and self.instance.pk and self.instance.id_guardia_id is None):
            self.fields['id_guardia'].required = True
        self.fields['id_guardia'].queryset = Guardia.objects.order_by('apellido', 'nombre')


# Define campos y reglas reutilizables para pago formulario.
class PagoForm(EvidenciaObligatoriaMixin, forms.ModelForm):
    estado = forms.ChoiceField(
        choices=(('Pagado', 'Pagado'), ('Pendiente', 'Pendiente')),
        label='Estado',
        initial='Pendiente',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )

    # Agrupa las opciones de configuración del modelo o formulario que contiene.
    class Meta:
        model = Pago
        fields = ('id_casa', 'valor', 'fecha', 'estado', 'evidencia')
        labels = {'id_casa': 'Casa', 'valor': 'Valor pagado', 'fecha': 'Fecha del pago', 'estado': 'Estado', 'evidencia': 'Comprobante'}
        widgets = {
            'id_casa': forms.Select(attrs={'class': 'form-select'}),
            'valor': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'step': '0.01'}),
            'fecha': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'evidencia': forms.ClearableFileInput(attrs={'class': 'form-control', 'accept': 'image/*,.pdf'}),
        }

    # Inicializa el objeto y configura los valores necesarios para su uso.
    def __init__(self, *args, propietario=False, solo_estado=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['estado'].choices = opciones_estado_configuradas(
            'pago', self.fields['estado'].choices,
        )
        casas_con_propietario = Casa.objects.filter(id_propietario__isnull=False)
        if self.instance and self.instance.pk:
            casas_con_propietario = casas_con_propietario | Casa.objects.filter(pk=self.instance.id_casa_id)
        self.fields['id_casa'].queryset = casas_con_propietario.order_by('numero_casa')
        if propietario:
            self.fields['estado'].disabled = True
            if not self.instance.pk:
                self.initial['estado'] = 'Pendiente'
        if solo_estado:
            for field_name in tuple(self.fields):
                if field_name != 'estado':
                    self.fields.pop(field_name)
        if not self.instance.pk:
            self.fields['estado'].initial = 'Pendiente'
        else:
            for nombre, campo in self.fields.items():
                if nombre not in ('fecha', 'evidencia', 'estado', 'valor'):
                    campo.disabled = True


# Define campos y reglas reutilizables para configuración cartera formulario.
class ConfiguracionCarteraForm(forms.ModelForm):
    # Inicializa el objeto y configura los valores necesarios para su uso.
    def __init__(self, *args, estados_casa=None, **kwargs):
        super().__init__(*args, **kwargs)
        # Conserva los estados ya configurados y agrega los estados de casa existentes aunque no estén en la lista base.
        estados_guardados = self.instance.estados_visualizacion or {}
        estados_casa = set(estados_casa or ())
        estados_casa.update((estados_guardados.get('casa') or {}).keys())

        self.estado_secciones = []
        self.estado_campos = []
        for modulo, definicion in ESTADOS_CONFIGURABLES.items():
            opciones = [(estado, nombre, color) for estado, nombre, color in definicion['estados']]
            if modulo == 'casa':
                conocidos = {estado for estado, _, _ in opciones}
                opciones.extend(
                    (estado, estado, '#6c757d')
                    for estado in sorted(estados_casa - conocidos)
                )

            filas = []
            for indice, (estado, nombre_por_defecto, color_por_defecto) in enumerate(opciones):
                guardado = (estados_guardados.get(modulo) or {}).get(estado, {})
                iniciales = {
                    'nombre': guardado.get('nombre') or nombre_por_defecto,
                    'color': guardado.get('color') or color_por_defecto,
                }
                iniciales['color_texto'] = color_texto(iniciales['color'])
                prefijo = f'estado_{modulo}_{indice}'
                nombres = {
                    campo: f'{prefijo}_{campo}'
                    for campo in ('nombre', 'color')
                }
                self.fields[nombres['nombre']] = forms.CharField(
                    required=False,
                    max_length=60,
                    initial=iniciales['nombre'],
                    label='Nombre',
                    validators=[RegexValidator(
                        regex=r'^[^\W\d_]+(?: +[^\W\d_]+)*$',
                        message='Use solo letras y espacios, sin números ni caracteres especiales.',
                    )],
                    widget=forms.TextInput(attrs={
                        'class': 'form-control',
                        'pattern': r'[\p{L} ]+',
                        'oninput': "this.value = this.value.replace(/[^\\p{L} ]/gu, '')",
                        'title': 'Use solo letras y espacios.',
                    }),
                )
                self.fields[nombres['color']] = forms.CharField(
                    required=False,
                    initial=iniciales['color'],
                    label='Color',
                    validators=[RegexValidator(
                        regex=r'^#[0-9a-fA-F]{6}$',
                        message='Seleccione un color válido.',
                    )],
                    widget=forms.TextInput(attrs={
                        'class': 'form-control form-control-color',
                        'type': 'color',
                        'title': 'Seleccione el color del estado',
                    }),
                )
                fila = {
                    'estado': estado,
                    'nombre': self[nombres['nombre']],
                    'color': self[nombres['color']],
                    'iniciales': iniciales,
                    'nombres': nombres,
                }
                filas.append(fila)
                self.estado_campos.append((modulo, estado, fila))
            self.estado_secciones.append({
                'modulo': modulo,
                'label': definicion['label'],
                'filas': filas,
            })

    # Agrupa las opciones de configuración del modelo o formulario que contiene.
    class Meta:
        model = ConfiguracionCartera
        fields = ('porcentaje_mora', 'monto_aumento_mensual', 'dia_vencimiento', 'frecuencia_mora', 'tiempo_domiciliario_minutos')
        labels = {
            'porcentaje_mora': 'Interés de mora (%)',
            'monto_aumento_mensual': 'Administración mensual',
            'dia_vencimiento': 'Día límite de pago de cada mes',
            'frecuencia_mora': 'Frecuencia de aplicación',
            'tiempo_domiciliario_minutos': 'Tiempo máximo del domiciliario (minutos)',
        }
        widgets = {
            'porcentaje_mora': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0',
                'max': '100',
                'step': '0.01',
            }),
            'monto_aumento_mensual': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0',
                'step': '0.01',
            }),
            'dia_vencimiento': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1',
                'max': '31',
                'step': '1',
            }),
            'frecuencia_mora': forms.Select(attrs={'class': 'form-select'}),
            'tiempo_domiciliario_minutos': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1',
                'step': '1',
            }),
        }

    # Valida y normaliza el campo porcentaje mora antes de aceptar el formulario.
    def clean_porcentaje_mora(self):
        value = self.cleaned_data['porcentaje_mora']
        if value < 0 or value > 100:
            raise forms.ValidationError('El porcentaje debe estar entre 0 y 100.')
        return value

    # Valida y normaliza el campo monto aumento mensual antes de aceptar el formulario.
    def clean_monto_aumento_mensual(self):
        value = self.cleaned_data['monto_aumento_mensual']
        if value < 0:
            raise forms.ValidationError('El monto no puede ser negativo.')
        return value

    # Valida y normaliza el campo dia vencimiento antes de aceptar el formulario.
    def clean_dia_vencimiento(self):
        value = self.cleaned_data['dia_vencimiento']
        if value < 1 or value > 31:
            raise forms.ValidationError('El día debe estar entre 1 y 31.')
        return value

    # Valida y normaliza el campo tiempo domiciliario minutos antes de aceptar el formulario.
    def clean_tiempo_domiciliario_minutos(self):
        value = self.cleaned_data['tiempo_domiciliario_minutos']
        if value < 1:
            raise forms.ValidationError('El tiempo debe ser de al menos 1 minuto.')
        return value

    # Persiste los datos del formulario y completa las actualizaciones asociadas.
    def save(self, commit=True):
        configuracion = super().save(commit=False)
        # Actualiza solo las etiquetas y colores de la estructura existente para no descartar otros módulos guardados.
        estados_guardados = {
            modulo: dict(estados)
            for modulo, estados in (configuracion.estados_visualizacion or {}).items()
            if isinstance(estados, dict)
        }
        for modulo, estado, fila in self.estado_campos:
            estados_guardados.setdefault(modulo, {})
            estados_guardados[modulo][estado] = {
                campo: self.cleaned_data.get(nombre_campo) or fila['iniciales'][campo]
                for campo, nombre_campo in fila['nombres'].items()
            }
        configuracion.estados_visualizacion = estados_guardados
        if commit:
            configuracion.save()
            self.save_m2m()
        return configuracion


# Define campos y reglas reutilizables para configuración copias seguridad formulario.
class ConfiguracionCopiasSeguridadForm(forms.ModelForm):
    # Agrupa las opciones de configuración del modelo o formulario que contiene.
    class Meta:
        model = ConfiguracionCopiasSeguridad
        fields = ('intervalo', 'unidad_intervalo', 'automaticas_activas', 'ruta_destino')
        labels = {
            'intervalo': 'Frecuencia',
            'unidad_intervalo': 'Unidad',
            'automaticas_activas': 'Activar copias automáticas',
            'ruta_destino': 'Carpeta donde guardar las copias',
        }
        widgets = {
            'intervalo': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'max': '365', 'step': '1'}),
            'unidad_intervalo': forms.Select(attrs={'class': 'form-select'}),
            'automaticas_activas': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'ruta_destino': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': r'C:\Copias\Piemonte',
                'autocomplete': 'off',
            }),
        }

    # Valida y normaliza el campo intervalo antes de aceptar el formulario.
    def clean_intervalo(self):
        value = self.cleaned_data['intervalo']
        if value < 1 or value > 365:
            raise forms.ValidationError('La frecuencia debe estar entre 1 y 365 unidades.')
        return value

    # Valida y normaliza el campo ruta destino antes de aceptar el formulario.
    def clean_ruta_destino(self):
        value = self.cleaned_data['ruta_destino'].strip()
        if not value:
            return value
        ruta = Path(value).expanduser()
        if not ruta.is_absolute():
            raise forms.ValidationError('Ingresa una ruta absoluta de la computadora donde se ejecuta el sistema.')
        try:
            ruta_resuelta = ruta.resolve()
            proyecto = Path(settings.BASE_DIR).resolve()
            ruta_resuelta.relative_to(proyecto)
        except ValueError:
            return str(ruta_resuelta)
        raise forms.ValidationError('La carpeta de copias debe estar fuera del proyecto para evitar incluir las copias dentro de sí mismas.')


# Define campos y reglas reutilizables para casa edicion formulario.
class CasaEdicionForm(CasaForm):
    # Agrupa las opciones de configuración del modelo o formulario que contiene.
    class Meta(CasaForm.Meta):
        fields = ('numero_casa', 'cantidad_personas', 'cantidad_residentes', 'estado', 'estado_otro', 'cartera', 'id_residente')

    # Inicializa el objeto y configura los valores necesarios para su uso.
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields['numero_casa'].disabled = True
            self.fields['numero_casa'].widget.attrs['readonly'] = True


# Define campos y reglas reutilizables para guardia edicion formulario.
class GuardiaEdicionForm(CedulaUnicaMixin, SoloDigitosMixin, forms.ModelForm):
    activo = forms.BooleanField(label='Cuenta activa', required=False, initial=True)
    turno = forms.ChoiceField(
        choices=TURNOS_GUARDIA,
        label='Turno',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    password = forms.CharField(
        label='Nueva contraseña (opcional)',
        required=False,
        validators=VALIDADORES_CONTRASENA,
        help_text=REQUISITOS_CONTRASENA,
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
    )
    password_confirmacion = forms.CharField(label='Confirmar nueva contraseña', required=False, widget=forms.PasswordInput(attrs={'class': 'form-control'}))

    # Agrupa las opciones de configuración del modelo o formulario que contiene.
    class Meta:
        model = Guardia
        fields = ('cedula', 'nombre', 'apellido', 'telefono', 'turno', 'activo', 'password', 'password_confirmacion')
        labels = GuardiaForm.Meta.labels
        widgets = GuardiaForm.Meta.widgets

    # Aplica validaciones relacionadas entre los campos y devuelve los datos depurados.
    def clean(self):
        cleaned_data = super().clean()
        if self.instance and self.instance.pk and not self.instance.usuario and not cleaned_data.get('password'):
            self.add_error('password', 'Debe definir una contraseña para crear la cuenta de este guardia.')
        if cleaned_data.get('password') and cleaned_data.get('password') != cleaned_data.get('password_confirmacion'):
            self.add_error('password_confirmacion', 'Las contraseñas no coinciden.')
        return cleaned_data

    # Inicializa el objeto y configura los valores necesarios para su uso.
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        turnos_actuales = {valor for valor, _ in TURNOS_GUARDIA}
        if self.instance and self.instance.turno and self.instance.turno not in turnos_actuales:
            self.fields['turno'].choices = TURNOS_GUARDIA + ((self.instance.turno, self.instance.turno),)
        if self.instance and self.instance.usuario:
            activo = self.instance.usuario.is_active
            self.fields['activo'].initial = activo
            self.initial['activo'] = activo


# Define campos y reglas reutilizables para usuario formulario.
class UsuarioForm(SoloTextoMixin, forms.Form):
    CAMPOS_TEXTO = {'first_name', 'last_name'}
    ROLES = (
        ('administrador', 'Administrador'),
        ('guardia', 'Guardia'),
        ('propietario', 'Propietario'),
    )
    username = forms.CharField(
        label='Usuario de acceso',
        max_length=150,
        widget=forms.TextInput(attrs={'class': 'form-control', 'autocomplete': 'username'}),
    )
    first_name = forms.CharField(
        label='Nombre',
        required=False,
        max_length=150,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    last_name = forms.CharField(
        label='Apellido',
        required=False,
        max_length=150,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    rol = forms.ChoiceField(
        label='Tipo de cuenta',
        choices=ROLES,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    cedula = forms.IntegerField(
        label='Cédula del guardia',
        required=False,
        min_value=1,
        max_value=MAX_CEDULA,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': MAX_CEDULA}),
    )
    telefono = forms.CharField(label='Teléfono del guardia', required=False, max_length=20, widget=forms.TextInput(attrs={'class': 'form-control'}))
    turno = forms.ChoiceField(label='Turno del guardia', required=False, choices=TURNOS_GUARDIA, widget=forms.Select(attrs={'class': 'form-select'}))
    propietario_existente = forms.ModelChoiceField(label='Propietario registrado', required=False, queryset=Propietario.objects.none(), widget=forms.Select(attrs={'class': 'form-select'}))
    correo_contacto = forms.EmailField(label='Correo electrónico', required=False, widget=forms.EmailInput(attrs={'class': 'form-control', 'autocomplete': 'email'}))
    telefono_contacto = forms.CharField(label='Número telefónico', required=False, max_length=20, widget=forms.TextInput(attrs={'class': 'form-control', 'inputmode': 'numeric', 'pattern': '[0-9]*'}))
    casas_propietario = forms.ModelMultipleChoiceField(
        label='Casas asignadas',
        required=False,
        queryset=Casa.objects.none(),
        widget=forms.SelectMultiple(attrs={'class': 'form-select', 'size': 5}),
    )
    password = forms.CharField(
        label='Contraseña',
        validators=VALIDADORES_CONTRASENA,
        help_text=REQUISITOS_CONTRASENA,
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'autocomplete': 'new-password'}),
    )
    password_confirmacion = forms.CharField(
        label='Confirmar contraseña',
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'autocomplete': 'new-password'}),
    )
    activo = forms.BooleanField(label='Cuenta activa', required=False, initial=True)

    # Inicializa el objeto y configura los valores necesarios para su uso.
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['casas_propietario'].queryset = Casa.objects.filter(id_propietario__isnull=True).order_by('numero_casa')
        self.fields['propietario_existente'].queryset = Propietario.objects.filter(
            usuario__isnull=True,
            casas__isnull=True,
        ).distinct().order_by('apellido', 'nombre')

    # Valida y normaliza el campo username antes de aceptar el formulario.
    def clean_username(self):
        username = self.cleaned_data['username'].strip()
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError('Ese usuario ya existe.')
        return username

    # Aplica validaciones relacionadas entre los campos y devuelve los datos depurados.
    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('password') != cleaned_data.get('password_confirmacion'):
            self.add_error('password_confirmacion', 'Las contraseñas no coinciden.')
        if cleaned_data.get('rol') == 'guardia':
            for field in ('cedula', 'first_name', 'last_name', 'turno'):
                if not cleaned_data.get(field):
                    self.add_error(field, 'Este campo es obligatorio para una cuenta de guardia.')
            if cleaned_data.get('cedula') and Guardia.objects.filter(cedula=cleaned_data['cedula']).exists():
                self.add_error('cedula', 'Ya existe un guardia con esta cédula.')
        elif cleaned_data.get('rol') == 'propietario':
            if not cleaned_data.get('propietario_existente'):
                self.add_error('propietario_existente', 'Seleccione un propietario registrado.')
            if not cleaned_data.get('casas_propietario'):
                self.add_error('casas_propietario', 'Seleccione al menos una casa disponible.')
            cleaned_data['cedula'] = None
            cleaned_data['telefono'] = ''
            cleaned_data['turno'] = ''
        else:
            cleaned_data['cedula'] = None
            cleaned_data['telefono'] = ''
            cleaned_data['turno'] = ''
            cleaned_data['propietario_existente'] = None
            cleaned_data['casas_propietario'] = Casa.objects.none()
        correo_contacto = (cleaned_data.get('correo_contacto') or '').strip()
        if cleaned_data.get('rol') in ('administrador', 'guardia') and not correo_contacto:
            self.add_error('correo_contacto', 'El correo es obligatorio.')
        elif correo_contacto:
            cleaned_data['correo_contacto'] = correo_contacto.lower()
        if cleaned_data.get('telefono_contacto') and (
            not cleaned_data['telefono_contacto'].isascii()
            or not cleaned_data['telefono_contacto'].isdigit()
        ):
            self.add_error('telefono_contacto', 'El teléfono solo puede contener números.')
        return cleaned_data


# Define campos y reglas reutilizables para propietario formulario.
class PropietarioForm(CedulaUnicaMixin, SoloDigitosMixin, forms.ModelForm):
    ROLES_PROPIETARIO = (
        ('Administrador', 'Administrador'),
        ('Propietario', 'Propietario'),
        ('Residente', 'Residente'),
        ('Inmobiliaria', 'Inmobiliaria'),
        ('Otros', 'Otros'),
    )

    rol = forms.ChoiceField(
        choices=ROLES_PROPIETARIO,
        label='Rol',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    rol_otro = forms.CharField(
        required=False,
        label='Especifique otro rol',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Escriba el rol'}),
    )

    # Agrupa las opciones de configuración del modelo o formulario que contiene.
    class Meta:
        model = Propietario
        fields = ('cedula', 'nombre', 'apellido', 'telefono', 'correo', 'rol', 'rol_otro')
        labels = {
            'cedula': 'Cédula',
            'nombre': 'Nombre',
            'apellido': 'Apellido',
            'telefono': 'Teléfono',
            'correo': 'Correo electrónico',
            'rol': 'Rol',
        }
        widgets = {
            'cedula': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': MAX_CEDULA}),
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'apellido': forms.TextInput(attrs={'class': 'form-control'}),
            'telefono': forms.TextInput(attrs={'class': 'form-control'}),
            'correo': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'nombre@correo.com'}),
        }

    # Inicializa el objeto y configura los valores necesarios para su uso.
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        rol_enviado = self.data.get('rol') or self.initial.get('rol') or (self.instance.rol if self.instance and self.instance.pk else '')
        if rol_enviado == 'Residente':
            self.fields['correo'].required = False
        roles = {value for value, _ in self.ROLES_PROPIETARIO}
        if self.instance and self.instance.pk and self.instance.rol not in roles:
            self.fields['rol'].initial = 'Otros'
            self.fields['rol_otro'].initial = self.instance.rol

    # Valida y normaliza el campo correo antes de aceptar el formulario.
    def clean_correo(self):
        correo = (self.cleaned_data.get('correo') or '').strip()
        rol = self.cleaned_data.get('rol') or self.data.get('rol')
        if rol == 'Residente' and not correo:
            return ''
        return correo.lower()

    # Valida y normaliza el campo cédula antes de aceptar el formulario.
    def clean_cedula(self):
        cedula = super().clean_cedula()
        if cedula is None:
            return cedula
        if cedula <= 0:
            raise forms.ValidationError('La cédula debe ser mayor que cero.')
        return cedula

    # Aplica validaciones relacionadas entre los campos y devuelve los datos depurados.
    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('rol') == 'Otros':
            rol_otro = (cleaned_data.get('rol_otro') or '').strip()
            if not rol_otro:
                self.add_error('rol_otro', 'Especifique el rol.')
            else:
                cleaned_data['rol'] = rol_otro
        return cleaned_data
