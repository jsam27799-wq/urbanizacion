def _figure(filename, alt, caption, labels):
    return {
        "src": f"core/images/manual-operativo/{filename}",
        "alt": alt,
        "caption": caption,
        "labels": labels,
    }


def _chapter(identifier, title, summary, steps, figures=(), table="", actions=(), notice=""):
    return {
        "id": identifier,
        "title": title,
        "summary": summary,
        "steps": steps,
        "figures": figures,
        "table": table,
        "actions": actions,
        "notice": notice,
    }


_PROFILE = _chapter(
    "perfil",
    "Menú de cuenta y perfil",
    "Desde el menú de cuenta puedes revisar tus datos, actualizar la contraseña o cerrar la sesión.",
    [
        ("Abrir el menú", "Selecciona tu nombre o icono de usuario en la parte superior del panel y elige Perfil."),
        ("Guardar datos personales", "Actualiza los campos de contacto disponibles y usa Guardar cambios. Revisa el aviso de resultado antes de salir."),
        ("Cambiar contraseña", "Completa la sección de contraseña con la clave actual y la nueva contraseña; guarda el cambio y vuelve a iniciar sesión si la página lo solicita."),
    ],
    figures=[
        _figure("04-menu-sesion.png", "Menú de cuenta del panel", "Acceso al perfil y cierre de sesión.", ["A · Perfil", "B · Cerrar sesión"]),
        _figure("05-perfil.png", "Formulario de perfil", "Datos personales y controles para guardarlos.", ["A · Datos del perfil", "B · Guardar cambios"]),
        _figure("06-perfil-confirmacion.png", "Sección de seguridad del perfil", "Formulario de actualización de contraseña.", ["A · Contraseña actual", "B · Nueva contraseña", "C · Guardar contraseña"]),
    ],
    actions=[
        ("Guardar cambios", "Aplica los datos personales editados."),
        ("Actualizar contraseña", "Cambia la clave de acceso; no crea ni elimina la cuenta."),
        ("Cerrar sesión", "Finaliza la sesión actual."),
    ],
)

_GUARD_PROFILE = _chapter(
    "perfil",
    "Menú de cuenta y perfil",
    "Desde el menú de Guardia puedes revisar tus datos, actualizar la contraseña o cerrar la sesión.",
    [
        ("Abrir el menú", "Selecciona el botón con tu usuario en la parte superior del panel y elige Perfil."),
        ("Guardar datos personales", "Actualiza los campos de contacto disponibles y usa Guardar cambios. Revisa el aviso de resultado antes de salir."),
        ("Cambiar contraseña", "Completa la sección de contraseña con la clave actual y la nueva contraseña; guarda el cambio y vuelve a iniciar sesión si la página lo solicita."),
    ],
    figures=[
        _figure("08-dashboard-guardia.png", "Panel con el menú y la cuenta de Guardia", "La captura corresponde a la vista de Guardia; el botón de usuario abre el acceso al perfil.", ["A · Usuario de Guardia", "B · Menú operativo permitido"]),
    ],
    actions=[
        ("Guardar cambios", "Aplica los datos personales editados."),
        ("Actualizar contraseña", "Cambia la clave de acceso; no crea ni elimina la cuenta."),
        ("Cerrar sesión", "Finaliza la sesión actual."),
    ],
)

_OWNER_PROFILE = _chapter(
    "perfil",
    "Cuenta y perfil del propietario",
    "La navegación interna del Propietario muestra únicamente Pagos. Desde el botón de cuenta puedes abrir Perfil o cerrar sesión.",
    [
        ("Abrir el menú", "Selecciona el botón de cuenta en la parte superior y elige Perfil. El menú lateral de este rol se limita a Pagos."),
        ("Guardar datos personales", "Actualiza los campos de contacto disponibles y usa Guardar cambios. Revisa el aviso de resultado antes de salir."),
        ("Cambiar contraseña", "Completa la sección de contraseña con la clave actual y la nueva contraseña; guarda el cambio y vuelve a iniciar sesión si la página lo solicita."),
    ],
    figures=[
        _figure("04-menu-cuenta-propietario.png", "Opciones de cuenta del propietario", "Accesos a Perfil y Cerrar sesión; la captura no incluye navegación administrativa.", ["A · Perfil", "B · Cerrar sesión"]),
    ],
    actions=[
        ("Guardar cambios", "Aplica los datos personales editados."),
        ("Actualizar contraseña", "Cambia la clave de acceso; no crea ni elimina la cuenta."),
        ("Cerrar sesión", "Finaliza la sesión actual."),
    ],
)


_ADMIN_DASHBOARD = _chapter(
    "dashboard",
    "Dashboard y movimientos recientes",
    "El Dashboard resume la actividad y ofrece accesos a los módulos autorizados. La información visible depende de la fecha y de los registros existentes.",
    [
        ("Leer los indicadores", "Revisa las tarjetas de resumen y su periodo. Selecciona una tarjeta únicamente si ofrece un enlace al detalle."),
        ("Consultar movimientos", "En la tabla de actividad reciente abre el detalle para revisar el registro. Usa Todos los movimientos para buscar por fechas, casa o tipo de módulo."),
        ("Gestionar un registro", "El Dashboard es de consulta; para crear, editar o eliminar, entra al módulo correspondiente desde el menú lateral."),
    ],
    figures=[
        _figure("07-dashboard-admin.png", "Dashboard de Administrador", "Resumen general y accesos de administración.", ["A · Indicadores", "B · Menú lateral"]),
        _figure("09-movimientos-recientes.png", "Tabla de movimientos recientes", "Actividad reciente y acceso al detalle del movimiento.", ["A · Fecha, módulo y estado", "B · Casa y responsable", "C · Ver detalle"]),
    ],
    table="La tabla de movimientos muestra fecha y hora, módulo, estado, nombre del registro, casa, descripción y responsable. Todos los movimientos añade filtros por rango o fecha exacta, mes, año, casa y tipo; sus resultados se consultan, no se editan desde esta pantalla.",
    actions=[
        ("Todos los movimientos", "Abre la bitácora con filtros y detalle de cada evento."),
        ("Ver detalle", "Muestra la información extendida del movimiento seleccionado."),
        ("Menú lateral", "Abre el módulo donde se administra cada registro."),
    ],
)

_GUARD_DASHBOARD = _chapter(
    "dashboard",
    "Dashboard y movimientos recientes",
    "El panel de Guardia reúne indicadores operativos y accesos a los registros de acceso y entregas permitidos para su cuenta.",
    [
        ("Revisar el resumen", "Consulta las tarjetas operativas y la actividad reciente al iniciar el turno."),
        ("Buscar un movimiento", "Abre el detalle en la tabla. Si necesitas un periodo concreto, entra a Todos los movimientos y aplica sus filtros."),
        ("Registrar o actualizar", "Usa Visitantes, Domiciliarios, Paquetes o Notas. Los datos administrativos y financieros no se gestionan desde el Dashboard."),
    ],
    figures=[
        _figure("08-dashboard-guardia.png", "Dashboard de Guardia", "Indicadores operativos y menú disponible para Guardia.", ["A · Indicadores del turno", "B · Módulos operativos"]),
    ],
    table="La tabla de movimientos presenta los eventos que la cuenta puede consultar. Todos los movimientos permite filtrar por fechas, casa o módulo; desde allí se revisan detalles, no se modifica el registro original.",
    actions=[
        ("Ver detalle", "Consulta los datos del movimiento seleccionado."),
        ("Todos los movimientos", "Abre el historial filtrable disponible para la cuenta."),
        ("Módulos del menú", "Abre las pantallas donde se registran o actualizan las tareas operativas."),
    ],
)


_ADMIN_USERS = _chapter(
    "usuarios",
    "Usuarios y cuentas de acceso",
    "El Administrador crea cuentas para los perfiles disponibles y administra el acceso de las cuentas existentes.",
    [
        ("Crear una cuenta", "Escribe el nombre de usuario, selecciona el rol y completa los campos solicitados para ese tipo de cuenta."),
        ("Completar datos del rol", "Para un propietario vincula el registro de persona y sus casas disponibles. Para un guardia completa sus datos de identificación y turno."),
        ("Guardar y verificar", "Define la contraseña respetando los requisitos que muestra el formulario y selecciona Crear cuenta. Revisa el mensaje de resultado."),
        ("Administrar cuentas", "En la tabla localiza la cuenta y usa el control de activación o restablecimiento de contraseña que aparece en su fila."),
    ],
    figures=[
        _figure("10-crear-cuenta.png", "Formulario de creación de cuenta", "Selección de usuario y rol.", ["A · Nombre de usuario", "B · Rol"]),
        _figure("11-formulario-cuenta.png", "Datos asociados a la cuenta", "Campos que cambian según el rol seleccionado.", ["A · Persona vinculada", "B · Casas disponibles y seleccionadas", "C · Requisitos de contraseña"]),
        _figure("41-cuentas-tabla.png", "Listado de cuentas", "Estado y acciones disponibles por cuenta.", ["A · Cuenta y rol", "B · Activar o desactivar", "C · Restablecer contraseña"]),
    ],
    table="La tabla permite localizar cuentas y revisar su rol y estado. En este módulo las acciones son activar/desactivar y restablecer la contraseña; no se elimina una cuenta desde esta tabla.",
    actions=[
        ("Crear cuenta", "Guarda una cuenta nueva con el rol y los datos requeridos."),
        ("Activar / desactivar", "Habilita o suspende el acceso sin borrar la cuenta."),
        ("Restablecer contraseña", "Inicia el proceso de cambio de clave de esa cuenta."),
    ],
    notice="No es posible desactivar la cuenta con la que se está usando la sesión. Confirma la identidad y el rol antes de crear o cambiar una cuenta.",
)


_ADMIN_PEOPLE = _chapter(
    "personas",
    "Propietarios y residentes",
    "Registra y actualiza el directorio de personas vinculadas a la urbanización y a sus casas.",
    [
        ("Registrar una persona", "Completa identificación, nombres, contacto y rol. Si seleccionas Otros, escribe el rol solicitado por el formulario."),
        ("Buscar en el directorio", "Combina el filtro de tipo, número de cédula y casa; usa Buscar para aplicar los criterios."),
        ("Revisar o editar", "Abre el detalle para confirmar la persona y las casas asociadas. Selecciona Editar para corregir datos y Guardar para aplicar los cambios."),
        ("Eliminar cuando corresponda", "Usa Eliminar en la fila y confirma la operación. La acción retira el registro del directorio."),
    ],
    figures=[
        _figure("12-propietario-residente.png", "Formulario de propietario o residente", "Datos personales y tipo de vínculo.", ["A · Tipo de persona", "B · Identificación y contacto", "C · Guardar"]),
        _figure("13-asignacion-casas.png", "Asignación de casas", "Selección de casas disponibles y casas vinculadas.", ["A · Casas disponibles", "B · Casas seleccionadas"]),
        _figure("14-residentes-tabla.png", "Tabla del directorio", "Búsqueda, detalle y mantenimiento de personas.", ["A · Filtros de tipo, cédula y casa", "B · Ver detalle", "C · Editar o eliminar"]),
    ],
    table="La tabla incluye cédula, nombre, teléfono, correo, rol, casas y acciones. En propietarios se ofrecen detalle, edición y eliminación; en residentes del directorio se ofrecen edición y eliminación. Los filtros se aplican con Buscar y se limpian con el botón de reinicio.",
    actions=[
        ("Guardar", "Crea el registro o guarda los cambios del formulario."),
        ("Ver detalle", "Consulta datos y casas asociadas sin modificarlos."),
        ("Editar", "Carga los datos para corregirlos; guarda para confirmar."),
        ("Eliminar", "Borra el registro tras la confirmación del navegador."),
    ],
)


_ADMIN_HOUSES = _chapter(
    "casas",
    "Casas y asignaciones",
    "Mantén el inventario de casas y las relaciones con sus propietarios y residentes.",
    [
        ("Crear una casa", "Completa el número de casa y los datos que solicita el formulario; selecciona Guardar."),
        ("Registrar varias casas", "Usa la opción de carga por lote, ingresa los números en el formato que indica la pantalla y confirma el registro."),
        ("Buscar y actualizar", "Filtra la tabla por número de casa. Edita el registro para cambiar los datos o la asignación y guarda."),
        ("Eliminar con cuidado", "Usa Eliminar y confirma. Si la casa tiene pagos asociados, el sistema bloquea la eliminación."),
    ],
    figures=[
        _figure("15-casa-formulario.png", "Formulario de casa", "Campos para registrar o actualizar una casa.", ["A · Número y datos de la casa", "B · Guardar"]),
        _figure("16-casas-lote.png", "Registro por lote", "Entrada para crear varias casas en una operación.", ["A · Lista de números", "B · Registrar lote"]),
        _figure("17-casas-tabla.png", "Tabla de casas", "Casas registradas y controles de mantenimiento.", ["A · Número y estado", "B · Editar", "C · Eliminar"]),
    ],
    table="La tabla permite localizar casas y revisar sus datos y vínculos. Usa los controles de la fila para editar o eliminar; los cambios se aplican al guardar el formulario.",
    actions=[
        ("Guardar casa", "Crea una casa o aplica las modificaciones del formulario."),
        ("Registrar lote", "Crea varias casas a partir de la lista proporcionada."),
        ("Editar", "Permite corregir los datos disponibles de la casa."),
        ("Eliminar", "Borra una casa únicamente si no tiene pagos asociados."),
    ],
    notice="Antes de borrar una casa, verifica que su número y sus relaciones sean correctos. Una casa con pagos asociados no puede eliminarse.",
)


_GUARD_VISITORS = _chapter(
    "visitantes",
    "Visitantes y control de ingreso",
    "Registra los ingresos de visitantes y consulta su información y estado desde el listado.",
    [
        ("Registrar el ingreso", "Completa los datos de identificación, la casa y el tipo de ingreso; agrega datos del vehículo cuando el formulario los solicite."),
        ("Guardar el registro", "Selecciona Guardar. La cuenta de Guardia queda asociada al movimiento según la sesión activa."),
        ("Consultar el listado", "Filtra por los datos disponibles, abre Ver detalle para confirmar la información y usa Editar para actualizar el estado del ingreso o salida."),
        ("Eliminar si es necesario", "Elimina desde la fila correspondiente y confirma la operación."),
    ],
    figures=[
        _figure("18-visitante-formulario.png", "Formulario de visitante", "Identificación, destino y datos de ingreso.", ["A · Datos de la persona", "B · Casa de destino", "C · Datos del vehículo cuando aplican"]),
        _figure("20-visitante-detalle.png", "Detalle de un registro de visitante", "Información asociada al ingreso.", ["A · Datos del visitante", "B · Estado y hora", "C · Responsable"]),
        _figure("21-visitantes-tabla.png", "Tabla de visitantes", "Búsqueda y acciones del registro.", ["A · Filtros", "B · Ver detalle", "C · Editar o eliminar"]),
    ],
    table="El listado reúne los visitantes registrados y sus datos de ingreso. Aplica los filtros de la pantalla para localizar una persona o una casa; abre el detalle antes de cambiar el estado o borrar el registro.",
    actions=[
        ("Guardar", "Registra el ingreso con los datos del formulario."),
        ("Ver detalle", "Muestra los datos guardados del visitante."),
        ("Editar", "Permite actualizar los campos de estado disponibles, incluida la salida cuando corresponda."),
        ("Eliminar", "Retira el registro después de confirmar."),
    ],
    notice="Verifica identidad y casa de destino antes de guardar. La guía no presupone una preautorización móvil: utiliza únicamente las opciones que aparecen en la pantalla.",
)


_GUARD_DELIVERIES = _chapter(
    "domiciliarios",
    "Domiciliarios",
    "Registra el ingreso de una entrega y actualiza su estado al finalizar la atención.",
    [
        ("Registrar al domiciliario", "Completa nombre, empresa o servicio, datos del vehículo cuando apliquen y casa de destino."),
        ("Guardar y atender", "Guarda el ingreso. La aplicación registra la hora y muestra el estado o tiempo configurado para el seguimiento."),
        ("Cerrar la atención", "En la fila del registro usa la acción disponible para marcar la entrega atendida; revisa el resultado y el estado."),
        ("Consultar o corregir", "Usa filtros y detalle para localizar el registro. Edita o elimina solo si corresponde y confirma los cambios."),
    ],
    figures=[
        _figure("22-domiciliario-formulario.png", "Formulario de domiciliario", "Información de la entrega y su destino.", ["A · Datos del domiciliario", "B · Vehículo", "C · Casa y autorización"]),
        _figure("23-domiciliarios-tabla.png", "Tabla de domiciliarios", "Estado de atención y acciones del registro.", ["A · Hora y estado", "B · Marcar como atendido", "C · Detalle, editar o eliminar"]),
    ],
    table="La tabla permite consultar domicilios y su seguimiento. Revisa el estado antes de cerrar la atención. Los tiempos dependen de la configuración vigente; no se debe asumir un límite fijo.",
    actions=[
        ("Guardar", "Registra el ingreso del domiciliario."),
        ("Marcar atendido", "Cierra el seguimiento cuando la atención haya terminado."),
        ("Ver detalle / Editar", "Consulta o actualiza los campos permitidos."),
        ("Eliminar", "Retira el registro tras confirmar."),
    ],
)


_GUARD_PACKAGES = _chapter(
    "paquetes",
    "Paquetes",
    "Registra los paquetes recibidos, su casa de destino y las acciones realizadas para contactar a la persona correspondiente.",
    [
        ("Registrar el paquete", "Ingresa transportadora, guía o remitente, destino, persona autorizada y los datos de contacto solicitados."),
        ("Adjuntar soporte", "Si el formulario ofrece evidencia, selecciona el archivo requerido y guarda el registro."),
        ("Actualizar estado", "Localiza el paquete y usa Editar para cambiar los campos de estado disponibles. Registra el resultado de la llamada cuando el formulario lo solicite."),
        ("Consultar o eliminar", "Usa Ver detalle para revisar los datos. Elimina solo el registro correcto y confirma."),
    ],
    figures=[
        _figure("24-paquete-formulario.png", "Formulario de paquete", "Datos de recepción, destino y contacto.", ["A · Remitente y guía", "B · Casa y persona autorizada", "C · Evidencia y guardar"]),
        _figure("25-paquete-edicion.png", "Edición de paquete", "Actualización de la información y el estado.", ["A · Estado del paquete", "B · Resultado del contacto", "C · Guardar cambios"]),
        _figure("26-paquetes-tabla.png", "Tabla de paquetes", "Listado, filtros y acciones por paquete.", ["A · Destino y estado", "B · Ver detalle", "C · Editar o eliminar"]),
    ],
    table="La tabla organiza los paquetes por casa, fecha y estado, según las columnas de la pantalla. Utiliza filtros para encontrarlos y abre el detalle para revisar la evidencia y el contacto.",
    actions=[
        ("Guardar", "Registra el paquete y los datos de recepción."),
        ("Editar", "Actualiza los datos y opciones de estado disponibles."),
        ("Ver detalle", "Consulta la información completa del registro."),
        ("Eliminar", "Retira el paquete después de confirmar."),
    ],
    notice="El sistema muestra los estados disponibles en el formulario. No se debe prometer una alerta automática por abandono si la pantalla no la ofrece.",
)


_GUARD_NOTES = _chapter(
    "notas",
    "Notas internas",
    "Usa Notas para dejar información operativa que necesite consultar el equipo autorizado.",
    [
        ("Crear una nota", "Completa el asunto o descripción y los datos de contacto o casa que solicite el formulario."),
        ("Guardar y revisar", "Selecciona Guardar y verifica el mensaje de confirmación. Evita incluir información que no sea necesaria para la operación."),
        ("Buscar y mantener", "Filtra la tabla, abre el detalle y usa Editar para corregir. Elimina una nota solo cuando sea necesario y confirma."),
    ],
    figures=[
        _figure("32-nota-formulario.png", "Formulario de nota interna", "Campos de la nota y acción para guardarla.", ["A · Descripción", "B · Datos relacionados", "C · Guardar"]),
    ],
    table="La tabla presenta las notas registradas y las acciones disponibles para consultarlas, editarlas o eliminarlas. Utiliza los filtros de la pantalla cuando estén disponibles.",
    actions=[
        ("Guardar", "Crea la nota o aplica los cambios editados."),
        ("Ver detalle", "Consulta el contenido de la nota."),
        ("Editar", "Corrige el texto o la información asociada."),
        ("Eliminar", "Borra la nota tras confirmar."),
    ],
)


_ADMIN_PAYMENTS = _chapter(
    "pagos",
    "Pagos y cartera",
    "Administra los pagos registrados, revisa los soportes y consulta el saldo de las casas.",
    [
        ("Registrar un pago", "Selecciona la casa y completa periodo, valor, fecha, estado y soporte según los campos visibles."),
        ("Revisar el listado", "Filtra por casa o fecha y comprueba el estado del pago antes de editarlo."),
        ("Abrir el soporte", "Usa el detalle o el enlace de recibo disponible para verificar el comprobante y los datos del pago."),
        ("Editar o eliminar", "Si el registro requiere corrección, abre Editar y guarda los cambios. Al eliminar, confirma la operación; los pagos confirmados afectan el saldo y la cartera."),
    ],
    figures=[
        _figure("27-pago-formulario.png", "Formulario para registrar un pago", "Campos del pago y soporte.", ["A · Casa y periodo", "B · Valor, fecha y estado", "C · Soporte"]),
        _figure("28-pagos-tabla.png", "Tabla de pagos", "Estado, filtros y acciones por registro.", ["A · Filtros", "B · Estado y saldo", "C · Detalle, edición o recibo"]),
        _figure("30-recibo-pago.png", "Recibo de pago", "Comprobante imprimible del registro.", ["A · Datos del pago", "B · Casa y periodo", "C · Descargar o imprimir"]),
    ],
    table="El listado muestra pagos y permite filtrar según las opciones de la pantalla. Revisa estado, casa, periodo y soporte; el saldo de cartera descuenta únicamente los pagos que el sistema considera confirmados.",
    actions=[
        ("Guardar", "Crea el pago o guarda una corrección."),
        ("Ver recibo", "Abre el comprobante para imprimirlo o guardarlo."),
        ("Editar", "Actualiza los datos del pago."),
        ("Eliminar", "Elimina el registro tras confirmar y puede cambiar el saldo calculado."),
    ],
    notice="Confirma el soporte y el estado antes de registrar. No marques un pago como confirmado hasta verificarlo.",
)


_OWNER_PAYMENTS = _chapter(
    "pagos",
    "Pagos de mi casa",
    "Consulta el saldo y el historial de la casa vinculada a tu cuenta y registra nuevos pagos con el soporte solicitado.",
    [
        ("Revisar el saldo", "Consulta el resumen de cartera y los pagos visibles para la casa asociada a tu cuenta."),
        ("Registrar un pago", "Completa el periodo, valor, fecha y soporte que pide el formulario; selecciona Guardar."),
        ("Verificar el registro", "En la tabla revisa el estado que tiene registrado el pago. Abre el detalle o recibo cuando esos controles estén disponibles."),
        ("Solicitar una corrección", "Si hay un error, contacta al Administrador. El Propietario no puede editar ni eliminar pagos desde esta pantalla."),
    ],
    figures=[
        _figure("27-pago-formulario.png", "Formulario para registrar pago", "Campos para reportar un pago asociado a la casa.", ["A · Periodo y valor", "B · Fecha y soporte", "C · Guardar"]),
        _figure("30-recibo-pago.png", "Recibo de pago", "Vista del comprobante para consulta o impresión.", ["A · Resumen", "B · Información de casa y pago", "C · Imprimir o guardar"]),
    ],
    table="El historial corresponde a la casa vinculada a la cuenta. Consulta los pagos y su estado; las acciones de edición y eliminación son administrativas y no aparecen disponibles para Propietarios.",
    actions=[
        ("Guardar pago", "Envía el registro y soporte al sistema para su revisión."),
        ("Consultar", "Revisa el estado y los datos guardados."),
        ("Ver recibo", "Abre el comprobante si está disponible."),
    ],
    notice="Enviar un pago no significa que ya esté confirmado. El estado que aparece en el historial es el que debe tomarse como referencia.",
)


_ADMIN_NEWS = _chapter(
    "novedades",
    "Novedades",
    "Publica y mantiene avisos o eventos que se muestran en la página pública.",
    [
        ("Crear una novedad", "Completa título, descripción, fecha y los campos que muestre el formulario; guarda para publicarla."),
        ("Revisar la lista", "Consulta las novedades existentes y sus fechas. Usa los filtros disponibles para encontrar una."),
        ("Editar o retirar", "Edita el contenido y guarda el cambio. Eliminar retira la novedad; confirma que seleccionaste la correcta."),
    ],
    figures=[
        _figure("31-novedad-formulario.png", "Formulario de novedad", "Información de la publicación y acción de guardar.", ["A · Título y descripción", "B · Fecha del evento", "C · Guardar"]),
    ],
    table="La tabla permite localizar publicaciones y utilizar las acciones visibles para editarlas o eliminarlas. Las novedades se muestran en la página pública según su fecha y estado.",
    actions=[
        ("Guardar", "Crea una novedad o guarda una modificación."),
        ("Editar", "Actualiza el contenido o la fecha."),
        ("Eliminar", "Retira la publicación después de confirmar."),
    ],
)


_ADMIN_REVIEWS = _chapter(
    "resenas",
    "Reseñas",
    "Modera las reseñas enviadas desde la página pública antes de mostrarlas en el sitio.",
    [
        ("Consultar las reseñas", "Abre el módulo y revisa el texto, autor y estado de cada reseña."),
        ("Moderar", "Usa las acciones que aparecen en la fila para aprobar o retirar la reseña. Revisa el resultado en la lista."),
        ("Comprobar la página pública", "Las reseñas aprobadas son las que se muestran en la sección pública de reseñas."),
    ],
    figures=[
        _figure("33-resena-publica.png", "Formulario público de reseña", "La reseña se envía desde la página pública y queda sujeta a moderación.", ["A · Nombre", "B · Comentario", "C · Enviar reseña"]),
    ],
    table="El módulo administrativo muestra las reseñas recibidas y sus controles de moderación. La captura adjunta ilustra el formulario público de envío; la tabla de moderación está dentro del panel de Administrador.",
    actions=[
        ("Aprobar", "Autoriza que la reseña aparezca en la página pública."),
        ("Ocultar o eliminar", "Retira la reseña de la publicación según el control disponible."),
    ],
    notice="Una reseña enviada no aparece públicamente hasta que su estado de aprobación lo permita.",
)


_ADMIN_REPORTS = _chapter(
    "reportes",
    "Reportes",
    "Consulta información consolidada por módulo, casa y periodo; esta pantalla genera salidas de consulta, no edita los registros originales.",
    [
        ("Seleccionar el módulo", "Elige el tipo de reporte. La pantalla muestra únicamente los filtros aplicables a esa selección."),
        ("Aplicar filtros", "Selecciona una casa o todas las casas y, cuando estén disponibles, las fechas desde y hasta."),
        ("Consultar y exportar", "Usa Consultar información para cargar la tabla; genera PDF para abrir una versión imprimible. El reporte de pagos también ofrece Excel."),
    ],
    figures=[
        _figure("36-reportes-filtros.png", "Filtros del centro de reportes", "Selección del módulo y criterios de consulta.", ["A · Módulo del reporte", "B · Casa", "C · Periodo"]),
        _figure("37-reporte-pdf.png", "Reporte generado", "Resultado tabular y opciones de descarga.", ["A · Resumen", "B · Tabla de resultados", "C · PDF y Excel para pagos"]),
    ],
    table="Los resultados incluyen solo registros que coinciden con los filtros y muestran su cantidad. El resumen de pagos diferencia total registrado, pagado, pendiente y saldo actual; el detalle del saldo depende de las reglas mostradas en pantalla.",
    actions=[
        ("Consultar información", "Muestra los resultados en la tabla."),
        ("Generar PDF", "Abre el documento para guardar o imprimir."),
        ("Descargar Excel", "Disponible para el reporte de pagos."),
        ("Limpiar filtros", "Restablece los campos del formulario."),
    ],
)


_ADMIN_HISTORY = _chapter(
    "historial",
    "Historial de movimientos",
    "Consulta la bitácora de cambios y eventos de los módulos para conocer qué ocurrió y cuándo.",
    [
        ("Definir el periodo", "Filtra por rango de fechas, día, mes o año. También puedes limitar por casa y tipo de módulo."),
        ("Buscar el evento", "Selecciona Filtrar y revisa fecha, tipo, estado, registro, casa, información y responsable."),
        ("Abrir detalles", "Usa el icono de ojo para ver los datos ampliados del movimiento."),
    ],
    figures=[
        _figure("38-historial.png", "Historial filtrable", "Filtros y tabla de eventos registrados.", ["A · Fechas y módulo", "B · Casa y tipo de movimiento", "C · Detalle"]),
    ],
    table="Es una vista de consulta. La tabla muestra los eventos disponibles para los filtros seleccionados y no ofrece edición o eliminación de los registros originales.",
    actions=[
        ("Filtrar", "Aplica los criterios de fecha, casa y módulo."),
        ("Limpiar filtros", "Vuelve a la consulta sin criterios seleccionados."),
        ("Ver detalle", "Abre los datos ampliados del evento."),
    ],
)


_ADMIN_BACKUPS = _chapter(
    "copias",
    "Copias de seguridad y restauración",
    "Configura copias automáticas, crea respaldos manuales y administra restauraciones desde el panel de Administrador.",
    [
        ("Programar copias", "Define intervalo, unidad, activación y carpeta de destino; selecciona Guardar cambios. La ejecución automática requiere el Programador de tareas de Windows configurado para ejecutar el comando que indica la pantalla."),
        ("Crear respaldo manual", "Usa Crear copia ahora para guardar un ZIP del proyecto completo, o Crear copia de información para respaldar solo la base de datos."),
        ("Subir o restaurar", "El ZIP del proyecto se valida y almacena, pero no reemplaza el programa en ejecución. La restauración de información fusiona datos y requiere confirmar la operación."),
        ("Revisar y administrar", "Consulta la lista de respaldos y sus fechas. Usa las acciones disponibles para descargar o eliminar el archivo correcto."),
    ],
    figures=[
        _figure("39-copias-seguridad.png", "Panel de copias de seguridad", "Programación, respaldos manuales y opciones de información.", ["A · Intervalo y carpeta", "B · Crear copia completa", "C · Copia o restauración de información"]),
    ],
    table="La lista separa los respaldos completos de los que contienen solo información. Revisa tipo, nombre, fecha y tamaño antes de descargar o eliminar.",
    actions=[
        ("Guardar cambios", "Aplica la programación y la carpeta de destino."),
        ("Crear copia ahora", "Genera un ZIP manual del proyecto completo."),
        ("Crear copia de información", "Genera un respaldo solo de la base de datos."),
        ("Subir ZIP del proyecto", "Valida y guarda el archivo; no restaura el programa activo."),
        ("Subir y fusionar", "Importa información desde un archivo con confirmación y copia preventiva."),
    ],
    notice="La restauración de información fusiona datos con los actuales; no equivale a reemplazar el proyecto completo. La recuperación de un ZIP del proyecto se realiza fuera de la aplicación.",
)


_ADMIN_SETTINGS = _chapter(
    "configuracion",
    "Configuración de cartera y estados",
    "Define las reglas que afectan los cálculos de cartera, los tiempos de seguimiento y la presentación de estados.",
    [
        ("Configurar cartera", "Revisa porcentaje de mora, aumento mensual y día de vencimiento. Cambia los valores solo con autorización y guarda."),
        ("Definir tiempos", "Configura los parámetros de seguimiento que aparezcan para entregas y otros módulos."),
        ("Personalizar estados", "Edita nombre, color u opciones de estado disponibles y guarda los cambios."),
        ("Verificar", "Regresa al módulo relacionado y comprueba cómo se aplicó la configuración."),
    ],
    figures=[
        _figure("29-configuracion-cartera.png", "Configuración de cartera", "Reglas de mora y administración mensual.", ["A · Porcentaje de mora", "B · Aumento mensual", "C · Día de vencimiento"]),
        _figure("40-configuracion-estados.png", "Configuración de estados", "Parámetros de presentación para los módulos.", ["A · Módulo o grupo", "B · Estado y color", "C · Guardar cambios"]),
    ],
    table="La pantalla organiza los ajustes por módulo. Cada formulario muestra el valor actual; conserva el formato y rango aceptado por los campos, guarda y verifica en la pantalla de operación correspondiente.",
    actions=[
        ("Guardar cambios", "Aplica los valores del formulario."),
        ("Volver", "Sale de la configuración sin sustituir el botón Guardar para aplicar cambios."),
    ],
    notice="Modificar cartera o estados puede alterar cálculos y etiquetas visibles para otros usuarios. Confirma los valores antes de guardar.",
)


_OWNER_COMMUNITY = _chapter(
    "comunidad",
    "Página pública, reseñas y contacto",
    "Además de tu panel, puedes consultar información pública de la urbanización y utilizar los canales que estén habilitados.",
    [
        ("Consultar la página pública", "Abre la página principal para leer novedades y la información publicada por la Administración."),
        ("Enviar una reseña", "Completa el formulario público y envíalo. La reseña queda pendiente de moderación antes de publicarse."),
        ("Ubicación y ayuda", "Consulta el mapa y utiliza los medios de soporte que la página muestre. El asistente responde dentro de las opciones disponibles."),
    ],
    figures=[
        _figure("33-resena-publica.png", "Formulario público de reseña", "Campos para compartir una opinión con la administración.", ["A · Nombre", "B · Comentario", "C · Enviar"]),
        _figure("34-contacto-mapa.png", "Mapa y contacto", "Información pública de ubicación y contacto.", ["A · Mapa", "B · Datos de contacto"]),
        _figure("35-chatbot.png", "Ayuda en la página pública", "Acceso al asistente o canal de ayuda visible.", ["A · Abrir ayuda", "B · Escribir o elegir una consulta"]),
    ],
    table="La página pública presenta contenido informativo y no permite gestionar los registros internos de visitantes, paquetes o pagos.",
    actions=[
        ("Enviar reseña", "Envía un comentario sujeto a moderación."),
        ("Consultar mapa", "Abre la ubicación publicada."),
        ("Abrir ayuda", "Muestra el canal de asistencia disponible."),
    ],
    notice="Para registrar un pago, consulta el módulo Pagos del panel autenticado. No compartas contraseñas ni datos bancarios en reseñas o mensajes públicos.",
)


MANUAL_MODULES = {
    "administrador": (
        _PROFILE,
        _ADMIN_DASHBOARD,
        _ADMIN_USERS,
        _ADMIN_PEOPLE,
        _ADMIN_HOUSES,
        _GUARD_VISITORS,
        _GUARD_DELIVERIES,
        _GUARD_PACKAGES,
        _GUARD_NOTES,
        _ADMIN_PAYMENTS,
        _ADMIN_NEWS,
        _ADMIN_REVIEWS,
        _ADMIN_REPORTS,
        _ADMIN_HISTORY,
        _ADMIN_BACKUPS,
        _ADMIN_SETTINGS,
    ),
    "guardia": (
        _GUARD_PROFILE,
        _GUARD_DASHBOARD,
        _GUARD_VISITORS,
        _GUARD_DELIVERIES,
        _GUARD_PACKAGES,
        _GUARD_NOTES,
    ),
    "propietario": (
        _OWNER_PROFILE,
        _OWNER_PAYMENTS,
        _OWNER_COMMUNITY,
    ),
}
