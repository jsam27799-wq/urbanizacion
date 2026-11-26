# Módulo: Define las entidades de persistencia y sus relaciones en la base de datos.
from django.db import models
from django.conf import settings


# Representa perfil usuario y define sus datos y relaciones persistentes.
class PerfilUsuario(models.Model):
	usuario = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='perfil_contacto')
	telefono = models.CharField(max_length=20, blank=True)

	# Construye la representación textual legible del objeto.
def __str__(self):
		return f'Perfil de {self.usuario.username}'
