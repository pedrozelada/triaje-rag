"""Generación de informes PDF (ReportLab) para el historial de triaje.

Los imports de reportlab son diferidos dentro de la función generadora para que
el router de informes siga funcionando aunque falte la librería en el servidor.
"""

from datetime import datetime
from io import BytesIO
from xml.sax.saxutils import escape as _xml_escape

# Paleta Manchester — espejo de frontend/src/utils/colores.ts
COLOR_MANCHESTER_HEX = {
    "rojo": "#EF4444",
    "naranja": "#F97316",
    "amarillo": "#EAB308",
    "verde": "#22C55E",
    "azul": "#3B82F6",
    "sin_clasificar": "#9CA3AF",
}

NIVEL_LABEL = {
    "rojo": "Rojo — Emergencia",
    "naranja": "Naranja — Urgencia Mayor",
    "amarillo": "Amarillo — Urgencia Menor",
    "verde": "Verde — No Urgente",
    "azul": "Azul — Autosanamiento",
    "sin_clasificar": "Sin clasificar",
}

# Niveles con fondo oscuro usan texto blanco para contraste
FONDO_OSCURO = {"rojo", "naranja", "azul"}

SEXO_LABEL = {"M": "Masculino", "F": "Femenino", "Otro": "Otro"}

_AZUL_600 = "#2563EB"


def _pie_de_pagina(canvas, doc):
    """Pie de página: identificación del sistema + numeración."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm

    canvas.saveState()
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColorRGB(0.42, 0.45, 0.50)  # gris medio
    ancho = A4[0]
    canvas.drawString(2 * cm, 1.1 * cm, "Sistema de Triaje NNAC Bolivia — Informe de Triaje")
    canvas.drawRightString(ancho - 2 * cm, 1.1 * cm, f"Página {canvas.getPageNumber()}")
    canvas.restoreState()


def _parrafo(texto, estilo):
    """Paragraph escapando XML y preservando saltos de línea."""
    from reportlab.platypus import Paragraph

    if texto is None or str(texto).strip() == "":
        return Paragraph("—", estilo)
    return Paragraph(_xml_escape(str(texto)).replace("\n", "<br/>"), estilo)


def _fmt_tiempo(valor):
    if valor is None:
        return "—"
    return f"{float(valor):.2f} s"


def _signos_vitales(c):
    """Fila compacta con los signos vitales registrados (los ausentes se omiten)."""
    partes = []
    if c.temperatura is not None:
        partes.append(f"T° {float(c.temperatura):.1f} °C")
    if c.presion_sistolica is not None and c.presion_diastolica is not None:
        partes.append(f"PA {int(c.presion_sistolica)}/{int(c.presion_diastolica)} mmHg")
    if c.frecuencia_cardiaca is not None:
        partes.append(f"FC {int(c.frecuencia_cardiaca)} lpm")
    if c.frecuencia_respiratoria is not None:
        partes.append(f"FR {int(c.frecuencia_respiratoria)} rpm")
    if c.spo2 is not None:
        partes.append(f"SpO2 {int(c.spo2)} %")
    return "  ·  ".join(partes)


def _bloque_consulta(idx, c, base, ancho_util):
    """Construye la barra de encabezado de una consulta con su color Manchester."""
    from reportlab.lib import colors
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import Paragraph, Table, TableStyle

    nivel = c.nivel_urgencia or "sin_clasificar"
    fondo = colors.HexColor(COLOR_MANCHESTER_HEX.get(nivel, COLOR_MANCHESTER_HEX["sin_clasificar"]))
    texto_barra = colors.white if nivel in FONDO_OSCURO else colors.HexColor("#1F2937")
    fecha = c.fecha_hora.strftime("%d/%m/%Y %H:%M") if c.fecha_hora else "Sin fecha"

    barra_estilo = ParagraphStyle(
        "barra", parent=base["Normal"], fontSize=10, leading=13, textColor=texto_barra
    )
    barra = Table(
        [[Paragraph(
            f"<b>Consulta {idx}</b>   ·   {fecha}   ·   {NIVEL_LABEL.get(nivel, nivel)}",
            barra_estilo,
        )]],
        colWidths=[ancho_util],
    )
    barra.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), fondo),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return barra


def generar_pdf_informe_paciente(paciente, consultas, usuario) -> bytes:
    """Genera el PDF del historial de triaje de un paciente y devuelve los bytes."""
    try:
        from reportlab import rl_config
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import cm
        from reportlab.platypus import (
            HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
        )
    except ImportError as exc:  # pragma: no cover - entorno sin reportlab
        raise RuntimeError(
            "Generación de PDF no disponible: falta la librería 'reportlab' en el servidor."
        ) from exc

    # Sin compresión: permite buscar y copiar texto dentro del PDF
    rl_config.pageCompression = 0

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        title="Informe de Triaje — Historial del Paciente",
        author=usuario.nombre_completo,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=1.5 * cm,
        bottomMargin=2 * cm,
    )
    ancho_util = A4[0] - 4 * cm

    base = getSampleStyleSheet()
    est_title = ParagraphStyle("titulo", parent=base["Title"], fontSize=15, leading=19, textColor=colors.HexColor(_AZUL_600))
    est_meta = ParagraphStyle("meta", parent=base["Normal"], fontSize=8.5, leading=11, textColor=colors.HexColor("#6B7280"))
    est_normal = ParagraphStyle("normal", parent=base["Normal"], fontSize=9, leading=12.5, textColor=colors.HexColor("#374151"))
    est_mono = ParagraphStyle("mono", parent=base["Normal"], fontName="Courier", fontSize=7.8, leading=10.5, textColor=colors.HexColor("#374151"))
    est_seccion = ParagraphStyle("seccion", parent=base["Heading2"], fontSize=11, leading=14, textColor=colors.HexColor("#374151"), spaceBefore=8, spaceAfter=2)

    story = [
        Paragraph("INFORME DE TRIAJE — HISTORIAL DEL PACIENTE", est_title),
        HRFlowable(width="100%", thickness=1, color=colors.HexColor(_AZUL_600), spaceAfter=8),
        Paragraph(
            f"Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}"
            f"   ·   Generado por: {usuario.nombre_completo}",
            est_meta,
        ),
        Spacer(1, 8),
    ]

    # Datos del paciente (2 columnas)
    edad = paciente.edad if paciente.edad is not None else "—"
    sexo = SEXO_LABEL.get(paciente.sexo, paciente.sexo)
    datos = [
        [Paragraph(f"<b>Paciente:</b> {paciente.apellido}, {paciente.nombre}", est_normal),
         Paragraph(f"<b>C.I.:</b> {paciente.ci}", est_normal)],
        [Paragraph(f"<b>Edad:</b> {edad} años", est_normal),
         Paragraph(f"<b>Sexo:</b> {sexo}", est_normal)],
        [Paragraph(f"<b>Total de consultas:</b> {len(consultas)}", est_normal),
         Paragraph("", est_normal)],
    ]
    tabla = Table(datos, colWidths=[ancho_util / 2, ancho_util / 2])
    tabla.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LINEBELOW", (0, -1), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
    ]))
    story += [
        tabla,
        Paragraph("Historial de Consultas", est_seccion),
        HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#E5E7EB"), spaceAfter=6),
    ]

    if not consultas:
        story.append(Paragraph("<i>Sin consultas registradas.</i>", est_normal))

    for i, c in enumerate(consultas, 1):
        story.append(_bloque_consulta(i, c, base, ancho_util))
        story.append(Spacer(1, 5))
        story.append(Paragraph(
            f"<b>Modelo:</b> {c.modelo_utilizado or 'N/D'}"
            f"   ·   <b>Tiempo de respuesta:</b> {_fmt_tiempo(c.tiempo_respuesta)}"
            f"   ·   <b>Tokens:</b> {c.tokens_consumidos if c.tokens_consumidos is not None else '—'}",
            est_normal,
        ))
        if c.motivo_consulta:
            story += [Paragraph("<b>Motivo de consulta:</b>", est_normal), _parrafo(c.motivo_consulta, est_normal)]
        if c.sintomas:
            story += [Paragraph("<b>Síntomas:</b>", est_normal), _parrafo(c.sintomas, est_normal)]
        vitales = _signos_vitales(c)
        if vitales:
            story.append(Paragraph(f"<b>Signos vitales:</b> {vitales}", est_normal))
        if c.respuesta_llm:
            story += [
                Paragraph("<b>Resultado de la evaluación (IA):</b>", est_normal),
                _parrafo(c.respuesta_llm, est_mono),
            ]
        if c.prompt_utilizado:
            story += [
                Paragraph("<b>Prompt utilizado:</b>", est_normal),
                _parrafo(c.prompt_utilizado, est_mono),
            ]
        story.append(Spacer(1, 10))

    doc.build(story, onFirstPage=_pie_de_pagina, onLaterPages=_pie_de_pagina)
    return buffer.getvalue()
