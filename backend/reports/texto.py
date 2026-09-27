"""Informe de historial de paciente en texto plano.

Es el formato que usa el panel para "ver" el informe antes de descargarlo, así
que incluye la auditoría (prompt y respuesta del modelo) tal cual quedó
guardada.
"""

from datetime import datetime

SEPARADOR = "=" * 50


def informe_de_paciente(paciente, consultas, usuario) -> str:
    """Arma el informe en texto plano de un paciente y sus consultas."""
    lineas = [
        "INFORME DE TRIAJE - HISTORIAL DEL PACIENTE",
        SEPARADOR,
        f"Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}",
        f"Generado por: {usuario.nombre_completo}",
        f"Filtro: Paciente #{paciente.id}",
        "",
        f"Paciente: {paciente.nombre} {paciente.apellido}",
        f"C.I.: {paciente.ci}",
        f"Edad: {paciente.edad} años   Sexo: {paciente.sexo}",
        f"Total de consultas: {len(consultas)}",
        "",
    ]
    for i, consulta in enumerate(consultas, 1):
        lineas.extend(_bloque_consulta(i, consulta))
    return "\n".join(lineas)


def _bloque_consulta(indice: int, consulta) -> list[str]:
    """Líneas de una consulta, con su auditoría si existe."""
    fecha = (
        consulta.fecha_hora.strftime("%Y-%m-%d %H:%M") if consulta.fecha_hora else "?"
    )
    lineas = [
        f"--- Consulta {indice} ({fecha}) ---",
        f"Nivel de urgencia: {consulta.nivel_urgencia or 'N/D'}",
        f"Modelo: {consulta.modelo_utilizado or 'N/D'}",
        f"Tiempo: {consulta.tiempo_respuesta}s  Tokens: {consulta.tokens_consumidos}",
    ]
    if consulta.respuesta_llm:
        lineas.append("Resultado:")
        lineas.append(consulta.respuesta_llm)
    if consulta.prompt_utilizado:
        lineas.append("Prompt utilizado (auditoría):")
        lineas.append(consulta.prompt_utilizado)
    lineas.append("")
    return lineas
