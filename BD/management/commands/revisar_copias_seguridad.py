# Módulo: Implementa un comando de gestión para operaciones administrativas del proyecto.
import sqlite3

from django.core.management.base import BaseCommand, CommandError

from BD.copias_seguridad import revisar_copia_automatica


# Implementa la interfaz de línea de comandos para la operación administrativa de este módulo.
class Command(BaseCommand):
    help = 'Crea las copias automáticas del proyecto y la información cuando se cumple la frecuencia configurada.'

    # Ejecuta la revisión programada y comunica el resultado por la salida estándar del comando.
    def handle(self, *args, **options):
        # Convierte fallos esperables del respaldo en errores legibles para el sistema de comandos de Django.
        try:
            copias, creadas = revisar_copia_automatica()
        except (OSError, RuntimeError, ValueError, sqlite3.Error) as error:
            raise CommandError(f'No se pudo completar la copia automática: {error}') from error

        if copias is None:
            # La programación aún no requiere una ejecución; el comando termina sin crear un archivo.
            self.stdout.write('No hay una copia automática pendiente.')
        elif any(creadas):
            nombres = ' y '.join(copia.archivo for copia in copias)
            self.stdout.write(self.style.SUCCESS(f'Copias automáticas creadas o actualizadas: {nombres}'))
        else:
            nombres = ' y '.join(copia.archivo for copia in copias)
            self.stdout.write(f'El contenido ya estaba respaldado en {nombres}; no se creó un duplicado.')
