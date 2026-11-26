# Módulo: Declara la configuración de la aplicación Django.
from django.apps import AppConfig


# Identifica la aplicación de datos para que Django la registre con su configuración.
class BdConfig(AppConfig):
    name = 'BD'
