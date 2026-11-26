# Módulo: Construye resúmenes y exportaciones de pagos y otros reportes.
from datetime import datetime
from decimal import Decimal
from io import BytesIO
from xml.sax.saxutils import escape

from django.contrib.staticfiles import finders
from django.db.models import Count, Q, Sum
from django.http import HttpResponse
from django.contrib.auth.models import User
from django.utils import timezone
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .models import Casa, CasaResidente, Domicilio, Guardia, Notas, Novedad, Paquete, Pago, Proceso, Propietario, Resena, Residente, Visitante


# Identificadores y etiquetas visibles admitidos por el selector de reportes.
REPORT_OPTIONS = (
    ('pagos', 'Pagos y cartera'),
    ('casas', 'Casas'),
    ('visitantes', 'Visitantes'),
    ('domicilios', 'Domicilios'),
    ('paquetes', 'Paquetes'),
    ('notas', 'Notas'),
    ('novedades', 'Novedades'),
    ('resenas', 'Reseñas'),
    ('usuarios', 'Usuarios'),
    ('movimientos', 'Movimientos'),
    ('residentes', 'Residentes'),
    ('propietarios', 'Propietarios'),
    ('guardias', 'Guardias'),
)

# Solo estos informes interpretan y reciben filtros temporales.
DATE_FILTER_REPORTS = (
    'pagos', 'visitantes', 'domicilios', 'paquetes', 'notas', 'novedades',
    'resenas', 'usuarios', 'movimientos',
)

# Informes que pueden limitar sus resultados a una vivienda.
HOUSE_FILTER_REPORTS = (
    'pagos', 'casas', 'visitantes', 'domicilios', 'paquetes', 'movimientos',
    'residentes', 'propietarios',
)

MONTH_NAMES_ES = (
    'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
    'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre',
)


def _draw_report_page_chrome(pdf_canvas, document, include_footer=True):
    logo_path = finders.find('core/images/logo.png')
    if not logo_path:
        raise FileNotFoundError('No se encontró el logo de la aplicación en los archivos estáticos.')
    logo = ImageReader(logo_path)
    image_width, image_height = logo.getSize()
    logo_width = 22 * mm
    logo_height = logo_width * image_height / image_width
    pdf_canvas.saveState()
    pdf_canvas.drawImage(
        logo,
        document.pagesize[0] - document.rightMargin - logo_width,
        document.pagesize[1] - 5 * mm - logo_height,
        width=logo_width,
        height=logo_height,
        mask='auto',
    )
    pdf_canvas.setStrokeColor(colors.HexColor('#d6e2df'))
    pdf_canvas.setLineWidth(.6)
    pdf_canvas.line(
        document.leftMargin,
        15 * mm,
        document.pagesize[0] - document.rightMargin,
        15 * mm,
    )
    if include_footer:
        pdf_canvas.setFillColor(colors.HexColor('#657773'))
        pdf_canvas.setFont('Helvetica', 8)
        pdf_canvas.drawString(document.leftMargin, 10 * mm, 'Urbanización Piemonte')
        pdf_canvas.drawRightString(
            document.pagesize[0] - document.rightMargin,
            10 * mm,
            f'Página {document.page}',
        )
    pdf_canvas.restoreState()


# Convierte una fecha ISO recibida del formulario; un valor vacío o inválido se interpreta como ausencia de filtro.
def _parse_date(value):
    try:
        return datetime.strptime(value, '%Y-%m-%d').date() if value else None
    except ValueError:
        return None


# Realiza la tarea de formateo money y entrega el resultado al flujo que la invoca.
def _format_money(value):
    # Presenta el importe sin decimales y usa puntos como separadores de miles en los reportes.
    return f'$ {value:,.0f}'.replace(',', '.')


# Presenta fechas y horas en la zona horaria configurada y con el formato local de la aplicación.
def _format_datetime(value):
    return timezone.localtime(value).strftime('%d/%m/%Y %H:%M')


# Extrae y convierte los extremos opcionales del intervalo solicitado por la página.
def _date_filters(request):
    return _parse_date(request.GET.get('desde')), _parse_date(request.GET.get('hasta'))


# Define la fecha de referencia del resumen usando el extremo más reciente o el día actual.
def _payment_date_details(desde, hasta):
    fecha_corte = hasta or desde or timezone.localdate()
    mes = MONTH_NAMES_ES[fecha_corte.month - 1]
    return {
        'fecha_etiqueta': 'Fecha de corte' if desde or hasta else 'Fecha de generación',
        'fecha_resumen': f'{fecha_corte.day} de {mes} ({fecha_corte.month:02d}) de {fecha_corte.year}',
    }


# Aplica límites inclusivos y convierte campos datetime a fecha cuando el filtro recibido no contiene hora.
def _apply_date_filters(queryset, field, desde, hasta, datetime_field=False):
    date_field = f'{field}__date' if datetime_field else field
    if desde:
        queryset = queryset.filter(**{f'{date_field}__gte': desde})
    if hasta:
        queryset = queryset.filter(**{f'{date_field}__lte': hasta})
    return queryset


# Obtiene pagos de casas con propietario y añade, cuando existen, los filtros de vivienda y fecha.
def _payment_queryset(casa_id, desde, hasta):
    queryset = Pago.objects.select_related('id_casa', 'id_casa__id_propietario').filter(
        id_casa__id_propietario__isnull=False,
    ).order_by('fecha', 'id_pago')
    if casa_id.isdigit():
        queryset = queryset.filter(id_casa_id=int(casa_id))
    return _apply_date_filters(queryset, 'fecha', desde, hasta)


# Realiza la tarea de current balances by house y entrega el resultado al flujo que la invoca.
def _current_balances_by_house(payments):
    house_ids = payments.values_list('id_casa_id', flat=True).distinct()
    houses = Casa.objects.filter(pk__in=house_ids)
    return {
        # El saldo por casa combina cartera y mora, con un mínimo de cero para no mostrar deuda negativa.
        house.pk: max(house.cartera + house.saldo_mora, 0)
        for house in houses
    }


# Agrega cantidades y valores pagados o pendientes, y calcula por separado la deuda actual de las casas consultadas.
def _summarize_payments(queryset):
    totals = queryset.aggregate(
        cantidad=Count('pk'),
        total=Sum('valor'),
        pagado=Sum('valor', filter=Q(estado='Pagado')),
        pendiente=Sum('valor', filter=~Q(estado='Pagado')),
    )
    current_balances = _current_balances_by_house(queryset)
    return {
        'cantidad': totals['cantidad'],
        'total': totals['total'] or 0,
        'pagado': totals['pagado'] or 0,
        'pendiente': totals['pendiente'] or 0,
        'saldo_actual': sum(current_balances.values()),
        'total_formatted': _format_money(totals['total'] or 0),
        'pagado_formatted': _format_money(totals['pagado'] or 0),
        'pendiente_formatted': _format_money(totals['pendiente'] or 0),
        'saldo_actual_formatted': _format_money(sum(current_balances.values())),
    }


# Construye el resumen financiero usando los mismos filtros que alimentan las filas del reporte de pagos.
def build_payment_summary(request):
    casa_id = request.GET.get('casa', '')
    desde, hasta = _date_filters(request)
    summary = _summarize_payments(_payment_queryset(casa_id, desde, hasta))
    summary.update(_payment_date_details(desde, hasta))
    return summary


# Exporta los pagos filtrados a una hoja Excel con encabezado, formato monetario y filtros de columna.
def generate_payments_excel(request):
    casa_id = request.GET.get('casa', '')
    desde, hasta = _date_filters(request)
    queryset = _payment_queryset(casa_id, desde, hasta)
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = 'Pagos'
    headers = ['Casas', 'Fecha mes', 'Fecha día', 'Valor mensual', 'Pagado (Sí o No)']
    worksheet.append(headers)
    for header_cell in worksheet[1]:
        header_cell.font = Font(bold=True, color='FFFFFF')
        header_cell.fill = PatternFill('solid', fgColor='173F3A')
        header_cell.alignment = Alignment(horizontal='center')

    for payment in queryset:
        month_label = f'{MONTH_NAMES_ES[payment.fecha.month - 1].capitalize()} {payment.fecha.year}'
        worksheet.append([
            payment.id_casa.numero_casa,
            month_label,
            payment.fecha.day,
            payment.valor,
            'Sí' if payment.estado == 'Pagado' else 'No',
        ])
        worksheet.cell(worksheet.max_row, 4).number_format = '"$" #,##0.00'

    widths = (14, 22, 14, 20, 20)
    for index, width in enumerate(widths, start=1):
        worksheet.column_dimensions[get_column_letter(index)].width = width
    worksheet.freeze_panes = 'A2'
    worksheet.auto_filter.ref = worksheet.dimensions

    output = BytesIO()
    workbook.save(output)
    response = HttpResponse(
        output.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    response['Content-Disposition'] = 'attachment; filename="reporte_pagos.xlsx"'
    return response


# Filtra procesos por casa y fecha, tratando el campo de fecha como fecha-hora.
def _process_filters(queryset, casa_id, desde, hasta):
    if casa_id.isdigit():
        queryset = queryset.filter(id_casa_id=int(casa_id))
    return _apply_date_filters(queryset, 'fecha', desde, hasta, datetime_field=True)


# Traduce cada tipo de informe a encabezados y filas, aplicando solo los filtros admitidos para ese tipo.
def build_report_rows(request, report_type):
    casa_id = request.GET.get('casa', '') if report_type in HOUSE_FILTER_REPORTS else ''
    desde, hasta = _date_filters(request) if report_type in DATE_FILTER_REPORTS else (None, None)
    rows = []
    title = dict(REPORT_OPTIONS).get(report_type, 'Reporte')

    if report_type == 'pagos':
        queryset = _payment_queryset(casa_id, desde, hasta)
        saldos_actuales = _current_balances_by_house(queryset)
        for item in queryset:
            rows.append([
                f'Casa {item.id_casa.numero_casa}',
                item.id_casa.id_propietario and f'{item.id_casa.id_propietario.nombre} {item.id_casa.id_propietario.apellido}' or 'Sin propietario',
                item.fecha.strftime('%d/%m/%Y'),
                item.estado,
                _format_money(item.valor),
                _format_money(saldos_actuales.get(item.id_casa_id, 0)),
            ])
        return title, ['Casa', 'Propietario', 'Fecha', 'Estado', 'Valor', 'Saldo actual'], rows

    if report_type == 'casas':
        queryset = Casa.objects.select_related('id_propietario', 'id_residente').order_by('numero_casa')
        if casa_id.isdigit():
            queryset = queryset.filter(pk=int(casa_id))
        for item in queryset:
            rows.append([f'Casa {item.numero_casa}', item.estado, str(item.cantidad_residentes), _format_money(item.cartera), item.id_propietario and f'{item.id_propietario.nombre} {item.id_propietario.apellido}' or 'Sin propietario'])
        return title, ['Casa', 'Estado', 'Residentes', 'Cartera', 'Propietario'], rows

    if report_type == 'movimientos':
        queryset = _process_filters(Proceso.objects.select_related('id_casa').order_by('fecha', 'id_proceso'), casa_id, desde, hasta)
        for item in queryset:
            rows.append([_format_datetime(item.fecha), f'Casa {item.id_casa.numero_casa}', item.tipo, item.nombre, item.get_estado_display()])
        return title, ['Fecha', 'Casa', 'Tipo', 'Nombre', 'Estado'], rows

    if report_type in ('visitantes', 'domicilios', 'paquetes'):
        model_map = {'visitantes': ('id_visitante', 'Visitante'), 'domicilios': ('id_domicilio', 'Domicilio'), 'paquetes': ('id_paquete', 'Paquete')}
        relation, process_type = model_map[report_type]
        processes = _process_filters(
            Proceso.objects.filter(**{f'{relation}__isnull': False, 'tipo': process_type})
            .select_related(relation, 'id_casa')
            .order_by('fecha', 'id_proceso'),
            casa_id,
            desde,
            hasta,
        )
        for proceso in processes:
            item = getattr(proceso, relation)
            casa = f'Casa {proceso.id_casa.numero_casa}' if proceso else 'No asociada'
            fecha = _format_datetime(proceso.fecha) if proceso else ''
            if report_type == 'visitantes':
                rows.append([fecha, casa, item.nombre + ' ' + item.apellido, item.cedula, item.tipo_v or 'Sin tipo', item.vehiculo_tipo or 'Peatonal'])
            elif report_type == 'domicilios':
                rows.append([fecha, casa, item.nombre + ' ' + item.apellido, item.telefono_negocio, item.descripcion_negocio or '', item.vehiculo_tipo or ''])
            else:
                rows.append([fecha, casa, item.nombre + ' ' + item.apellido, item.transportadora, item.guia or '', 'Con evidencia' if item.evidencia else 'Sin evidencia'])
        headers = {
            'visitantes': ['Fecha', 'Casa', 'Nombre', 'Documento', 'Tipo', 'Vehículo'],
            'domicilios': ['Fecha', 'Casa', 'Nombre', 'Teléfono', 'Descripción', 'Vehículo'],
            'paquetes': ['Fecha', 'Casa', 'Destinatario', 'Transportadora', 'Guía', 'Evidencia'],
        }[report_type]
        return title, headers, rows

    if report_type == 'notas':
        queryset = Notas.objects.select_related('id_guardia').order_by('fecha', 'id_nota')
        queryset = _apply_date_filters(queryset, 'fecha', desde, hasta, datetime_field=True)
        for item in queryset:
            rows.append([item.fecha.strftime('%d/%m/%Y'), f'{item.nombre} {item.apellido}', item.nota, item.id_guardia and str(item.id_guardia) or ''])
        return title, ['Fecha', 'Persona', 'Nota', 'Guardia'], rows

    if report_type == 'novedades':
        queryset = Novedad.objects.select_related('registrado_por').order_by('fecha_suceso', 'id_novedad')
        queryset = _apply_date_filters(queryset, 'fecha_suceso', desde, hasta, datetime_field=True)
        for item in queryset:
            rows.append([timezone.localtime(item.fecha_suceso).strftime('%d/%m/%Y %H:%M'), item.titulo, item.tipo, item.nota, 'Con evidencia' if item.evidencia else 'Sin evidencia'])
        return title, ['Fecha', 'Título', 'Tipo', 'Descripción', 'Evidencia'], rows

    if report_type == 'resenas':
        queryset = Resena.objects.select_related('usuario').order_by('fecha_creacion', 'id_resena')
        queryset = _apply_date_filters(queryset, 'fecha_creacion', desde, hasta, datetime_field=True)
        for item in queryset:
            rows.append([_format_datetime(item.fecha_creacion), item.nombre, str(item.calificacion), item.comentario, 'Aprobada' if item.aprobada else 'Pendiente'])
        return title, ['Fecha', 'Nombre', 'Calificación', 'Comentario', 'Estado'], rows

    if report_type == 'usuarios':
        queryset = _apply_date_filters(User.objects.order_by('date_joined', 'username'), 'date_joined', desde, hasta, datetime_field=True)
        for item in queryset:
            rows.append([_format_datetime(item.date_joined), item.username, item.get_full_name() or 'Sin nombre', item.email or '', 'Administrador' if item.is_staff else 'Usuario', 'Activo' if item.is_active else 'Inactivo'])
        return title, ['Fecha de registro', 'Usuario', 'Nombre', 'Correo', 'Rol', 'Estado'], rows

    model_map = {
        'residentes': (Residente, 'id_residente', ['Cédula', 'Nombre', 'Apellido', 'Teléfono']),
        'propietarios': (Propietario, 'id_propietario', ['Cédula', 'Nombre', 'Apellido', 'Correo']),
        'guardias': (Guardia, 'id_guardia', ['Cédula', 'Nombre', 'Apellido', 'Turno']),
    }
    model, order_field, headers = model_map[report_type]
    queryset = model.objects.all().order_by(order_field)
    if casa_id.isdigit():
        if report_type == 'residentes':
            casa = Casa.objects.filter(pk=int(casa_id)).first()
            if not casa:
                return title, ['Casa'] + headers, []
            residente_ids = CasaResidente.objects.filter(casa_id=casa.pk).values_list('residente_id', flat=True)
            queryset = queryset.filter(Q(pk=casa.id_residente_id) | Q(pk__in=residente_ids))
        else:
            casa = Casa.objects.filter(pk=int(casa_id)).first()
            if not casa or report_type == 'guardias':
                return title, ['Casa'] + headers, []
            queryset = queryset.filter(pk=casa.id_propietario_id)
    for item in queryset:
        if report_type == 'residentes':
            casas = item.casas.order_by('numero_casa')
            rows.append([', '.join(f'Casa {casa.numero_casa}' for casa in casas) or 'No asociada', str(item.cedula), item.nombre, item.apellido, item.telefono or ''])
        elif report_type == 'propietarios':
            casas = item.casas.order_by('numero_casa')
            rows.append([', '.join(f'Casa {casa.numero_casa}' for casa in casas) or 'No asociada', str(item.cedula), item.nombre, item.apellido, item.correo])
        else:
            rows.append(['No asociada', str(item.cedula), item.nombre, item.apellido, item.turno or ''])
    headers = ['Casa'] + headers
    return title, headers, rows


# Genera un PDF imprimible; el informe de pagos agrega el resumen financiero y los demás presentan sus filas tabulares.
def generate_report_pdf(request, report_type):
    title, headers, rows = build_report_rows(request, report_type)
    casa_id = request.GET.get('casa', '') if report_type in HOUSE_FILTER_REPORTS else ''
    desde, hasta = _date_filters(request) if report_type in DATE_FILTER_REPORTS else (None, None)
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=12 * mm,
        leftMargin=12 * mm,
        topMargin=32 * mm,
        bottomMargin=20 * mm,
        title=f'{title} - Urbanización Piemonte',
        author='Urbanización Piemonte',
    )
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='ReportKicker', parent=styles['Normal'], textColor=colors.HexColor('#657773'), fontName='Helvetica-Bold', fontSize=8, leading=10, spaceAfter=1 * mm))
    styles.add(ParagraphStyle(name='ReportTitle', parent=styles['Title'], alignment=TA_LEFT, textColor=colors.HexColor('#173f3a'), fontSize=20, leading=24, spaceAfter=1 * mm))
    styles.add(ParagraphStyle(name='ReportSubtitle', parent=styles['Normal'], textColor=colors.HexColor('#657773'), fontSize=9, leading=12))
    styles.add(ParagraphStyle(name='Small', parent=styles['Normal'], textColor=colors.HexColor('#52615e'), fontSize=8, leading=11))
    story = [
        Paragraph('URBANIZACIÓN PIEMONTE', styles['ReportKicker']),
        Paragraph(escape(title), styles['ReportTitle']),
        Paragraph('Informe administrativo', styles['ReportSubtitle']),
        Spacer(1, 6 * mm),
    ]
    filtros = []
    if casa_id:
        casa = Casa.objects.filter(pk=casa_id).first()
        if casa:
            filtros.append(f'Casa: {casa.numero_casa}')
    if desde:
        filtros.append('Desde: ' + desde.strftime('%d/%m/%Y'))
    if hasta:
        filtros.append('Hasta: ' + hasta.strftime('%d/%m/%Y'))
    if filtros:
        story.append(Paragraph(' | '.join(filtros), styles['Small']))
        story.append(Spacer(1, 4 * mm))
    if report_type == 'pagos':
        queryset = _payment_queryset(casa_id, desde, hasta)
        payment_totals = _summarize_payments(queryset)
        payment_totals.update(_payment_date_details(desde, hasta))
        if not queryset.exists():
            story.append(Paragraph('No hay pagos para los filtros seleccionados.', styles['Normal']))
        payment_table = Table(
            [headers] + rows if rows else [headers, ['Sin registros'] + [''] * (len(headers) - 1)],
            repeatRows=1,
            colWidths=[24 * mm, 50 * mm, 24 * mm, 22 * mm, 30 * mm, 36 * mm],
        )
        payment_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#173f3a')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), .35, colors.HexColor('#b8c9c5')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#eef4f2')]),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('ALIGN', (-2, 1), (-1, -1), 'RIGHT'),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ]))
        story.extend([payment_table, Spacer(1, 6 * mm)])
        payment_summary = Table([
            ['RESUMEN DEL MES', 'VALOR'],
            ['Total registrado', _format_money(payment_totals['total'])],
            ['Total pagado', _format_money(payment_totals['pagado'])],
            ['Pagos no confirmados', _format_money(payment_totals['pendiente'])],
            ['Saldo actual de las casas incluidas', _format_money(payment_totals['saldo_actual'])],
        ], colWidths=[130 * mm, 48 * mm])
        payment_summary.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), .5, colors.black),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#173f3a')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
            ('ALIGN', (1, 1), (1, -1), 'RIGHT'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('TOPPADDING', (0, 0), (-1, -1), 7),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
        ]))
        story.extend([
            payment_summary,
            Spacer(1, 4 * mm),
            Paragraph(
                f'{payment_totals["fecha_etiqueta"]}: {payment_totals["fecha_resumen"]}',
                styles['Small'],
            ),
            Spacer(1, 2 * mm),
            Paragraph(f'Total de recibos: {payment_totals["cantidad"]} | Generado: {timezone.localtime().strftime("%d/%m/%Y %H:%M")}', styles['Small']),
        ])
        document.build(story, onFirstPage=_draw_report_page_chrome, onLaterPages=_draw_report_page_chrome)
        response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
        response['Content-Disposition'] = 'inline; filename="reporte_pagos.pdf"'
        return response
    data = [headers] + rows if rows else [headers, ['Sin registros'] + [''] * (len(headers) - 1)]
    table = Table(data, repeatRows=1, colWidths=[None] * len(headers))
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#173f3a')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.35, colors.HexColor('#b8c9c5')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#eef4f2')]),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (-2, 1), (-1, -1), 'RIGHT'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(table)
    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph(f'Total de registros: {len(rows)} | Generado: {timezone.localtime().strftime("%d/%m/%Y %H:%M")}', styles['Small']))
    document.build(story, onFirstPage=_draw_report_page_chrome, onLaterPages=_draw_report_page_chrome)
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="reporte_{report_type}.pdf"'
    return response


# Emite el comprobante individual y distingue el desglose confirmado del documento de pago todavía pendiente.
def generate_payment_receipt_pdf(payment):
    owner = payment.id_casa.id_propietario
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=15 * mm,
        leftMargin=15 * mm,
        topMargin=32 * mm,
        bottomMargin=20 * mm,
        title=f'{"Recibo de pago" if payment.estado == "Pagado" else "Comprobante de pago pendiente"} - Urbanización Piemonte',
        author='Urbanización Piemonte',
    )
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name='ReceiptTitle',
        parent=styles['Title'],
        alignment=TA_LEFT,
        textColor=colors.HexColor('#173f3a'),
        fontSize=20,
        leading=24,
        spaceAfter=1 * mm,
    ))
    styles.add(ParagraphStyle(name='ReceiptKicker', parent=styles['Normal'], textColor=colors.HexColor('#657773'), fontName='Helvetica-Bold', fontSize=12, leading=10, spaceAfter=1 * mm))
    styles.add(ParagraphStyle(name='ReceiptSubtitle', parent=styles['Normal'], textColor=colors.HexColor('#657773'), fontSize=9, leading=12))
    styles.add(ParagraphStyle(name='ReceiptSmall', parent=styles['Normal'], fontSize=8, leading=11))
    month = MONTH_NAMES_ES[payment.fecha.month - 1]
    owner_name = f'{owner.nombre} {owner.apellido}' if owner else 'Propietario no registrado'
    pago_confirmado = payment.estado == 'Pagado'
    # Los importes aplicados se registran al confirmar; en comprobantes históricos sin desglose se trata el pago como capital.
    mora_cubierta = payment.valor_mora_aplicada if pago_confirmado else Decimal('0.00')
    capital_cubierto = payment.valor_cartera_aplicada if pago_confirmado else Decimal('0.00')
    saldo_favor_aplicado = payment.valor_saldo_favor_aplicado if pago_confirmado else Decimal('0.00')
    if pago_confirmado and capital_cubierto == 0 and mora_cubierta == 0:
        capital_cubierto = payment.valor
    saldo_capital = max(payment.id_casa.cartera, 0)
    saldo_mora = max(payment.id_casa.saldo_mora, 0)
    # El saldo total es la suma de los componentes no negativos que siguen pendientes en la casa.
    saldo_total = saldo_capital + saldo_mora
    details = [
        ['PROPIETARIO', owner_name, 'RECIBO N.º', str(payment.pk)],
        ['CASA', str(payment.id_casa.numero_casa), 'FECHA DE PAGO', payment.fecha.strftime('%d/%m/%Y')],
        ['MES DEL PAGO', f'{month.capitalize()} de {payment.fecha.year}', 'ESTADO', payment.estado.upper()],
    ]
    detail_table = Table(details, colWidths=[35 * mm, 55 * mm, 35 * mm, 55 * mm])
    detail_table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), .5, colors.HexColor('#52615e')),
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#eef4f2')),
        ('BACKGROUND', (2, 0), (2, -1), colors.HexColor('#eef4f2')),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 9),
    ]))
    if pago_confirmado:
        concepts = [
            ['DETALLE DEL PAGO', 'VALOR'],
            ['Administracion Pagada', _format_money(capital_cubierto)],
            ['Intereses cobrados por Mora (2%)', _format_money(mora_cubierta)],
            ['Saldo a favor', _format_money(saldo_favor_aplicado)],
            ['TOTAL RECIBIDO', _format_money(payment.valor)],
            ['Saldo Pendiente', _format_money(saldo_capital)],
            ['Saldo Total Administracion', _format_money(saldo_total)],
        ]
        receipt_title = 'RECIBO DE PAGO - ADMINISTRACIÓN'
        receipt_closing = 'Este documento certifica que el pago indicado fue recibido y confirmado.'
    else:
        concepts = [
            ['DETALLE DEL PAGO', 'VALOR'],
            ['Pago propuesto', _format_money(payment.valor)],
            ['Intereses por Mora pendientes (2%)', _format_money(saldo_mora)],
            ['Saldo Pendiente', _format_money(saldo_capital)],
            ['Saldo Total Administracion', _format_money(saldo_total)],
        ]
        receipt_title = 'COMPROBANTE DE PAGO PENDIENTE'
        receipt_closing = 'Este documento corresponde a un pago pendiente; no certifica recepción de dinero.'
    concepts_table = Table(concepts, colWidths=[125 * mm, 55 * mm])
    concepts_table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), .5, colors.HexColor('#52615e')),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#173f3a')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTNAME', (0, -2), (-1, -1), 'Helvetica-Bold'),
        ('ALIGN', (1, 1), (1, -1), 'RIGHT'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('TOPPADDING', (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 9),
    ]))
    story = [
        Paragraph('URBANIZACIÓN PIEMONTE', styles['ReceiptKicker']),
        Paragraph('Recibo de pago - Administracion' if pago_confirmado else 'Comprobante de pago pendiente', styles['ReceiptTitle']),
        Paragraph('NIT 811.546.980', styles['ReceiptSubtitle']),
        Spacer(1, 8 * mm),
        detail_table,
        Spacer(1, 8 * mm),
        concepts_table,
        Spacer(1, 8 * mm),
        Paragraph(receipt_closing, styles['Normal']),
        Spacer(1, 2 * mm),
        Paragraph(f'Generado: {timezone.localtime().strftime("%d/%m/%Y %H:%M")}', styles['ReceiptSmall']),
    ]
    receipt_page_chrome = lambda canvas, doc: _draw_report_page_chrome(canvas, doc, include_footer=False)
    document.build(story, onFirstPage=receipt_page_chrome, onLaterPages=receipt_page_chrome)
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="recibo_pago_{payment.pk}.pdf"'
    return response
