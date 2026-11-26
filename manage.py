#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
# Módulo: Punto de entrada para ejecutar los comandos administrativos de Django.
import os
import sys


# Organiza el flujo de main dentro de este módulo.
def main():
    """Run administrative tasks."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Piemonte.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
