# Módulo: Gestiona la creación, ubicación y revisión de copias de seguridad.
import hashlib
import json
import os
import shutil
import sqlite3
import stat
import tempfile
import zipfile
from contextlib import closing
from datetime import date, datetime, timedelta, timezone as datetime_timezone
from pathlib import Path
from uuid import uuid4

from django.apps import apps
from django.conf import settings
from django.core import serializers
from django.core.management import call_command
from django.core.serializers.base import DeserializationError
from django.db import connection, IntegrityError, transaction
from django.utils import timezone

from .models import CopiaSeguridad, ConfiguracionCopiasSeguridad

MAX_COPIAS_POR_ALCANCE = 4
MAX_TAMANO_COPIA_INFORMACION = 1024 * 1024 * 1024
MAX_TAMANO_COPIA_PROYECTO = 2 * 1024 * 1024 * 1024
MAX_TAMANO_EXTRAIDO_PROYECTO = 8 * 1024 * 1024 * 1024
FORMATO_COPIA_MYSQL = 'piemonte-django-fixture'
VERSION_COPIA_MYSQL = 1
MODELOS_EXCLUIDOS_COPIA_MYSQL = (
    'admin.LogEntry',
    'auth.Permission',
    'contenttypes.ContentType',
    'sessions.Session',
    'BD.CopiaSeguridad',
    'BD.ConfiguracionCopiasSeguridad',
)
TABLAS_ADMINISTRACION_COPIAS = {
    'copia_seguridad',
    'configuracion_copias_seguridad',
    'django_migrations',
    'django_session',
    'django_admin_log',
}


class CopiaInformacionIdentica(ValueError):
    pass


CAMPO_FECHA_VERSION = (
    'updated_at',
    'actualizado_en',
    'modificado_en',
    'fecha_actualizacion',
    'fecha_modificacion',
    'updated_on',
    'modified_at',
    'fecha_creacion',
    'creado_en',
    'fecha_salida',
    'ultima_mora_calculada',
    'fecha',
)


# Realiza la tarea de directorio copias y entrega el resultado al flujo que la invoca.
def directorio_copias(configuracion=None):
    if configuracion is None:
        configuracion = ConfiguracionCopiasSeguridad.objects.filter(pk=1).first()
    if configuracion and configuracion.ruta_destino.strip():
        ruta = os.path.expandvars(os.path.expanduser(configuracion.ruta_destino.strip()))
        return Path(ruta).resolve()
    return Path(settings.BASE_DIR).parent / 'copia de seguridad Piemonte'


# Realiza la tarea de ruta archivo copia y entrega el resultado al flujo que la invoca.
def ruta_archivo_copia(copia):
    if copia.ruta_archivo:
        return Path(copia.ruta_archivo).resolve()
    carpeta_predeterminada = Path(settings.BASE_DIR).parent / 'copia de seguridad Piemonte'
    return (carpeta_predeterminada / copia.archivo).resolve()


# Realiza la tarea de intervalo configurado y entrega el resultado al flujo que la invoca.
def intervalo_configurado(configuracion):
    unidades = {
        'minutos': 'minutes',
        'horas': 'hours',
        'dias': 'days',
    }
    unidad = unidades.get(configuracion.unidad_intervalo)
    if unidad is None:
        raise ValueError('La unidad de frecuencia de copias no es válida.')
    return timedelta(**{unidad: configuracion.intervalo})


# Realiza la tarea de hash archivos y entrega el resultado al flujo que la invoca.
def _hash_archivos(archivos):
    # La huella incluye las rutas y el contenido, separados por bytes nulos para evitar ambigüedades entre archivos.
    huella = hashlib.sha256()
    for ruta, nombre_archivo in archivos:
        huella.update(ruta.encode('utf-8'))
        huella.update(b'\0')
        with nombre_archivo.open('rb') as archivo:
            for bloque in iter(lambda: archivo.read(1024 * 1024), b''):
                huella.update(bloque)
        huella.update(b'\0')
    return huella.hexdigest()


# Devuelve las etiquetas de modelos de aplicación incluidos en las copias MySQL.
def _modelos_fixture_mysql():
    excluidos = {etiqueta.casefold() for etiqueta in MODELOS_EXCLUIDOS_COPIA_MYSQL}
    return sorted(
        modelo._meta.label_lower
        for modelo in apps.get_models()
        if modelo._meta.managed
        and not modelo._meta.proxy
        and modelo._meta.label_lower.casefold() not in excluidos
    )


# Lee de forma incremental los objetos de una lista JSON producida por dumpdata.
def _iterar_lista_json(archivo):
    decodificador = json.JSONDecoder()
    buffer = ''
    posicion = 0
    iniciada = False
    separador_requerido = False
    coma_recien_leida = False
    fin_archivo = False

    while True:
        if posicion >= len(buffer) and not fin_archivo:
            buffer = archivo.read(64 * 1024)
            posicion = 0
            fin_archivo = not buffer
        if posicion >= len(buffer):
            if fin_archivo:
                raise ValueError('El archivo JSON terminó antes de cerrar la lista de registros.')
            continue

        if not iniciada:
            while posicion < len(buffer) and buffer[posicion].isspace():
                posicion += 1
            if posicion >= len(buffer):
                continue
            if buffer[posicion] != '[':
                raise ValueError('La exportación de Django no contiene una lista JSON.')
            posicion += 1
            iniciada = True
            continue

        while posicion < len(buffer) and buffer[posicion].isspace():
            posicion += 1
        if posicion >= len(buffer):
            continue

        if separador_requerido:
            if buffer[posicion] == ',':
                posicion += 1
                separador_requerido = False
                coma_recien_leida = True
                continue
            if buffer[posicion] == ']':
                if coma_recien_leida:
                    raise ValueError('La lista JSON de Django termina con un separador inválido.')
                restante = buffer[posicion + 1:] + archivo.read()
                if restante.strip():
                    raise ValueError('La exportación de Django contiene datos después de la lista JSON.')
                return
            raise ValueError('La lista JSON de Django contiene un separador inválido.')

        if buffer[posicion] == ']':
            if coma_recien_leida:
                raise ValueError('La lista JSON de Django termina con un separador inválido.')
            restante = buffer[posicion + 1:] + archivo.read()
            if restante.strip():
                raise ValueError('La exportación de Django contiene datos después de la lista JSON.')
            return

        try:
            registro, siguiente = decodificador.raw_decode(buffer, posicion)
        except json.JSONDecodeError:
            resto = buffer[posicion:]
            bloque = archivo.read(64 * 1024)
            if not bloque:
                fin_archivo = True
                raise
            buffer = resto + bloque
            posicion = 0
            continue
        if not isinstance(registro, dict):
            raise ValueError('La lista JSON contiene un registro con formato no válido.')
        yield registro
        posicion = siguiente
        separador_requerido = True
        coma_recien_leida = False


# Exporta los datos MySQL como registros Django en JSON Lines, con cabecera de formato y esquema.
def _exportar_fixture_mysql(ruta_destino):
    ruta_destino = Path(ruta_destino)
    ruta_destino.parent.mkdir(parents=True, exist_ok=True)
    descriptor, ruta_temporal_dump = tempfile.mkstemp(
        prefix='.piemonte_dump_',
        suffix='.json',
        dir=ruta_destino.parent,
    )
    os.close(descriptor)
    ruta_temporal_dump = Path(ruta_temporal_dump)
    modelos = _modelos_fixture_mysql()
    try:
        call_command(
            'dumpdata',
            format='json',
            indent=0,
            exclude=list(MODELOS_EXCLUIDOS_COPIA_MYSQL),
            output=str(ruta_temporal_dump),
            verbosity=0,
        )
        cabecera = {
            'format': FORMATO_COPIA_MYSQL,
            'version': VERSION_COPIA_MYSQL,
            'backend': 'mysql',
            'models': modelos,
        }
        with ruta_destino.open('w', encoding='utf-8', newline='\n') as destino:
            destino.write(json.dumps(cabecera, ensure_ascii=False, separators=(',', ':')))
            destino.write('\n')
            with ruta_temporal_dump.open('r') as origen:
                for registro in _iterar_lista_json(origen):
                    if registro.get('model') not in modelos:
                        raise RuntimeError('Django exportó un modelo fuera del esquema esperado.')
                    if registro.get('model', '').casefold() == 'auth.user':
                        registro['fields']['last_login'] = None
                    destino.write(json.dumps(registro, ensure_ascii=False, separators=(',', ':')))
                    destino.write('\n')
    finally:
        ruta_temporal_dump.unlink(missing_ok=True)


# Valida la cabecera y cada registro de una copia MySQL sin modificar la base actual.
def _validar_copia_mysql(ruta):
    ruta = Path(ruta)
    if not ruta.is_file() or ruta.stat().st_size == 0:
        raise ValueError('Selecciona una copia MySQL JSONL válida.')
    if ruta.stat().st_size > MAX_TAMANO_COPIA_INFORMACION:
        raise ValueError('La copia supera el límite permitido de 1 GB.')

    modelos_esperados = _modelos_fixture_mysql()
    try:
        with ruta.open('r', encoding='utf-8') as archivo:
            cabecera_texto = archivo.readline()
            cabecera = json.loads(cabecera_texto)
            if (
                not isinstance(cabecera, dict)
                or cabecera.get('format') != FORMATO_COPIA_MYSQL
                or cabecera.get('version') != VERSION_COPIA_MYSQL
                or cabecera.get('backend') != 'mysql'
                or cabecera.get('models') != modelos_esperados
            ):
                raise ValueError('La copia MySQL no corresponde al esquema de esta instalación de Piemonte.')

            for numero_linea, linea in enumerate(archivo, start=2):
                if not linea.strip():
                    raise ValueError(f'La copia MySQL contiene una línea vacía en la línea {numero_linea}.')
                registro = json.loads(linea)
                if (
                    not isinstance(registro, dict)
                    or not isinstance(registro.get('model'), str)
                    or registro['model'] not in modelos_esperados
                    or 'pk' not in registro
                    or not isinstance(registro.get('fields'), dict)
                ):
                    raise ValueError(f'La copia MySQL contiene un registro no válido en la línea {numero_linea}.')
                list(serializers.deserialize('json', f'[{linea.strip()}]'))
    except (UnicodeDecodeError, json.JSONDecodeError, DeserializationError, TypeError) as error:
        raise ValueError('El archivo no contiene una copia MySQL JSONL válida de Piemonte.') from error
    return cabecera


# Cita identificadores SQLite inspeccionados antes de armar una consulta.
def _identificador_sql(nombre):
    return f'"{nombre.replace(chr(34), chr(34) * 2)}"'


# Actualiza los respaldos iguales para conservar el archivo y la fecha más recientes.
def _guardar_copia_informacion(ruta_origen, tipo, usuario, hora=None):
    hora = hora or timezone.now()
    carpeta = directorio_copias()
    carpeta.mkdir(parents=True, exist_ok=True)
    identificador = uuid4().hex
    extension = '.sqlite3' if Path(ruta_origen).suffix.lower() in ('.sqlite3', '.db') else '.jsonl'
    nombre_archivo = f'piemonte_informacion_{hora:%Y-%m-%d_%H-%M-%S}_{identificador[:8]}{extension}'
    ruta_final = carpeta / nombre_archivo
    descriptor, ruta_temporal = tempfile.mkstemp(
        prefix=f'.{identificador}_',
        suffix=f'{extension}.tmp',
        dir=carpeta,
    )
    os.close(descriptor)
    ruta_temporal = Path(ruta_temporal)
    try:
        shutil.copyfile(ruta_origen, ruta_temporal)
        huella = (
            _hash_base_datos(ruta_origen)
            if extension == '.sqlite3'
            else _hash_archivos([('piemonte_mysql.jsonl', Path(ruta_origen))])
        )
        existente = CopiaSeguridad.objects.filter(
            alcance='informacion',
            sha256=huella,
        ).order_by('-creado_en', '-pk').first()
        ruta_anterior = ruta_archivo_copia(existente) if existente else None
        os.replace(ruta_temporal, ruta_final)
        if existente:
            existente.archivo = nombre_archivo
            existente.ruta_archivo = str(ruta_final.resolve())
            existente.tipo = tipo
            existente.creado_en = hora
            existente.tamano_bytes = ruta_final.stat().st_size
            existente.creado_por = usuario
            existente.save(update_fields=(
                'archivo', 'ruta_archivo', 'tipo', 'creado_en', 'tamano_bytes', 'creado_por',
            ))
            copia = existente
        else:
            copia = CopiaSeguridad.objects.create(
                archivo=nombre_archivo,
                ruta_archivo=str(ruta_final.resolve()),
                sha256=huella,
                tipo=tipo,
                alcance='informacion',
                creado_en=hora,
                tamano_bytes=ruta_final.stat().st_size,
                creado_por=usuario,
            )
    except Exception:
        ruta_final.unlink(missing_ok=True)
        raise
    finally:
        ruta_temporal.unlink(missing_ok=True)

    if ruta_anterior and ruta_anterior != ruta_final and ruta_anterior.is_file():
        ruta_anterior.unlink()
    _aplicar_retencion('informacion')
    return copia, True


# Calcula una huella estable de la información sin incluir el catálogo ni la programación de respaldos.
def _hash_base_datos(ruta_base):
    descriptor, ruta_temporal = tempfile.mkstemp(prefix='.piemonte_hash_', suffix='.sqlite3', dir=Path(ruta_base).parent)
    os.close(descriptor)
    ruta_temporal = Path(ruta_temporal)
    try:
        _crear_base_hash(ruta_base, ruta_temporal)
        return _hash_archivos([('base.sqlite3', ruta_temporal)])
    finally:
        ruta_temporal.unlink(missing_ok=True)


# Normaliza una base para comparar el contenido sin incluir el historial de copias.
def _crear_base_hash(ruta_origen, ruta_destino):
    with closing(sqlite3.connect(ruta_origen)) as base_origen, closing(sqlite3.connect(ruta_destino)) as base_hash:
        base_origen.backup(base_hash)
        tablas = {
            fila[0] for fila in base_hash.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
        for tabla in ('copia_seguridad', 'configuracion_copias_seguridad'):
            if tabla in tablas:
                base_hash.execute(f'DROP TABLE {_identificador_sql(tabla)}')
        if 'sqlite_sequence' in tablas:
            base_hash.execute(
                'DELETE FROM sqlite_sequence WHERE name IN (?, ?)',
                ('copia_seguridad', 'configuracion_copias_seguridad'),
            )
        base_hash.commit()
        base_hash.execute('VACUUM')


def _hash_datos_para_fusion(ruta_base):
    tablas_omitidas = TABLAS_ADMINISTRACION_COPIAS | {'django_content_type', 'auth_permission'}
    huella = hashlib.sha256()
    with closing(sqlite3.connect(ruta_base)) as base:
        tablas = sorted(
            fila[0] for fila in base.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
            if not fila[0].startswith('sqlite_') and fila[0] not in tablas_omitidas
        )
        for tabla in tablas:
            informacion = base.execute(f'PRAGMA table_info({_identificador_sql(tabla)})').fetchall()
            columnas = [fila[1] for fila in informacion]
            if not columnas:
                continue
            claves = [
                fila[1] for fila in sorted(informacion, key=lambda columna: columna[5]) if fila[5]
            ]
            orden = ', '.join(_identificador_sql(clave) for clave in claves) if claves else 'rowid'
            nombre_seguro = _identificador_sql(tabla)
            consulta = f'SELECT * FROM {nombre_seguro} ORDER BY {orden}'
            huella.update(json.dumps(
                [tabla, [(fila[1], fila[2], fila[3], fila[4], fila[5]) for fila in informacion]],
                ensure_ascii=False,
                separators=(',', ':'),
            ).encode('utf-8'))
            huella.update(b'\0')
            cursor = base.execute(consulta)
            while True:
                registros = cursor.fetchmany(500)
                if not registros:
                    break
                for registro in registros:
                    valores = list(registro)
                    if tabla == 'auth_user' and 'last_login' in columnas:
                        valores[columnas.index('last_login')] = None
                    serializados = json.dumps(
                        valores,
                        ensure_ascii=False,
                        separators=(',', ':'),
                        default=lambda valor: {'__bytes__': valor.hex()},
                    )
                    huella.update(serializados.encode('utf-8'))
                    huella.update(b'\n')
    return huella.hexdigest()


# Valida la estructura, integridad y huella del ZIP de un proyecto completo sin extraer su código.
def _validar_copia_proyecto(ruta_zip):
    descriptor_db, ruta_db = tempfile.mkstemp(prefix='.piemonte_proyecto_db_', suffix='.sqlite3')
    os.close(descriptor_db)
    ruta_db = Path(ruta_db)
    descriptor_hash, ruta_hash = tempfile.mkstemp(prefix='.piemonte_proyecto_hash_', suffix='.sqlite3')
    os.close(descriptor_hash)
    ruta_hash = Path(ruta_hash)
    try:
        with zipfile.ZipFile(ruta_zip) as paquete:
            entradas = paquete.infolist()
            nombres = [entrada.filename for entrada in entradas]
            if len(nombres) != len(set(nombres)) or nombres.count('manifest.json') != 1:
                raise ValueError('El ZIP no tiene un manifiesto único o contiene rutas duplicadas.')
            archivos_programa = []
            tamano_extraido = 0
            for entrada in entradas:
                nombre = entrada.filename
                if nombre == 'manifest.json':
                    if entrada.file_size > 1024 * 1024:
                        raise ValueError('El manifiesto del proyecto supera el tamaño permitido.')
                    continue
                partes = nombre.split('/')
                modo_archivo = entrada.external_attr >> 16
                if (
                    not nombre.startswith('program/')
                    or '\\' in nombre
                    or nombre.startswith('/')
                    or any(parte in ('', '.', '..') or ':' in parte for parte in partes)
                    or entrada.is_dir()
                    or stat.S_ISLNK(modo_archivo)
                    or stat.S_IFMT(modo_archivo) not in (0, stat.S_IFREG)
                    or entrada.flag_bits & 0x1
                ):
                    raise ValueError('El ZIP contiene rutas, enlaces o archivos no permitidos.')
                tamano_extraido += entrada.file_size
                if tamano_extraido > MAX_TAMANO_EXTRAIDO_PROYECTO:
                    raise ValueError('El contenido descomprimido del proyecto supera el límite permitido.')
                archivos_programa.append(entrada)

            manifiesto = json.loads(paquete.read('manifest.json').decode('utf-8'))
            if (
                not isinstance(manifiesto, dict)
                or manifiesto.get('proyecto') != 'program/'
                or manifiesto.get('archivos_programa') != len(archivos_programa)
                or not isinstance(manifiesto.get('sha256_contenido'), str)
                or len(manifiesto['sha256_contenido']) != 64
                or any(caracter not in '0123456789abcdef' for caracter in manifiesto['sha256_contenido'].lower())
            ):
                raise ValueError('El manifiesto no corresponde a una copia completa de Piemonte.')
            nombre_db = manifiesto.get('base_datos')
            entrada_db = next((entrada for entrada in archivos_programa if entrada.filename == nombre_db), None)
            if entrada_db is None:
                raise ValueError('La base de datos declarada no está incluida en el ZIP.')
            motor_db = manifiesto.get('motor_base_datos', 'sqlite')
            if motor_db not in ('sqlite', 'mysql'):
                raise ValueError('El manifiesto declara un motor de base de datos no admitido.')

            with paquete.open(entrada_db) as origen_db, ruta_db.open('wb') as destino_db:
                shutil.copyfileobj(origen_db, destino_db)
            formato_db = _validar_copia_informacion(ruta_db)
            if formato_db != motor_db:
                raise ValueError('El motor declarado en el manifiesto no coincide con la copia incluida.')
            if motor_db == 'sqlite':
                _crear_base_hash(ruta_db, ruta_hash)

            huella = hashlib.sha256()
            for entrada in archivos_programa:
                huella.update(entrada.filename.encode('utf-8'))
                huella.update(b'\0')
                if entrada.filename == nombre_db and motor_db == 'sqlite':
                    origen = ruta_hash.open('rb')
                elif entrada.filename == nombre_db:
                    origen = ruta_db.open('rb')
                else:
                    origen = paquete.open(entrada)
                with origen:
                    for bloque in iter(lambda: origen.read(1024 * 1024), b''):
                        huella.update(bloque)
                huella.update(b'\0')
            if huella.hexdigest() != manifiesto['sha256_contenido'].lower():
                raise ValueError('La huella del proyecto no coincide; el ZIP está incompleto o fue alterado.')
    except (zipfile.BadZipFile, json.JSONDecodeError, UnicodeDecodeError, KeyError, StopIteration) as error:
        raise ValueError('El archivo no es una copia ZIP completa y válida de Piemonte.') from error
    finally:
        ruta_db.unlink(missing_ok=True)
        ruta_hash.unlink(missing_ok=True)
    return manifiesto['sha256_contenido'].lower()


# Guarda un ZIP completo subido, actualizando el duplicado más antiguo del mismo contenido.
def subir_copia_proyecto(archivo_subido, usuario=None):
    carpeta = directorio_copias()
    carpeta.mkdir(parents=True, exist_ok=True)
    descriptor, ruta_temporal = tempfile.mkstemp(prefix='.piemonte_subida_proyecto_', suffix='.zip', dir=carpeta)
    os.close(descriptor)
    ruta_temporal = Path(ruta_temporal)
    descriptor_destino, ruta_temporal_destino = tempfile.mkstemp(
        prefix='.piemonte_proyecto_', suffix='.zip.tmp', dir=carpeta,
    )
    os.close(descriptor_destino)
    ruta_temporal_destino = Path(ruta_temporal_destino)
    ruta_final = None
    registrada = False
    try:
        tamano = 0
        with ruta_temporal.open('wb') as destino:
            for bloque in archivo_subido.chunks():
                tamano += len(bloque)
                if tamano > MAX_TAMANO_COPIA_PROYECTO:
                    raise ValueError('El ZIP del proyecto supera el límite permitido de 2 GB.')
                destino.write(bloque)
        huella = _validar_copia_proyecto(ruta_temporal)
        hora = timezone.now()
        identificador = uuid4().hex
        nombre_archivo = f'piemonte_backup_subido_{hora:%Y-%m-%d_%H-%M-%S}_{identificador[:8]}.zip'
        ruta_final = carpeta / nombre_archivo
        existente = CopiaSeguridad.objects.filter(
            alcance='proyecto',
            sha256=huella,
        ).order_by('-creado_en', '-pk').first()
        ruta_anterior = ruta_archivo_copia(existente) if existente else None
        shutil.copyfile(ruta_temporal, ruta_temporal_destino)
        os.replace(ruta_temporal_destino, ruta_final)
        if existente:
            existente.archivo = nombre_archivo
            existente.ruta_archivo = str(ruta_final.resolve())
            existente.tipo = 'manual'
            existente.creado_en = hora
            existente.tamano_bytes = ruta_final.stat().st_size
            existente.creado_por = usuario
            existente.save(update_fields=(
                'archivo', 'ruta_archivo', 'tipo', 'creado_en', 'tamano_bytes', 'creado_por',
            ))
            copia = existente
        else:
            copia = CopiaSeguridad.objects.create(
                archivo=nombre_archivo,
                ruta_archivo=str(ruta_final.resolve()),
                sha256=huella,
                tipo='manual',
                alcance='proyecto',
                creado_en=hora,
                tamano_bytes=ruta_final.stat().st_size,
                creado_por=usuario,
            )
        registrada = True
        if ruta_anterior and ruta_anterior != ruta_final and ruta_anterior.is_file():
            ruta_anterior.unlink()
        _aplicar_retencion('proyecto')
        return copia, True
    except Exception:
        if ruta_final and not registrada:
            ruta_final.unlink(missing_ok=True)
        raise
    finally:
        ruta_temporal.unlink(missing_ok=True)
        ruta_temporal_destino.unlink(missing_ok=True)


# Elimina los respaldos más antiguos de un alcance cuando se supera el límite configurado.
def _aplicar_retencion(alcance):
    sobrantes = CopiaSeguridad.objects.filter(alcance=alcance).order_by('-creado_en', '-pk')[MAX_COPIAS_POR_ALCANCE:]
    for copia in sobrantes:
        ruta = ruta_archivo_copia(copia)
        if ruta.name != copia.archivo:
            raise RuntimeError('La ruta de una copia de seguridad no coincide con su nombre de archivo.')
        if ruta.is_file():
            ruta.unlink()
        copia.delete()


# Crea una copia de solo información usando el formato nativo de cada motor admitido.
def _crear_copia_informacion(tipo, usuario):
    if connection.vendor not in ('sqlite', 'mysql'):
        raise RuntimeError('Las copias integradas solo admiten bases de datos SQLite o MySQL.')
    carpeta = directorio_copias()
    carpeta.mkdir(parents=True, exist_ok=True)
    extension = '.sqlite3' if connection.vendor == 'sqlite' else '.jsonl'
    descriptor, ruta_temporal = tempfile.mkstemp(
        prefix='.piemonte_datos_',
        suffix=extension,
        dir=carpeta,
    )
    os.close(descriptor)
    ruta_temporal = Path(ruta_temporal)
    try:
        if connection.vendor == 'sqlite':
            connection.ensure_connection()
            with closing(sqlite3.connect(ruta_temporal)) as base_temporal:
                connection.connection.backup(base_temporal)
            with closing(sqlite3.connect(ruta_temporal)) as base_temporal:
                resultado = base_temporal.execute('PRAGMA quick_check').fetchone()
            if not resultado or resultado[0] != 'ok':
                raise RuntimeError('La copia de información no pasó la comprobación de integridad de SQLite.')
        else:
            _exportar_fixture_mysql(ruta_temporal)
            _validar_copia_mysql(ruta_temporal)
        return _guardar_copia_informacion(ruta_temporal, tipo, usuario)
    finally:
        ruta_temporal.unlink(missing_ok=True)


# Comprueba que el archivo subido sea una copia íntegra de información SQLite o MySQL.
def _validar_copia_informacion(ruta):
    ruta = Path(ruta)
    if not ruta.is_file() or ruta.stat().st_size == 0:
        raise ValueError('Selecciona una copia de información SQLite o MySQL válida.')
    if ruta.stat().st_size > MAX_TAMANO_COPIA_INFORMACION:
        raise ValueError('La copia supera el límite permitido de 1 GB.')
    with ruta.open('rb') as archivo:
        firma = archivo.read(16)
    if firma != b'SQLite format 3\x00':
        _validar_copia_mysql(ruta)
        return 'mysql'
    try:
        with closing(sqlite3.connect(ruta)) as base:
            integridad = base.execute('PRAGMA quick_check').fetchone()
            tablas = {
                fila[0] for fila in base.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
            }
            tiene_usuarios = base.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'auth_user'"
            ).fetchone()
            tiene_migraciones = base.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'django_migrations'"
            ).fetchone()
            tiene_tablas_de_datos = any(
                nombre.lower().startswith(('bd_', 'core_')) or nombre.lower() in {
                    'casa', 'propietario', 'residente', 'proceso', 'pago',
                }
                for nombre in tablas
            )
            if not integridad or integridad[0] != 'ok':
                raise ValueError('La copia de información está dañada y SQLite no pudo validarla.')
            if not tiene_usuarios or not tiene_migraciones or not tiene_tablas_de_datos:
                raise ValueError('El archivo no contiene la estructura de datos esperada de Piemonte.')
            if base.execute("SELECT 1 FROM sqlite_master WHERE type = 'trigger' LIMIT 1").fetchone():
                raise ValueError('No se admiten copias con disparadores SQLite ejecutables.')
    except sqlite3.DatabaseError as error:
        raise ValueError('El archivo no se puede abrir como una copia de información válida.') from error
    return 'sqlite'


# Convierte fechas SQLite a valores comparables para impedir que una copia antigua reemplace datos actuales.
def _valor_temporal(valor):
    if valor is None:
        return None
    if isinstance(valor, (int, float)):
        return float(valor)
    if isinstance(valor, datetime):
        instante = valor
    elif isinstance(valor, date):
        instante = datetime.combine(valor, datetime.min.time())
    elif isinstance(valor, bytes):
        valor = valor.decode('utf-8', errors='strict')
        instante = None
    elif isinstance(valor, str):
        instante = None
    else:
        return None
    if instante is None:
        try:
            instante = datetime.fromisoformat(valor.replace('Z', '+00:00'))
        except ValueError:
            try:
                instante = datetime.combine(datetime.fromisoformat(valor).date(), datetime.min.time())
            except ValueError:
                return None
    if instante.tzinfo is None:
        instante = instante.replace(tzinfo=datetime_timezone.utc)
    return instante.timestamp()


# Devuelve la fecha de versión de un registro solo si existe un campo temporal reconocible.
def _fecha_version(registro, columnas):
    indices = {nombre.casefold(): indice for indice, nombre in enumerate(columnas)}
    for nombre in CAMPO_FECHA_VERSION:
        if nombre.casefold() in indices:
            valor = _valor_temporal(registro[indices[nombre.casefold()]])
            if valor is not None:
                return valor
    return None


# Obtiene de un modelo Django la fecha comparable que protege registros más recientes.
def _fecha_version_modelo(instancia):
    for nombre in CAMPO_FECHA_VERSION:
        for campo in instancia._meta.concrete_fields:
            identificadores = {
                campo.name.casefold(),
                campo.attname.casefold(),
                (campo.db_column or '').casefold(),
            }
            if nombre.casefold() in identificadores:
                valor = _valor_temporal(getattr(instancia, campo.attname))
                if valor is not None:
                    return valor
    return None


# Mezcla dos bases por clave primaria: agrega faltantes y solo actualiza conflictos con fecha más reciente.
def _mezclar_bases_datos(ruta_actual, ruta_copia):
    tablas_omitidas = TABLAS_ADMINISTRACION_COPIAS | {
        'django_content_type',
        'auth_permission',
    }
    agregados = 0
    actualizados = 0
    with closing(sqlite3.connect(ruta_actual)) as actual, closing(sqlite3.connect(ruta_copia)) as copia:
        actual.execute('PRAGMA foreign_keys = OFF')
        tablas_actuales = {
            fila[0] for fila in actual.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
            if not fila[0].startswith('sqlite_')
        }
        tablas_copia = {
            fila[0] for fila in copia.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
            if not fila[0].startswith('sqlite_')
        }
        tablas_requeridas = tablas_actuales - tablas_omitidas - {'django_content_type', 'auth_permission'}
        faltantes = tablas_requeridas - tablas_copia
        if faltantes:
            raise ValueError('La copia no tiene todas las tablas de esta instalación; no se aplicó ningún cambio.')
        tablas = sorted(tablas_requeridas & tablas_copia)
        if not tablas:
            raise ValueError('La copia no comparte tablas de información con esta instalación.')

        for tabla in tablas:
            nombre_seguro = _identificador_sql(tabla)
            informacion = actual.execute(f'PRAGMA table_info({nombre_seguro})').fetchall()
            columnas = [fila[1] for fila in informacion]
            columnas_copia = [
                fila[1] for fila in copia.execute(f'PRAGMA table_info({nombre_seguro})').fetchall()
            ]
            if columnas != columnas_copia:
                raise ValueError(
                    f'La estructura de la tabla "{tabla}" no coincide. Usa una copia del mismo proyecto actualizado.'
                )
            claves = [
                fila[1] for fila in sorted(informacion, key=lambda columna: columna[5]) if fila[5]
            ]
            if not claves:
                continue
            lista_columnas = ', '.join(_identificador_sql(columna) for columna in columnas)
            marcadores = ', '.join('?' for _ in columnas)
            clausula_clave = ' AND '.join(
                f'{_identificador_sql(clave)} IS ?' for clave in claves
            )
            for valores in copia.execute(f'SELECT {lista_columnas} FROM {nombre_seguro}'):
                registro_copia = dict(zip(columnas, valores))
                clave_valores = tuple(registro_copia[clave] for clave in claves)
                registro_actual = actual.execute(
                    f'SELECT {lista_columnas} FROM {nombre_seguro} WHERE {clausula_clave}',
                    clave_valores,
                ).fetchone()
                if registro_actual is None:
                    cursor = actual.execute(
                        f'INSERT OR IGNORE INTO {nombre_seguro} ({lista_columnas}) VALUES ({marcadores})',
                        valores,
                    )
                    agregados += cursor.rowcount
                    continue
                if tabla == 'auth_user':
                    continue
                version_actual = _fecha_version(registro_actual, columnas)
                version_copia = _fecha_version(valores, columnas)
                if version_actual is None or version_copia is None or version_copia <= version_actual:
                    continue
                columnas_actualizables = [columna for columna in columnas if columna not in claves]
                if columnas_actualizables:
                    asignaciones = ', '.join(
                        f'{_identificador_sql(columna)} = ?'
                        for columna in columnas_actualizables
                    )
                    cursor = actual.execute(
                        f'UPDATE {nombre_seguro} SET {asignaciones} WHERE {clausula_clave}',
                        tuple(registro_copia[columna] for columna in columnas_actualizables) + clave_valores,
                    )
                    actualizados += cursor.rowcount

        errores_fk = actual.execute('PRAGMA foreign_key_check').fetchmany(10)
        if errores_fk:
            raise ValueError('La copia generaría relaciones incompletas; no se aplicó ningún cambio.')
        actual.commit()
    return agregados, actualizados


# Recorre los registros fixture en orden de exportación sin cargar el archivo completo en memoria.
def _iterar_fixture_mysql(ruta):
    with Path(ruta).open('r', encoding='utf-8') as archivo:
        next(archivo)
        for linea in archivo:
            yield from serializers.deserialize('json', f'[{linea.strip()}]')


# Fusiona el fixture MySQL, agrega claves faltantes y solo actualiza conflictos con fecha más reciente.
def _mezclar_fixture_mysql(ruta_copia):
    tablas_omitidas = TABLAS_ADMINISTRACION_COPIAS | {
        'django_content_type',
        'auth_permission',
    }
    agregados = 0
    actualizados = 0
    try:
        with transaction.atomic():
            with connection.constraint_checks_disabled():
                for registro in _iterar_fixture_mysql(ruta_copia):
                    instancia = registro.object
                    modelo = instancia.__class__
                    tabla = modelo._meta.db_table
                    if tabla in tablas_omitidas:
                        continue

                    existente = modelo._base_manager.using(connection.alias).filter(
                        pk=instancia.pk,
                    ).first()
                    if existente is None:
                        registro.save(using=connection.alias, force_insert=True)
                        agregados += 1
                        continue
                    if modelo._meta.label_lower == 'auth.user':
                        continue

                    version_actual = _fecha_version_modelo(existente)
                    version_copia = _fecha_version_modelo(instancia)
                    if version_actual is None or version_copia is None or version_copia <= version_actual:
                        continue
                    registro.save(using=connection.alias, force_update=True)
                    actualizados += 1
            connection.check_constraints()
    except IntegrityError as error:
        raise ValueError(
            'La copia contiene relaciones o claves que no se pueden fusionar; no se aplicó ningún cambio.'
        ) from error
    return agregados, actualizados


# Importa una copia de información sin hacer retroceder registros actuales cuando no hay fechas comparables.
def restaurar_copia_informacion(archivo_subido, usuario=None):
    if connection.vendor not in ('sqlite', 'mysql'):
        raise RuntimeError('La restauración integrada solo admite bases de datos SQLite o MySQL.')
    nombre_db = str(connection.settings_dict['NAME']) if connection.vendor == 'sqlite' else ''
    base_en_memoria = connection.vendor == 'sqlite' and (
        nombre_db == ':memory:' or (nombre_db.startswith('file:') and 'mode=memory' in nombre_db)
    )
    if connection.vendor == 'sqlite' and nombre_db.startswith('file:') and not base_en_memoria:
        raise RuntimeError('La restauración integrada no admite URI SQLite que no sean bases en memoria.')
    ruta_db = None
    if connection.vendor == 'sqlite' and not base_en_memoria:
        ruta_db = Path(nombre_db)
        if not ruta_db.is_absolute():
            ruta_db = Path(settings.BASE_DIR) / ruta_db
        ruta_db = ruta_db.resolve()
        ruta_db.parent.mkdir(parents=True, exist_ok=True)

    carpeta = directorio_copias()
    carpeta.mkdir(parents=True, exist_ok=True)
    extension = '.sqlite3' if connection.vendor == 'sqlite' else '.jsonl'
    descriptor_subida, ruta_subida = tempfile.mkstemp(
        prefix='.piemonte_subida_',
        suffix=extension,
        dir=carpeta,
    )
    os.close(descriptor_subida)
    ruta_subida = Path(ruta_subida)
    directorio_temporal_db = ruta_db.parent if ruta_db else carpeta
    descriptor_actual, ruta_actual_temporal = tempfile.mkstemp(
        prefix='.piemonte_actual_',
        suffix=extension,
        dir=directorio_temporal_db,
    )
    os.close(descriptor_actual)
    ruta_actual_temporal = Path(ruta_actual_temporal)

    try:
        tamano = 0
        with ruta_subida.open('wb') as destino:
            for bloque in archivo_subido.chunks():
                tamano += len(bloque)
                if tamano > MAX_TAMANO_COPIA_INFORMACION:
                    raise ValueError('La copia supera el límite permitido de 1 GB.')
                destino.write(bloque)
        formato = _validar_copia_informacion(ruta_subida)
        if formato != connection.vendor:
            raise ValueError(
                f'La copia usa {formato} y la base de datos actual usa {connection.vendor}.'
            )

        if formato == 'sqlite':
            with closing(sqlite3.connect(ruta_actual_temporal)) as base_actual:
                connection.ensure_connection()
                connection.connection.backup(base_actual)
            if _hash_datos_para_fusion(ruta_actual_temporal) == _hash_datos_para_fusion(ruta_subida):
                raise CopiaInformacionIdentica(
                    'Esta copia es idéntica a la información actual; no se realizó la fusión.'
                )
            copia_previa, _ = _crear_copia_informacion('manual', usuario)
            copia_importada, _ = _guardar_copia_informacion(ruta_subida, 'manual', usuario)
            agregados, actualizados = _mezclar_bases_datos(ruta_actual_temporal, ruta_subida)

            with closing(sqlite3.connect(ruta_actual_temporal)) as base_restaurada:
                connection.ensure_connection()
                base_restaurada.backup(connection.connection)
                connection.connection.commit()
        else:
            _exportar_fixture_mysql(ruta_actual_temporal)
            if _hash_archivos([('piemonte_mysql.jsonl', ruta_actual_temporal)]) == _hash_archivos(
                [('piemonte_mysql.jsonl', ruta_subida)]
            ):
                raise CopiaInformacionIdentica(
                    'Esta copia es idéntica a la información actual; no se realizó la fusión.'
                )
            copia_previa, _ = _crear_copia_informacion('manual', usuario)
            copia_importada, _ = _guardar_copia_informacion(ruta_subida, 'manual', usuario)
            agregados, actualizados = _mezclar_fixture_mysql(ruta_subida)

        _aplicar_retencion('informacion')
        return copia_previa, copia_importada, agregados, actualizados
    finally:
        ruta_subida.unlink(missing_ok=True)
        ruta_actual_temporal.unlink(missing_ok=True)


# Realiza la tarea de archivos programa y entrega el resultado al flujo que la invoca.
def _archivos_programa(ruta_db_temporal):
    base_proyecto = Path(settings.BASE_DIR)
    archivos = []
    if connection.vendor == 'mysql':
        ruta_db_relativa = Path('database/piemonte_mysql.jsonl')
        archivos_db = []
    else:
        nombre_configurado = str(settings.DATABASES['default']['NAME'])
        # La base en memoria no tiene ruta; las bases en disco también omiten sus auxiliares SQLite.
        base_en_memoria = nombre_configurado == ':memory:' or nombre_configurado.startswith('file:')
        ruta_db = Path(nombre_configurado)
        ruta_db_resuelta = ruta_db.resolve() if not base_en_memoria else None
        nombre_db = ruta_db.name if not base_en_memoria and ruta_db.name not in ('', '.') else 'BD.sqlite3'
        archivos_db = [] if base_en_memoria else [
            ruta_db_resuelta,
            Path(f'{ruta_db}-wal').resolve(),
            Path(f'{ruta_db}-shm').resolve(),
            Path(f'{ruta_db}-journal').resolve(),
        ]
        if base_en_memoria:
            ruta_db_relativa = Path(nombre_db)
        else:
            try:
                ruta_db_relativa = ruta_db_resuelta.relative_to(base_proyecto.resolve())
            except ValueError:
                ruta_db_relativa = Path(nombre_db)
            if ruta_db_relativa.as_posix() == '.':
                ruta_db_relativa = Path(nombre_db)
    archivos.append((f'program/{ruta_db_relativa.as_posix()}', ruta_db_temporal))

    # Se evita incluir enlaces simbólicos para que el respaldo no salga de la carpeta del proyecto.
    if base_proyecto.is_symlink():
        raise RuntimeError(f'No se puede respaldar un enlace simbólico del proyecto: {base_proyecto}')
    for ruta in sorted(base_proyecto.rglob('*')):
        if ruta.is_symlink():
            raise RuntimeError(f'No se puede respaldar un enlace simbólico del proyecto: {ruta}')
        if not ruta.is_file():
            continue
        ruta_resuelta = ruta.resolve()
        if any(ruta_resuelta == ruta_db_extra for ruta_db_extra in archivos_db):
            continue
        ruta_relativa = ruta.relative_to(base_proyecto).as_posix()
        if ruta_relativa == ruta_db_relativa.as_posix():
            continue
        archivos.append((f'program/{ruta_relativa}', ruta))
    return archivos


# Crea creación copia seguridad y coordina los datos relacionados.
def crear_copia_seguridad(tipo='manual', usuario=None, alcance='proyecto'):
    if tipo not in dict(CopiaSeguridad.TIPOS):
        raise ValueError('El tipo de copia solicitado no es válido.')
    if alcance not in dict(CopiaSeguridad.ALCANCES):
        raise ValueError('El alcance de copia solicitado no es válido.')
    if connection.vendor not in ('sqlite', 'mysql'):
        raise RuntimeError('Las copias integradas solo admiten bases de datos SQLite o MySQL.')
    if alcance == 'informacion':
        return _crear_copia_informacion(tipo, usuario)

    carpeta = directorio_copias()
    carpeta.mkdir(parents=True, exist_ok=True)
    identificador = uuid4().hex
    extension_db = '.sqlite3' if connection.vendor == 'sqlite' else '.jsonl'
    descriptor_db, ruta_db_temporal = tempfile.mkstemp(
        prefix=f'.{identificador}_',
        suffix=extension_db,
        dir=carpeta,
    )
    os.close(descriptor_db)
    ruta_db_temporal = Path(ruta_db_temporal)
    descriptor_hash_db, ruta_hash_db = tempfile.mkstemp(prefix=f'.{identificador}_hash_', suffix='.sqlite3', dir=carpeta)
    os.close(descriptor_hash_db)
    ruta_hash_db = Path(ruta_hash_db)
    ruta_zip_temporal = carpeta / f'.{identificador}.zip.tmp'
    hora = timezone.now()

    try:
        if connection.vendor == 'sqlite':
            connection.ensure_connection()
            with closing(sqlite3.connect(ruta_db_temporal)) as base_temporal:
                connection.connection.backup(base_temporal)
            # La huella ignora el catálogo de copias, que cambia al registrar este mismo respaldo.
            with closing(sqlite3.connect(ruta_db_temporal)) as base_temporal, closing(sqlite3.connect(ruta_hash_db)) as base_hash:
                base_temporal.backup(base_hash)
                base_hash.execute('DROP TABLE IF EXISTS "copia_seguridad"')
                base_hash.execute('DROP TABLE IF EXISTS "configuracion_copias_seguridad"')
                base_hash.execute(
                    'DELETE FROM sqlite_sequence WHERE name IN (?, ?)',
                    ('copia_seguridad', 'configuracion_copias_seguridad'),
                )
                base_hash.commit()
                base_hash.execute('VACUUM')
        else:
            _exportar_fixture_mysql(ruta_db_temporal)
            _validar_copia_mysql(ruta_db_temporal)

        archivos_programa = _archivos_programa(ruta_db_temporal)
        archivos_para_hash = [
            (
                ruta,
                ruta_hash_db
                if connection.vendor == 'sqlite' and origen == ruta_db_temporal
                else origen,
            )
            for ruta, origen in archivos_programa
        ]
        huella = _hash_archivos(archivos_para_hash)
        copia_existente = CopiaSeguridad.objects.filter(
            sha256=huella,
            alcance='proyecto',
        ).order_by('-creado_en', '-pk').first()
        ruta_existente = ruta_archivo_copia(copia_existente) if copia_existente else None

        manifiesto = {
            'creado_en': hora.isoformat(),
            'proyecto': 'program/',
            'base_datos': next(ruta for ruta, origen in archivos_programa if origen == ruta_db_temporal),
            'motor_base_datos': connection.vendor,
            'archivos_programa': len(archivos_programa),
            'sha256_contenido': huella,
        }
        # El ZIP conserva rutas relativas del proyecto y agrega un manifiesto para identificar el contenido respaldado.
        with zipfile.ZipFile(ruta_zip_temporal, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as paquete:
            for ruta_paquete, ruta_archivo in archivos_programa:
                paquete.write(ruta_archivo, ruta_paquete)
            paquete.writestr(
                'manifest.json',
                json.dumps(manifiesto, ensure_ascii=False, indent=2),
            )

        # La segunda huella detecta modificaciones en los archivos ocurridas durante la construcción del ZIP.
        archivos_programa_actualizados = _archivos_programa(ruta_db_temporal)
        archivos_para_hash_actualizados = [
            (
                ruta,
                ruta_hash_db
                if connection.vendor == 'sqlite' and origen == ruta_db_temporal
                else origen,
            )
            for ruta, origen in archivos_programa_actualizados
        ]
        if _hash_archivos(archivos_para_hash_actualizados) != huella:
            raise RuntimeError('Los archivos del programa cambiaron mientras se generaba la copia. Inténtalo de nuevo.')

        base_nombre = f'piemonte_backup_{hora:%Y-%m-%d_%H-%M-%S}'
        nombre_archivo = f'{base_nombre}.zip'
        if (carpeta / nombre_archivo).exists() or CopiaSeguridad.objects.filter(archivo=nombre_archivo).exists():
            nombre_archivo = f'{base_nombre}_{identificador[:8]}.zip'
        ruta_final = carpeta / nombre_archivo
        # El reemplazo publica el archivo completo de una sola vez, sin dejar un ZIP parcial con el nombre definitivo.
        os.replace(ruta_zip_temporal, ruta_final)
        if copia_existente:
            try:
                with transaction.atomic():
                    copia_existente.archivo = nombre_archivo
                    copia_existente.ruta_archivo = str(ruta_final.resolve())
                    copia_existente.tipo = tipo
                    copia_existente.creado_en = hora
                    copia_existente.tamano_bytes = ruta_final.stat().st_size
                    copia_existente.creado_por = usuario
                    copia_existente.save(update_fields=(
                        'archivo', 'ruta_archivo', 'tipo', 'creado_en', 'tamano_bytes', 'creado_por',
                    ))
            except Exception:
                ruta_final.unlink(missing_ok=True)
                raise
            if ruta_existente and ruta_existente != ruta_final and ruta_existente.is_file():
                ruta_existente.unlink()
            _aplicar_retencion('proyecto')
            return copia_existente, True

        try:
            with transaction.atomic():
                copia = CopiaSeguridad.objects.create(
                    archivo=nombre_archivo,
                    ruta_archivo=str(ruta_final.resolve()),
                    sha256=huella,
                    tipo=tipo,
                    alcance='proyecto',
                    creado_en=hora,
                    tamano_bytes=ruta_final.stat().st_size,
                    creado_por=usuario,
                )
        except IntegrityError:
            ruta_final.unlink(missing_ok=True)
            raise
        except Exception:
            ruta_final.unlink(missing_ok=True)
            raise
        _aplicar_retencion('proyecto')
        return copia, True
    finally:
        # Los snapshots y el ZIP temporal se eliminan también si falla la compresión o el registro en la base de datos.
        ruta_db_temporal.unlink(missing_ok=True)
        ruta_hash_db.unlink(missing_ok=True)
        ruta_zip_temporal.unlink(missing_ok=True)


# Realiza la tarea de revisión copia automatica y entrega el resultado al flujo que la invoca.
def revisar_copia_automatica(ahora=None):
    ahora = ahora or timezone.now()
    configuracion = ConfiguracionCopiasSeguridad.objects.filter(pk=1).first()
    if configuracion is None or not configuracion.automaticas_activas:
        return None, False
    if configuracion.proxima_automatica is None:
        configuracion.proxima_automatica = ahora + intervalo_configurado(configuracion)
        configuracion.save(update_fields=('proxima_automatica',))
        return None, False
    if ahora < configuracion.proxima_automatica:
        return None, False

    copia_proyecto, creada_proyecto = crear_copia_seguridad(
        tipo='automatica',
        alcance='proyecto',
    )
    copia_informacion, creada_informacion = crear_copia_seguridad(
        tipo='automatica',
        alcance='informacion',
    )
    configuracion.ultima_automatica = ahora
    configuracion.proxima_automatica = ahora + intervalo_configurado(configuracion)
    configuracion.save(update_fields=('ultima_automatica', 'proxima_automatica'))
    return (copia_proyecto, copia_informacion), (creada_proyecto, creada_informacion)
