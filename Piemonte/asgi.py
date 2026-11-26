"""
ASGI config for Piemonte project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/asgi/
"""
# Módulo: Expone la aplicación Django para servidores compatibles con ASGI.

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Piemonte.settings')

application = get_asgi_application()
