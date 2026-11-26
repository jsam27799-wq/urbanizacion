$root = 'C:\Piemonte Proyecto terminado\Piemonte'
$newline = "`r`n"

function Get-ModuleDescription([string]$relativePath) {
    $name = [IO.Path]::GetFileNameWithoutExtension($relativePath)
    if ($relativePath -match 'migrations\\') { return 'Registra la evolución del esquema de datos de la aplicación BD.' }
    if ($relativePath -match 'templates\\') { return "Presenta la interfaz y los datos dinámicos de la vista «$name»." }
    if ($relativePath -match '\\static\\.*\.css$') { return 'Organiza la presentación visual, los componentes y los ajustes adaptables de la aplicación.' }
    if ($relativePath -match '\\static\\.*\.js$') { return 'Coordina las interacciones del sitio, la navegación y las animaciones de la interfaz.' }
    if ($relativePath -match '\.sql$') { return 'Define la base de datos relacional y las tablas que almacenan la información del conjunto residencial.' }
    $descriptions = @{
        'manage.py' = 'Punto de entrada para ejecutar los comandos administrativos de Django.'
        'settings.py' = 'Centraliza la configuración del proyecto Django, sus aplicaciones, middleware y servicios.'
        'urls.py' = 'Asocia las rutas HTTP del proyecto con las vistas correspondientes.'
        'asgi.py' = 'Expone la aplicación Django para servidores compatibles con ASGI.'
        'wsgi.py' = 'Expone la aplicación Django para servidores compatibles con WSGI.'
        'models.py' = 'Define las entidades de persistencia y sus relaciones en la base de datos.'
        'forms.py' = 'Define formularios, presentación de campos y reglas de validación de los datos recibidos.'
        'views.py' = 'Coordina las solicitudes, reglas de negocio y respuestas de las pantallas de la aplicación.'
        'admin.py' = 'Configura los modelos disponibles y sus opciones de administración en Django.'
        'apps.py' = 'Declara la configuración de la aplicación Django.'
        'tests.py' = 'Agrupa pruebas automatizadas de los comportamientos y reglas de la aplicación.'
        'middleware.py' = 'Aplica reglas transversales durante el procesamiento de solicitudes y respuestas.'
        'permissions.py' = 'Centraliza la determinación de roles y permisos para las acciones de usuario.'
        'auditoria.py' = 'Proporciona el registro común de eventos de auditoría.'
        'cartera.py' = 'Calcula vencimientos, mora y saldos pendientes asociados a las casas.'
        'copias_seguridad.py' = 'Gestiona la creación, ubicación y revisión de copias de seguridad.'
        'estados.py' = 'Define y normaliza las etiquetas y colores configurables de los estados.'
        'context_processors.py' = 'Inyecta datos de configuración compartidos en el contexto de las plantillas.'
        'reportes.py' = 'Construye resúmenes y exportaciones de pagos y otros reportes.'
        'formatos.py' = 'Proporciona filtros de plantilla para presentar valores con formato.'
        'cargar_datos_demo_completos.py' = 'Prepara y carga datos de demostración para probar el sistema.'
        'cargar_personas_reales.py' = 'Carga registros de personas desde la fuente definida por el script.'
        '__init__.py' = 'Marca este directorio como paquete Python y permite su importación.'
    }
    if ($descriptions.ContainsKey([IO.Path]::GetFileName($relativePath))) { return $descriptions[[IO.Path]::GetFileName($relativePath)] }
    if ($relativePath -match 'management\\commands\\') { return 'Implementa un comando de gestión para operaciones administrativas del proyecto.' }
    if ($relativePath -match 'templatetags\\') { return 'Registra filtros o etiquetas reutilizables para las plantillas Django.' }
    return "Reúne la lógica de «$name» dentro de la aplicación."
}

function Get-MigrationDescription([string]$fileName) {
    $map = @{
        '0001_initial.py' = 'crea el esquema inicial de entidades de la aplicación BD.'
        '0002_guardia_usuario.py' = 'vincula el registro de guardia con la cuenta de usuario.'
        '0003_casaresidente_casa_residentes_secundarios_and_more.py' = 'incorpora la relación de residentes secundarios con las casas.'
        '0004_remove_casa_foto_alter_propietario_rol.py' = 'retira el campo de foto de casa y ajusta el rol del propietario.'
        '0005_proceso_estado.py' = 'agrega el estado al registro de procesos.'
        '0006_proceso_tiempo_restante.py' = 'añade el tiempo restante al proceso.'
        '0007_proceso_estado_entregado_tarde.py' = 'amplía los estados de proceso para identificar entregas tardías.'
        '0008_notas_fecha.py' = 'añade la fecha a las notas.'
        '0009_visitante_datos_vehiculo.py' = 'incorpora información del vehículo del visitante.'
        '0010_visitante_tipos.py' = 'define los tipos de visitante.'
        '0011_novedad_tipo_registrado_por.py' = 'añade el tipo de novedad y quién la registra.'
        '0012_notas_titulo.py' = 'agrega un título a las notas.'
        '0013_separar_novedades.py' = 'separa las novedades de los registros anteriores y migra su información.'
        '0014_novedad_fechas.py' = 'añade fechas de referencia a las novedades.'
        '0015_alinear_fecha_suceso.py' = 'alinea el campo de fecha de suceso con el modelo.'
        '0016_resena.py' = 'crea la entidad para reseñas.'
        '0017_alter_novedad_options_casa_cantidad_residentes_and_more.py' = 'ajusta opciones de novedad y datos de residentes de casa.'
        '0018_alter_casa_id_propietario_alter_casa_id_residente.py' = 'modifica las relaciones de casa con propietario y residente.'
        '0019_visitante_autoriza_visitante_residente_secundario.py' = 'añade los datos de autorización del visitante y residente secundario.'
        '0020_visitante_propietario_autorizador.py' = 'incorpora al propietario como posible autorizador de visitantes.'
        '0021_domicilio_autoriza_domicilio_propietario_autorizador_and_more.py' = 'incorpora la autorización de domiciliarios y sus datos asociados.'
        '0022_paquete_informacion_adicional_paquete_llamada_and_more.py' = 'amplía los datos de paquetes y registra la información de llamadas.'
        '0023_alter_pago_id_casa.py' = 'ajusta la relación entre pagos y casas.'
        '0024_propietario_casas_historicas.py' = 'almacena el historial de casas del propietario.'
        '0025_alter_casa_cartera.py' = 'ajusta el campo de cartera de la casa.'
        '0026_configurar_grupos_permisos.py' = 'crea y asigna los grupos y permisos iniciales según roles.'
        '0027_sincronizar_grupos_permisos.py' = 'sincroniza los permisos de los grupos de usuarios.'
        '0028_propietario_usuario.py' = 'relaciona propietarios con cuentas de usuario.'
        '0029_pago_estado_default.py' = 'define un estado predeterminado para los pagos.'
        '0030_resena_rol_usuario.py' = 'asocia las reseñas con el rol de quien las publica.'
        '0031_convertir_residentes_huerfanos.py' = 'migra residentes sin relación principal a la estructura de relaciones vigente.'
        '0032_configuracion_incremento_cartera.py' = 'agrega la configuración del incremento de cartera.'
        '0033_casa_ultima_actualizacion_cartera.py' = 'registra cuándo se actualizó por última vez la cartera de cada casa.'
        '0034_convertir_cartera_a_saldo_pendiente.py' = 'convierte los valores históricos de cartera al saldo pendiente.'
        '0035_configurar_mora_por_vencimiento.py' = 'configura la aplicación de mora de acuerdo con fechas de vencimiento.'
        '0036_separar_saldo_mora.py' = 'separa el saldo de mora del saldo de cartera.'
        '0037_frecuencia_mora_prueba.py' = 'incorpora la frecuencia de mora usada para pruebas.'
        '0038_configuracion_monto_aumento_mensual.py' = 'agrega el monto fijo del aumento mensual.'
        '0039_configuracioncartera_tiempo_domiciliario_minutos.py' = 'configura el tiempo de espera de domiciliarios en minutos.'
        '0040_configuracioncopiasseguridad_copiaseguridad.py' = 'crea la configuración y los registros de copias de seguridad.'
        '0041_configuracioncopiasseguridad_ruta_destino_and_more.py' = 'añade la ruta de destino y otros ajustes de las copias.'
        '0042_alter_copiaseguridad_sha256.py' = 'ajusta el almacenamiento de la huella SHA-256 de una copia.'
        '0043_configuracioncartera_estados_visualizacion.py' = 'agrega la configuración de etiquetas y colores visuales de estados.'
        '0044_registrobitacora.py' = 'crea el registro de bitácora para auditar eventos.'
        '0045_registrobitacora_accion.py' = 'añade el tipo de acción a los eventos de bitácora.'
        '0001_perfilusuario.py' = 'crea el perfil de usuario asociado a las cuentas de autenticación.'
    }
    if ($map.ContainsKey($fileName)) { return $map[$fileName] }
    return 'actualiza el esquema de datos según la evolución de los modelos.'
}

function Convert-Name([string]$name) {
    $text = [regex]::Replace($name, '([a-z])([A-Z])', '$1 $2')
    $text = $text.Trim('_').Replace('_', ' ').ToLowerInvariant()
    $words = @{
        'id' = 'identificador'; 'pk' = 'clave'; 'pdf' = 'PDF'; 'excel' = 'Excel'
        'casa' = 'casa'; 'casas' = 'casas'; 'resena' = 'reseña'; 'resenas' = 'reseñas'
        'cedula' = 'cédula'; 'guardia' = 'guardia'; 'domicilio' = 'domicilio'
        'domiciliario' = 'domiciliario'; 'cartera' = 'cartera'; 'mora' = 'mora'
        'pago' = 'pago'; 'pagos' = 'pagos'; 'usuario' = 'usuario'; 'usuarios' = 'usuarios'
        'novedad' = 'novedad'; 'visitante' = 'visitante'; 'paquete' = 'paquete'
        'reporte' = 'reporte'; 'reportes' = 'reportes'; 'copia' = 'copia'; 'seguridad' = 'seguridad'
        'fecha' = 'fecha'; 'fechas' = 'fechas'; 'estado' = 'estado'; 'estados' = 'estados'
        'perfil' = 'perfil'; 'movimientos' = 'movimientos'; 'movimiento' = 'movimiento'
        'residente' = 'residente'; 'residentes' = 'residentes'; 'propietario' = 'propietario'
        'propietarios' = 'propietarios'; 'bitacora' = 'bitácora'; 'auditoria' = 'auditoría'
        'configuracion' = 'configuración'; 'configuraciones' = 'configuraciones'
        'dinero' = 'dinero'; 'saldo' = 'saldo'; 'saldos' = 'saldos'; 'filtro' = 'filtro'
        'filtros' = 'filtros'; 'formulario' = 'formulario'; 'form' = 'formulario'
        'prueba' = 'prueba'; 'tests' = 'pruebas'; 'test' = 'prueba'; 'admin' = 'administración'
        'view' = 'vista'; 'dashboard' = 'panel'; 'login' = 'inicio de sesión'; 'logout' = 'cierre de sesión'
        'cargar' = 'carga'; 'generar' = 'generación'; 'crear' = 'creación'; 'aplicar' = 'aplicación'
        'obtener' = 'obtención'; 'calcular' = 'cálculo'; 'validar' = 'validación'; 'filtrar' = 'filtrado'
        'construir' = 'construcción'; 'build' = 'construcción'; 'generate' = 'generación'
        'create' = 'creación'; 'get' = 'obtención'; 'set' = 'asignación'; 'save' = 'guardado'
        'clean' = 'validación'; 'format' = 'formateo'; 'formatear' = 'formateo'
        'render' = 'presentación'; 'registrar' = 'registro'; 'revisar' = 'revisión'
        'actualizar' = 'actualización'; 'procesar' = 'procesamiento'; 'exportar' = 'exportación'
        'eliminar' = 'eliminación'; 'editar' = 'edición'; 'iniciar' = 'inicio'
        'autorizar' = 'autorización'; 'responder' = 'respuesta'; 'enviar' = 'envío'
        'consultar' = 'consulta'; 'convertir' = 'conversión'; 'resumen' = 'resumen'
        'resumir' = 'resumen'; 'set up' = 'preparación'
        'nuevo' = 'nuevo'; 'nueva' = 'nueva'
    }
    $parts = @($text -split '\s+' | ForEach-Object { if ($words.ContainsKey($_)) { $words[$_] } else { $_ } })
    return ($parts -join ' ')
}

function Get-SymbolComment([string]$symbol, [bool]$isClass, [string]$relativePath) {
    if ($symbol -eq 'Migration') { return "Intención de la migración: $(Get-MigrationDescription ([IO.Path]::GetFileName($relativePath)))" }
    if ($isClass) {
        if ($symbol -eq 'Meta') { return 'Agrupa las opciones de configuración del modelo o formulario que contiene.' }
        if ($symbol -eq 'Command') { return 'Implementa la interfaz de línea de comandos para la operación administrativa de este módulo.' }
        if ($symbol -match 'Tests?$' -or $symbol -match 'TestCase$') { return "Agrupa pruebas automatizadas relacionadas con $(Convert-Name $symbol)." }
        if ($symbol -match 'Admin$') { return "Configura la consulta y presentación administrativa de $(Convert-Name $symbol)." }
        if ($symbol -match 'Form$|Field$|Mixin$') { return "Define campos y reglas reutilizables para $(Convert-Name $symbol)." }
        if ($relativePath -match 'models\.py$') { return "Representa $(Convert-Name $symbol) y define sus datos y relaciones persistentes." }
        return "Agrupa la lógica y responsabilidades de $(Convert-Name $symbol)."
    }
    if ($symbol -match '^test_') { return "Verifica el comportamiento de $(Convert-Name $symbol.Substring(5)) y sus condiciones relevantes." }
    if ($symbol -eq '__init__') { return 'Inicializa el objeto y configura los valores necesarios para su uso.' }
    if ($symbol -eq '__str__') { return 'Construye la representación textual legible del objeto.' }
    if ($symbol -match '^clean_') { return "Valida y normaliza el campo $(Convert-Name $symbol.Substring(6)) antes de aceptar el formulario." }
    if ($symbol -eq 'clean') { return 'Aplica validaciones relacionadas entre los campos y devuelve los datos depurados.' }
    if ($symbol -eq 'save') { return 'Persiste los datos del formulario y completa las actualizaciones asociadas.' }
    if ($symbol -match '^get_') { return "Obtiene $(Convert-Name $symbol.Substring(4)) para continuar el flujo de la aplicación." }
    if ($symbol -match '^set_') { return "Establece $(Convert-Name $symbol.Substring(4)) según el contexto recibido." }
    if ($symbol -match '^(is_|es_)') { return "Determina si se cumple la condición $(Convert-Name $symbol)." }
    if ($symbol -match '^(build_|construir)') { return "Reúne y estructura $(Convert-Name $symbol) para su consumo posterior." }
    if ($symbol -match '^(generate_|generar)') { return "Genera $(Convert-Name $symbol) a partir de los datos y filtros recibidos." }
    if ($symbol -match '^(create_|crear)') { return "Crea $(Convert-Name $symbol) y coordina los datos relacionados." }
    if ($symbol -match '^(update_|actualizar)') { return "Actualiza $(Convert-Name $symbol) conservando las reglas del dominio." }
    if ($symbol -match '^(filter_|filtrar)') { return "Filtra $(Convert-Name $symbol) conforme a los criterios de la solicitud." }
    if ($symbol -match '^(format_|formatear)') { return "Da formato a $(Convert-Name $symbol) para mostrarlo o exportarlo." }
    if ($symbol -match '^(validate_|validar)') { return "Comprueba $(Convert-Name $symbol) antes de continuar el proceso." }
    if ($symbol -match '(_view$|^index$|^login$|^logout_view$)') { return "Atiende la solicitud relacionada con $(Convert-Name $symbol) y prepara la respuesta de la vista." }
    if ($symbol -match '^(clean|formatear|obtener|aplicar|revisar|registrar|calcular|procesar|normalizar|color|intervalo|ruta|directorio|resumen|parse|_parse|_format|_apply|_hash|_archivos|_payment|_current|_summarize|_process|_date)') {
        return "Realiza la tarea de $(Convert-Name $symbol) y entrega el resultado al flujo que la invoca."
    }
    return "Organiza el flujo de $(Convert-Name $symbol) dentro de este módulo."
}

function Add-PythonComments([string]$text, [string]$relativePath) {
    $lines = [Collections.Generic.List[string]]::new()
    foreach ($line in [regex]::Split($text, '(?<=\n)')) { if ($line.Length -gt 0) { $lines.Add($line) } }
    if ($lines.Count -eq 0) { $lines.Add('') }
    $at = 0
    while ($at -lt $lines.Count -and ($lines[$at] -match '^\s*$' -or $lines[$at] -match '^\s*#')) { $at++ }
    if ($at -gt 0 -and $lines[0] -match '^#!') { }
    $docStart = -1
    if ($at -lt $lines.Count -and $lines[$at] -match '^\s*(?:r|u|R|U|br|rb|BR|RB)?"""') { $docStart = $at }
    if ($docStart -ge 0) {
        $quote = '"""'
        $docEnd = $docStart
        $occurrences = ([regex]::Matches($lines[$docStart], [regex]::Escape($quote))).Count
        while ($occurrences -lt 2 -and $docEnd + 1 -lt $lines.Count) {
            $docEnd++
            $occurrences += ([regex]::Matches($lines[$docEnd], [regex]::Escape($quote))).Count
        }
        if ($occurrences -ge 2) { $at = $docEnd + 1 }
    }
    $intent = ''
    if ($relativePath -match 'migrations\\') { $intent = "Intención de la migración: $(Get-MigrationDescription ([IO.Path]::GetFileName($relativePath)))" }
    $header = if ($intent) { "# $intent" } else { "# Módulo: $(Get-ModuleDescription $relativePath)" }
    if (-not ($text -match '(?m)^# (Módulo:|Intención de la migración:)')) {
        $lines.Insert($at, $header + $newline)
    }
    $text = $lines -join ''
    $pattern = '(?m)^(?<indent>[ \t]*)(?<decorators>(?:[ \t]*@[^\r\n]*(?:\r?\n|$))*)(?<declaration>[ \t]*(?:async[ \t]+)?(?<kind>def|class)[ \t]+(?<symbol>[A-Za-z_]\w*)[^\r\n]*)(?<ending>\r?\n|$)'
    $regex = [regex]::new($pattern)
    $text = $regex.Replace($text, [Text.RegularExpressions.MatchEvaluator]{
        param($match)
        $indent = $match.Groups['indent'].Value
        $symbol = $match.Groups['symbol'].Value
        $isClass = $match.Groups['kind'].Value -eq 'class'
        $comment = Get-SymbolComment $symbol $isClass $relativePath
        $decorators = $match.Groups['decorators'].Value
        $declaration = $match.Groups['declaration'].Value
        $ending = $match.Groups['ending'].Value
        return "$indent# $comment$ending$decorators$declaration$ending"
    })
    return $text
}

function Add-TemplateComments([string]$text, [string]$relativePath) {
    $result = [Collections.Generic.List[string]]::new()
    foreach ($line in [regex]::Split($text, '(?<=\n)')) {
        if ($line.Length -eq 0) { continue }
        $notes = [Collections.Generic.List[string]]::new()
        foreach ($match in [regex]::Matches($line, '\{%\s*(block|if|for|with|include|extends)\s+([^%]*?)%\}')) {
            $tag = $match.Groups[1].Value
            $detail = $match.Groups[2].Value.Trim()
            if ($tag -eq 'block') { $notes.Add("Define la sección de plantilla «$detail», que la vista base o hija completa.") }
            elseif ($tag -eq 'if') { $notes.Add("Muestra este contenido únicamente cuando se cumple la condición «$detail».") }
            elseif ($tag -eq 'for') { $notes.Add("Genera una sección repetida para cada elemento de «$detail».") }
            elseif ($tag -eq 'with') { $notes.Add("Prepara el contexto local «$detail» para los elementos siguientes.") }
            elseif ($tag -eq 'include') { $notes.Add("Inserta el fragmento reutilizable «$detail».") }
            elseif ($tag -eq 'extends') { $notes.Add("Hereda la estructura común definida en «$detail».") }
        }
        foreach ($match in [regex]::Matches($line, '<(nav|header|main|section|form|table|footer|aside|article)\b', 'IgnoreCase')) {
            $tag = $match.Groups[1].Value.ToLowerInvariant()
            $label = @{ nav='navegación'; header='encabezado'; main='contenido principal'; section='sección visual'; form='formulario de captura'; table='tabla de resultados'; footer='pie de página'; aside='panel complementario'; article='contenido independiente' }[$tag]
            $notes.Add("Esta estructura presenta el bloque de $label de la pantalla.")
        }
        if ($line -match '^\s*$' -and $notes.Count -eq 0) { $result.Add($line); continue }
        if ($notes.Count -gt 0 -and $line -notmatch '\{#') {
            $result.Add(($notes | ForEach-Object { "{# $_ #}" }) -join '')
        }
        $result.Add($line)
    }
    if ($result.Count -eq 0) { return "{# Módulo: $(Get-ModuleDescription $relativePath) #}" }
    $joined = $result -join ''
    if ($joined -notmatch '\{# Módulo:') {
        $header = "{# Módulo: $(Get-ModuleDescription $relativePath) #}"
        $joined = $header + $joined
    }
    return $joined
}

function Add-JavaScriptComments([string]$text) {
    $map = @{
        'updateActiveMenu' = 'Actualiza el enlace activo según la sección visible durante el desplazamiento.'
        'changeText' = 'Alterna los textos destacados del encabezado con una transición de salida y entrada.'
        'initializeServiceTabs' = 'Conecta las pestañas de servicios con el panel de contenido seleccionado.'
        'activateService' = 'Activa una pestaña y presenta el contenido del servicio que eligió la persona.'
        'initializeAboutFeatures' = 'Inicializa la interacción que cambia la imagen de las características.'
        'initializeNewsGallery' = 'Controla la revelación progresiva de las novedades de la galería.'
        'revealNews' = 'Muestra el siguiente grupo de novedades y actualiza la disponibilidad de carga.'
        'initializeReviewsGallery' = 'Prepara la galería de reseñas y su navegación progresiva.'
        'animateCounter' = 'Anima el contador hasta el valor final cuando el elemento entra en pantalla.'
        'observer' = 'Observa la entrada de elementos animados y activa la animación correspondiente.'
    }
    $pattern = '(?m)^(?<indent>[ \t]*)(?<decl>function[ \t]+(?<name>\w+)|(?:const|let|var)[ \t]+(?<arrow>\w+)[ \t]*=[ \t]*(?:\([^)]*\)|[A-Za-z_$][\w$]*)[ \t]*=>|(?:const|let|var)[ \t]+(?<obs>observer)[ \t]*=[ \t]*new[ \t]+IntersectionObserver)'
    return [regex]::Replace($text, $pattern, [Text.RegularExpressions.MatchEvaluator]{
        param($m)
        $name = $m.Groups['name'].Value
        if (-not $name) { $name = $m.Groups['arrow'].Value }
        if (-not $name) { $name = $m.Groups['obs'].Value }
        $comment = $map[$name]
        if (-not $comment) { $comment = "Gestiona el comportamiento asociado a «$name» dentro de la interfaz." }
        return "$($m.Groups['indent'].Value)// $comment$newline$($m.Groups['indent'].Value)$($m.Groups['decl'].Value)"
    })
}

function Add-CssComments([string]$text) {
    if ($text -notmatch 'Módulo:') { $text = "/* Módulo: reglas de estilo para la interfaz pública y los componentes de gestión. */$newline$text" }
    $result = [Collections.Generic.List[string]]::new()
    $section = ''
    foreach ($line in [regex]::Split($text, '(?<=\n)')) {
        if ($line.Length -eq 0) { continue }
        if ($line -match '^\s*/\*\s*(?<title>[^*]+?)\s*\*/') {
            $section = $Matches['title'].Trim()
            if ($section -and $section -notmatch '^(=+|[-= ]+)$' -and $section -notmatch '^Módulo:') {
                $result.Add("/* Esta sección reúne reglas visuales para $($section.Trim('- ')). */$newline")
            }
        }
        $result.Add($line)
    }
    return $result -join ''
}

function Add-SqlComments([string]$text) {
    $text = [regex]::Replace($text, '(?m)^CREATE DATABASE\b', "-- Crea el esquema lógico que contendrá las tablas de la aplicación.$newlineCREATE DATABASE")
    return [regex]::Replace($text, '(?m)^CREATE TABLE\s+(?<name>\w+)', {
        param($m)
        $name = $m.Groups['name'].Value
        $desc = @{
            propietario='personas propietarias y sus datos de contacto.'
            residente='personas residentes del conjunto.'
            casa='casas, ocupación, cartera y referencias a sus responsables.'
            guardia='guardias y la información asociada a sus turnos.'
            domicilio='datos de domiciliarios y de sus vehículos o negocios.'
            visitante='visitantes y datos del vehículo con el que ingresan.'
            paquete='paquetes recibidos y su información de seguimiento.'
            proceso='movimientos de acceso y sus relaciones con guardias, casas y registros asociados.'
            pago='pagos realizados o pendientes y la casa a la que pertenecen.'
            notas='notas registradas por el personal de guardia.'
        }[$name]
        if (-not $desc) { $desc = 'los registros principales de «' + $name + '».' }
        return "-- Define la tabla «$name» para almacenar $desc$newline" + $m.Value
    })
}

$files = Get-ChildItem -LiteralPath $root -File -Recurse | Where-Object {
    $_.Extension -in '.py', '.html', '.js', '.css', '.sql' -and
    $_.Name -notlike '*.pyc' -and
    $_.FullName -notmatch '\\backups?\\|\\media\\|\\evidencias?\\|\\__pycache__\\|\\\.git\\' -and
    $_.FullName -notmatch '\.sqlite3?$'
}
$documented = 0
$untouched = [Collections.Generic.List[string]]::new()
foreach ($file in $files) {
    $bytes = [IO.File]::ReadAllBytes($file.FullName)
    $encoding = [Text.UTF8Encoding]::new($false)
    $bom = $false
    if ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF) {
        $encoding = [Text.UTF8Encoding]::new($true); $bom = $true
    } elseif ($bytes.Length -ge 2 -and $bytes[0] -eq 0xFF -and $bytes[1] -eq 0xFE) {
        $encoding = [Text.UnicodeEncoding]::new($false, $true); $bom = $true
    } elseif ($bytes.Length -ge 2 -and $bytes[0] -eq 0xFE -and $bytes[1] -eq 0xFF) {
        $encoding = [Text.UnicodeEncoding]::new($true, $true); $bom = $true
    }
    $text = $encoding.GetString($bytes, $(if ($bom) { $encoding.GetPreamble().Length } else { 0 }), $bytes.Length - $(if ($bom) { $encoding.GetPreamble().Length } else { 0 }))
    if ($text.Contains("`r`n")) { $newline = "`r`n" } else { $newline = "`n" }
    $relativePath = $file.FullName.Substring($root.Length + 1)
    $updated = switch ($file.Extension.ToLowerInvariant()) {
        '.py' { Add-PythonComments $text $relativePath }
        '.html' { Add-TemplateComments $text $relativePath }
        '.js' { Add-JavaScriptComments $text }
        '.css' { Add-CssComments $text }
        '.sql' { Add-SqlComments $text }
    }
    if ($updated -ne $text) {
        $preamble = if ($bom) { $encoding.GetPreamble() } else { [byte[]]@() }
        $content = $encoding.GetBytes($updated)
        $output = [byte[]]::new($preamble.Length + $content.Length)
        if ($preamble.Length -gt 0) { [Array]::Copy($preamble, 0, $output, 0, $preamble.Length) }
        [Array]::Copy($content, 0, $output, $preamble.Length, $content.Length)
        [IO.File]::WriteAllBytes($file.FullName, $output)
        $documented++
    } else {
        $untouched.Add($relativePath)
    }
}
"Documentados: $documented de $($files.Count)"
if ($untouched.Count -gt 0) { 'Sin cambios: ' + ($untouched -join ', ') }
