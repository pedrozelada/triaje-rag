"""Interfaz Streamlit que actúa como CLIENTE de la API FastAPI del backend.

El motor RAG ahora vive en el backend; esta UI solo consume los endpoints
REST (pacientes, triage, informes) vía httpx.
"""

import logging

import httpx
import streamlit as st

logger = logging.getLogger(__name__)

# URL base del backend FastAPI (ajustable vía env).
API_BASE = "http://localhost:8000/api"

# Estilos por nivel de urgencia (Triaje Manchester)
COLORES = {
    "rojo": "#DC3545",
    "naranja": "#FD7E14",
    "amarillo": "#FFC107",
    "verde": "#28A745",
    "azul": "#007BFF",
    "no_urgencia": "#28A745",
}


def _client() -> httpx.Client:
    return httpx.Client(base_url=API_BASE, timeout=120.0)


def crear_interfaz_streamlit():
    st.set_page_config(
        page_title="🏥 Triaje Médico RAG",
        page_icon="🏥",
        layout="wide",
    )

    st.markdown(
        """
        <style>
        .nivel-card { padding: 10px 18px; border-radius: 6px; margin-bottom: 10px;
                      text-align: center; font-size: 20px; font-weight: 700; }
        .respuesta-box { background: #FAFAFA; padding: 10px 14px; border-radius: 4px;
                         border: 1px solid #E0E0E0; font-size: 15px; line-height: 1.3;
                         white-space: pre-line; margin-bottom: 8px; }
        .tiempo-badge { display: inline-block; background: #F0F0F0; padding: 3px 10px;
                        border-radius: 14px; font-size: 12px; color: #666; margin-bottom: 8px; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.title("🏥 Sistema de Triaje Médico con RAG")
    st.caption("Cliente de la API. Backend: FastAPI + RAG + SQLite.")

    tab1, tab2, tab3 = st.tabs(["➕ Nuevo Paciente", "🔍 Triaje", "📜 Informes"])

    # ---- TAB 1: Registro de paciente ----
    with tab1:
        st.subheader("Registrar Paciente")
        with st.form("form_paciente"):
            ci = st.text_input("C.I. (único, obligatorio)")
            nombre = st.text_input("Nombre")
            apellido = st.text_input("Apellido")
            fecha_nac = st.date_input("Fecha de nacimiento")
            sexo = st.selectbox("Sexo", ["M", "F", "Otro"])
            telefono = st.text_input("Teléfono")
            direccion = st.text_area("Dirección")
            if st.form_submit_button("Guardar Paciente"):
                payload = {
                    "ci": ci, "nombre": nombre, "apellido": apellido,
                    "fecha_nacimiento": str(fecha_nac), "sexo": sexo,
                    "telefono": telefono or None, "direccion": direccion or None,
                }
                try:
                    with _client() as c:
                        r = c.post("/pacientes", json=payload)
                    if r.status_code == 201:
                        p = r.json()
                        st.success(f"Paciente creado (ID {p['id']}, edad {p['edad']}).")
                    else:
                        st.error(f"Error {r.status_code}: {r.text}")
                except Exception as e:
                    st.error(f"No se pudo conectar al backend: {e}")

    # ---- TAB 2: Triaje ----
    with tab2:
        st.subheader("Evaluación de Triaje")
        try:
            with _client() as c:
                pacientes = c.get("/pacientes", params={"limit": 200}).json()
        except Exception as e:
            st.error(f"No se pudo conectar al backend: {e}")
            pacientes = []

        if not pacientes:
            st.info("No hay pacientes. Regístralo en la pestaña 'Nuevo Paciente'.")
        else:
            opciones = {f"{p['nombre']} {p['apellido']} (CI {p['ci']})": p["id"]
                        for p in pacientes}
            sel = st.selectbox("Paciente", list(opciones.keys()))
            paciente_id = opciones[sel]

            col1, col2 = st.columns(2)
            with col1:
                temperatura = st.slider("Temperatura (°C)", 34.0, 42.0, 37.0, 0.1)
                presion_sistolica = st.number_input("PA Sistólica", 40, 250, 120)
                presion_diastolica = st.number_input("PA Diastólica", 20, 150, 80)
            with col2:
                fc = st.number_input("FC (bpm)", 20, 200, 70)
                fr = st.number_input("FR (rpm)", 0, 100, 16)
                spo2 = st.number_input("SpO2 (%)", 50, 100, 98)

            motivo = st.text_input("Motivo de consulta")
            sintomas = st.text_area("Síntomas y presentación clínica")

            if st.button("🔍 Evaluar Triaje", type="primary"):
                payload = {
                    "paciente_id": paciente_id,
                    "temperatura": temperatura,
                    "presion_sistolica": presion_sistolica,
                    "presion_diastolica": presion_diastolica,
                    "frecuencia_cardiaca": fc,
                    "frecuencia_respiratoria": fr,
                    "spo2": spo2,
                    "motivo_consulta": motivo,
                    "sintomas": sintomas,
                }
                with st.spinner("Procesando con el motor RAG..."):
                    try:
                        with _client() as c:
                            r = c.post("/triage", json=payload)
                        if r.status_code == 201:
                            t = r.json()
                            nivel = t.get("nivel_urgencia") or "verde"
                            color = COLORES.get(nivel, "#28A745")
                            st.markdown(
                                f'<div class="nivel-card" style="background:{color};color:white;">'
                                f'NIVEL: {nivel.upper()}</div>',
                                unsafe_allow_html=True,
                            )
                            st.markdown(
                                f'<span class="tiempo-badge">⏱️ {t.get("tiempo_respuesta")}s | '
                                f'Modelo: {t.get("modelo_utilizado")}</span>',
                                unsafe_allow_html=True,
                            )
                            st.markdown(
                                f'<div class="respuesta-box">{t.get("respuesta_llm")}</div>',
                                unsafe_allow_html=True,
                            )
                        else:
                            st.error(f"Error {r.status_code}: {r.text}")
                    except Exception as e:
                        st.error(f"No se pudo conectar al backend: {e}")

    # ---- TAB 3: Informes ----
    with tab3:
        st.subheader("Informe por Paciente")
        try:
            with _client() as c:
                pacientes = c.get("/pacientes", params={"limit": 200}).json()
        except Exception:
            pacientes = []
        if pacientes:
            opciones = {f"{p['nombre']} {p['apellido']} (CI {p['ci']})": p["id"]
                        for p in pacientes}
            sel = st.selectbox("Paciente (informe)", list(opciones.keys()),
                               key="informe_sel")
            if st.button("Generar Informe"):
                with _client() as c:
                    r = c.get(f"/informes/paciente/{opciones[sel]}/texto")
                if r.status_code == 200:
                    st.text_area("Informe", r.json()["informe"], height=400)
                else:
                    st.error(f"Error {r.status_code}: {r.text}")


if __name__ == "__main__":
    crear_interfaz_streamlit()