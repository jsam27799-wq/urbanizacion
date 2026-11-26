# Módulo: Define formularios, presentación de campos y reglas de validación de los datos recibidos.
from django import forms
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.models import User
from django.core.validators import MinLengthValidator, RegexValidator
import phonenumbers
from .models import PerfilUsuario


PHONE_COUNTRY_PRIORITY = (
    'CO', 'US', 'MX', 'CA', 'AR', 'BR', 'CL', 'EC', 'PE', 'ES',
    'GB', 'FR', 'DE', 'IT', 'PT',
)
PHONE_CALLING_CODES = {
    region: calling_code
    for calling_code, regions in phonenumbers.COUNTRY_CODE_TO_REGION_CODE.items()
    for region in regions
    if region != '001'
}
PHONE_COUNTRY_REGIONS = (
    *(region for region in PHONE_COUNTRY_PRIORITY if region in PHONE_CALLING_CODES),
    *sorted(set(PHONE_CALLING_CODES) - set(PHONE_COUNTRY_PRIORITY)),
)
PHONE_COUNTRY_CHOICES = tuple(
    (region, f'{region} (+{PHONE_CALLING_CODES[region]})')
    for region in PHONE_COUNTRY_REGIONS
)


def formatear_telefono_internacional(telefono):
    telefono = (telefono or '').strip()
    if not telefono:
        return ''

    try:
        numero = phonenumbers.parse(telefono, None if telefono.startswith('+') else 'CO')
    except phonenumbers.NumberParseException:
        return telefono

    if not phonenumbers.is_possible_number(numero) or not phonenumbers.is_valid_number(numero):
        return telefono

    region = phonenumbers.region_code_for_number(numero)
    nacional = phonenumbers.national_significant_number(numero)
    if region == 'CO' and len(nacional) == 10:
        return f'+{numero.country_code} {nacional[:3]}-{nacional[3:]}'
    return phonenumbers.format_number(numero, phonenumbers.PhoneNumberFormat.INTERNATIONAL)


# Define campos y reglas reutilizables para perfil formulario.
class PerfilForm(forms.ModelForm):
    codigo_pais = forms.ChoiceField(
        label='País / código',
        choices=PHONE_COUNTRY_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select', 'autocomplete': 'country'}),
    )
    telefono = forms.CharField(
        label='Número telefónico',
        required=False,
        max_length=30,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'inputmode': 'tel',
            'autocomplete': 'tel-national',
            'placeholder': 'Ej. 323-6669030',
        }),
    )

    # Agrupa las opciones de configuración del modelo o formulario que contiene.
    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'email')
        labels = {
            'first_name': 'Nombre',
            'last_name': 'Apellido',
            'email': 'Correo electrónico',
        }
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'autocomplete': 'email'}),
        }

    # Inicializa el objeto y configura los valores necesarios para su uso.
    def __init__(self, *args, perfil=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['email'].required = True
        self.perfil = perfil or PerfilUsuario.objects.filter(usuario=self.instance).first()
        self.initial['codigo_pais'] = 'CO'
        self.initial['telefono'] = self.perfil.telefono if self.perfil else ''
        if self.perfil and self.perfil.telefono:
            telefono_guardado = self.perfil.telefono.strip()
            try:
                numero = phonenumbers.parse(
                    telefono_guardado,
                    None if telefono_guardado.startswith('+') else 'CO',
                )
            except phonenumbers.NumberParseException:
                pass
            else:
                region = phonenumbers.region_code_for_number(numero)
                if region in PHONE_CALLING_CODES and phonenumbers.is_possible_number(numero):
                    self.initial['codigo_pais'] = region
                    nacional = phonenumbers.national_significant_number(numero)
                    self.initial['telefono'] = (
                        f'{nacional[:3]}-{nacional[3:]}'
                        if region == 'CO' and len(nacional) == 10
                        else phonenumbers.format_number(numero, phonenumbers.PhoneNumberFormat.NATIONAL)
                    )

    # Persiste los datos del formulario y completa las actualizaciones asociadas.
    def save(self, commit=True):
        usuario = super().save(commit=commit)
        if commit:
            PerfilUsuario.objects.update_or_create(usuario=usuario, defaults={'telefono': self.cleaned_data.get('telefono', '').strip()})
        return usuario

    # Valida y normaliza el campo telefono antes de aceptar el formulario.
    def clean_telefono(self):
        telefono = (self.cleaned_data.get('telefono') or '').strip()
        caracteres_permitidos = set('0123456789+ -().')
        if telefono and (
            not telefono.isascii()
            or not any(caracter.isdigit() for caracter in telefono)
            or any(caracter not in caracteres_permitidos for caracter in telefono)
        ):
            raise forms.ValidationError('Ingresa dígitos y, si lo necesitas, el prefijo +, espacios, paréntesis, puntos o guiones.')
        return telefono

    def clean(self):
        cleaned_data = super().clean()
        telefono = cleaned_data.get('telefono')
        if not telefono:
            return cleaned_data

        region = cleaned_data.get('codigo_pais') or 'CO'
        cleaned_data['codigo_pais'] = region
        try:
            numero = phonenumbers.parse(telefono, region)
        except phonenumbers.NumberParseException:
            self.add_error('telefono', 'No se pudo interpretar el número para el país seleccionado.')
            return cleaned_data

        if not phonenumbers.is_possible_number(numero):
            self.add_error('telefono', 'La longitud del número no es válida para el país seleccionado.')
        elif not phonenumbers.is_valid_number_for_region(numero, region):
            self.add_error('telefono', 'El número no es válido para el país seleccionado.')
        else:
            cleaned_data['telefono'] = phonenumbers.format_number(
                numero,
                phonenumbers.PhoneNumberFormat.E164,
            )
        return cleaned_data

    # Valida y normaliza el campo first name antes de aceptar el formulario.
    def clean_first_name(self):
        return self._limpiar_nombre('first_name')

    # Valida y normaliza el campo last name antes de aceptar el formulario.
    def clean_last_name(self):
        return self._limpiar_nombre('last_name')

    # Valida y normaliza el campo email antes de aceptar el formulario.
    def clean_email(self):
        return (self.cleaned_data.get('email') or '').strip().lower()

    # Organiza el flujo de limpiar nombre dentro de este módulo.
    def _limpiar_nombre(self, campo):
        valor = (self.cleaned_data.get(campo) or '').strip()
        if not valor or not all(caracter.isalpha() or caracter.isspace() for caracter in valor):
            raise forms.ValidationError('Este campo solo puede contener letras y espacios.')
        return valor


# Define campos y reglas reutilizables para perfil password formulario.
class PerfilPasswordForm(PasswordChangeForm):
    new_password1 = forms.CharField(
        label='Nueva contraseña',
        # Las reglas complementan la comparación de contraseñas de Django con longitud y diversidad de caracteres.
        validators=[
            MinLengthValidator(8, 'La contraseña debe tener al menos 8 caracteres.'),
            RegexValidator(r'(?=.*[A-Z])', 'La contraseña debe incluir al menos una mayúscula.'),
            RegexValidator(r'(?=.*[^A-Za-z0-9])', 'La contraseña debe incluir al menos un carácter especial.'),
        ],
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'autocomplete': 'new-password'}),
    )
    new_password2 = forms.CharField(
        label='Confirmar nueva contraseña',
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'autocomplete': 'new-password'}),
    )
