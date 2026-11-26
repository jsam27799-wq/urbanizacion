# Módulo: Declara la configuración de la aplicación Django.
from django.apps import AppConfig


# Identifica la aplicación transversal de usuarios y páginas públicas ante Django.
class CoreConfig(AppConfig):
    name = 'core'
