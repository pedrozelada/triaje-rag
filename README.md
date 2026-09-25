# 🏥 Sistema de Triaje Médico con RAG (NNAC Bolivia)

Sistema de apoyo a la decisión clínica para postas rurales usando Retrieval-Augmented Generation (RAG) con las Normas Nacionales de Atención Clínica (NNAC) de Bolivia.

## Características

- ✅ **RAG Multimodal**: Groq (nube, rápido) + Gemini (nube, Google) + Ollama (local, privado) + OpenAI (opcional)
- ✅ **Selección de LLM por consulta**: el usuario elige el proveedor en cada triaje
- ✅ **Backend REST**: FastAPI con autenticación JWT, CRUD de pacientes y auditoría completa
- ✅ **Frontend React**: Interfaz moderna con Vite + TypeScript + Tailwind CSS
- ✅ **Triaje Manchester**: Clasificación por colores (rojo/naranja/amarillo/verde/azul)
- ✅ **Control de roles**: admin, médico, enfermero de triaje
- ✅ **Thread-safe**: Manejo seguro de concurrencia
- ✅ **Offline-capable**: Opción de ejecutar completamente local

## Estructura del Proyecto

```
triaje-rag/
├── pyproject.toml            # Dependencias Python (pip install .)
├── requirements-lock.txt     # Versiones fijadas del entorno
├── .env.example              # Template de variables de entorno
├── data/                     # PDFs de las NNAC
├── chroma_db/                # Base vectorial persistente
├── scripts/reindexar.py      # Reindexado manual (--dry-run / --forzar)
├── ai_service/               # Motor RAG (servicio de IA)
│   ├── errors.py             # Excepciones custom
│   ├── embeddings.py         # Embeddings multilingües
│   ├── indice.py             # Manifiesto del índice + plan de reindexado
│   ├── models.py             # DatosVitales dataclass
│   ├── rag_pipeline.py       # Index + Query Engine
│   ├── red_flags.py          # Reglas deterministas de seguridad por grupo etario
│   ├── rangos_pediatricos.py # Grupos etarios y umbrales de vitales por edad
│   ├── utils.py              # Validaciones y formateo
│   └── providers/            # Proveedores LLM (pluggable)
│       ├── base.py           # Clase base LLMProvider
│       ├── groq.py           # Groq (nube)
│       ├── gemini.py         # Google Gemini (nube)
│       ├── openai.py         # OpenAI (nube, opcional)
│       └── ollama.py         # Local (Ollama/LM Studio)
├── backend/                  # API REST (FastAPI)
│   ├── app/main.py           # App FastAPI + routers
│   ├── api/                  # Endpoints
│   │   ├── auth.py           # Login, registro, /me
│   │   ├── pacientes.py      # CRUD pacientes
│   │   ├── triage.py         # Consultas de triaje + /modelos
│   │   ├── informes.py       # Reportes por paciente
│   │   ├── admin.py          # Estadísticas + usuarios
│   │   └── deps.py           # Dependencias de auth
│   ├── core/                 # Config (carga .env vía load_dotenv) + JWT
│   ├── db/                   # SQLAlchemy models + session
│   ├── rag/service.py        # Wrapper del motor RAG (listar_modelos, analizar)
│   └── schemas/              # Pydantic schemas
├── frontend/                 # SPA React
│   ├── src/
│   │   ├── api/client.ts     # Axios con JWT automático (401 interceptor)
│   │   ├── context/          # AuthContext (sesión + rol)
│   │   ├── components/       # Layout, Breadcrumb, PageHeader, FormField
│   │   ├── pages/            # Pantallas clínicas
│   │   │   └── admin/        # Pantallas de administración
│   │   ├── types/            # Interfaces TypeScript
│   │   └── utils/            # Máscaras, formato y rangos de vitales
│   └── vite.config.ts        # Proxy /api → :8000
└── tests/                    # Suite de tests
```

## Configuración

### 1. Clonar repositorio

```bash
git clone <repo>
cd triaje-rag
```

### 2. Crear ambiente virtual

```bash
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate
```

### 3. Instalar dependencias

```bash
pip install .
```

> Las versiones exactas del entorno de desarrollo están fijadas en
> `requirements-lock.txt`. Para reproducir el entorno tal cual:
> `pip install -r requirements-lock.txt`.

### 4. Configurar variables de entorno

```bash
cp .env.example .env
```

Luego edita `.env` con tus credenciales:

```env
GROQ_API_KEY=tu_api_key_aqui
OLLAMA_BASE_URL=http://localhost:1234/v1
DATA_DIR=./data
CHROMA_PATH=./chroma_db
RAG_PRECALENTAR_AL_ARRANCAR=true
RAG_RECONSTRUCCION_AUTOMATICA=false
LOG_LEVEL=INFO
DATABASE_URL=sqlite:///./triaje.db
JWT_SECRET_KEY=cambia-este-secreto-en-produccion
```

### 5. Agregar documentos PDF

Copia tus archivos PDF de las NNAC en la carpeta `data/`:

```bash
cp /ruta/a/nnac_urgencias.pdf data/
```

No hace falta borrar `chroma_db/` ni reindexar a mano: al cargar, el sistema
compara las huellas SHA-256 de `data/` con el manifiesto del índice e indexa
solo lo que cambió (ver [Frescura del Índice](#frescura-del-índice)).

### 6. Ejecutar el sistema completo

Se necesitan **dos terminales**:

```bash
# Terminal 1: Backend API (puerto 8000)
uvicorn backend.app.main:app --reload --port 8000

# Terminal 2: Frontend React (puerto 3000)
cd frontend
npm install
npm run dev
```

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **Documentación API**: http://localhost:8000/docs

## Backend API (FastAPI)

### Endpoints

#### Autenticación (`/api/auth`)

| Método | Ruta | Descripción |
|--------|------|-------------|
| `POST` | `/api/auth/registro` | Registrar nuevo usuario |
| `POST` | `/api/auth/login` | Login → devuelve JWT |
| `GET` | `/api/auth/me` | Perfil del usuario autenticado |

#### Pacientes (`/api/pacientes`)

| Método | Ruta | Descripción |
|--------|------|-------------|
| `POST` | `/api/pacientes` | Crear paciente |
| `GET` | `/api/pacientes` | Listar pacientes |
| `GET` | `/api/pacientes/{id}` | Obtener paciente |
| `PUT` | `/api/pacientes/{id}` | Actualizar paciente |
| `DELETE` | `/api/pacientes/{id}` | Eliminar paciente |

#### Triaje (`/api/triage`)

| Método | Ruta | Descripción |
|--------|------|-------------|
| `POST` | `/api/triage` | Crear consulta (ejecuta RAG). Campo opcional `modelo` para elegir el proveedor LLM |
| `GET` | `/api/triage` | Listar consultas (filtros: `paciente_id`, `nivel_urgencia`, `fecha_desde`, `fecha_hasta`) |
| `GET` | `/api/triage/modelos` | Listar proveedores LLM disponibles (pobla el selector del frontend) |
| `GET` | `/api/triage/{id}` | Obtener consulta |

> ⚠️ `/api/triage/modelos` está declarado **antes** de `/{id}` en el router para evitar conflictos de ruta.

#### Informes (`/api/informes`)

| Método | Ruta | Descripción |
|--------|------|-------------|
| `GET` | `/api/informes/paciente/{id}` | Historial JSON del paciente |
| `GET` | `/api/informes/paciente/{id}/texto` | Historial en texto plano |
| `GET` | `/api/informes/paciente/{id}/pdf` | Historial como PDF descargable (generado con ReportLab) |

#### Administración (`/api/admin`) — requiere rol `admin`

| Método | Ruta | Descripción |
|--------|------|-------------|
| `GET` | `/api/admin/estadisticas` | Estadísticas generales: totales, urgencias, pacientes por sexo y rango etario, consultas por día (30d), uso por modelo LLM + tokens, actividad por usuario y palabras clave de motivos de consulta |
| `GET` | `/api/admin/estadisticas/triaje` | Estadísticas de triaje filtradas por período (`dias`, `fecha_desde`, `fecha_hasta`): demografía (sexo/edad), consultas por día, urgencias, motivos frecuentes y actividad por usuario |
| `GET` | `/api/admin/estadisticas/llm` | Estadísticas globales de los modelos LLM: rendimiento por modelo (consultas, tokens, tiempo promedio/mín/máx) y tiempos globales |
| `GET` | `/api/admin/usuarios` | Listar usuarios |
| `POST` | `/api/admin/usuarios` | Crear usuario (valida email/CI duplicados) |
| `PUT` | `/api/admin/usuarios/{id}` | Actualizar usuario (nombre, email, rol, centro, estado, contraseña opcional) |
| `DELETE` | `/api/admin/usuarios/{id}` | Eliminar usuario (protege auto-eliminación y último admin activo; sus triajes quedan anónimos) |

#### Health

| Método | Ruta | Descripción |
|--------|------|-------------|
| `GET` | `/api/health` | Health check |

### Autenticación

El sistema usa JWT (Bearer token). El header se envía como:

```
Authorization: Bearer <token>
```

El endpoint de triaje soporta **auth opcional**: si hay token, se registra el usuario para auditoría; si no, funciona de forma anónima.

### Roles de usuario

| Rol | Permisos |
|-----|----------|
| `admin` | Todo + gestión de usuarios + estadísticas |
| `medico` | Flujo clínico completo |
| `enfermero_triage` | Flujo clínico completo |

## Frontend (React)

### Stack

- **Vite** + **React** + **TypeScript**
- **Tailwind CSS v4** (estilos)
- **React Router v6** (rutas con protección por rol)
- **Axios** (HTTP client con JWT automático)
- **React Hook Form** (formularios)
- **Recharts** (gráficos admin)

### Pantallas

| Ruta | Pantalla | Rol |
|------|----------|-----|
| `/login` | Login + Registro (toggle de visibilidad de contraseña con icono de ojo) | Público |
| `/` | Inicio (hub de acciones) | Todos |
| `/triage/nuevo` | Nuevo triaje (buscar paciente + vitales + síntomas + **selector de proveedor LLM**) | Clínico |
| `/triage/resultado/:id` | Resultado IA (banner de color + evaluación) | Clínico |
| `/pacientes` | Lista + búsqueda de pacientes | Clínico |
| `/pacientes/nuevo` | Registro de paciente (por pasos) | Clínico |
| `/pacientes/:id` | Detalle + historial del paciente | Clínico |
| `/pacientes/:id/editar` | Editar paciente | Clínico |
| `/historial` | Todas las consultas (filtro por color) | Clínico |
| `/admin` | Dashboard de resumen: totales, indicadores de funcionamiento, urgencias por nivel y consultas de los últimos 30 días | Admin |
| `/admin/estadisticas` | Estadísticas de triaje con filtros de período (30/90 días o rango personalizado): demografía por sexo/edad, consultas por fecha, urgencias, motivos frecuentes y actividad por usuario | Admin |
| `/admin/estadisticas/llm` | Estadísticas de LLM (globales): rendimiento por modelo, consultas y tokens por modelo, y tiempos de respuesta (promedio/mín/máx) | Admin |
| `/admin/usuarios` | CRUD de usuarios con modales y confirmación previa para acciones destructivas | Admin |
| `/admin/reportes` | Generación de reportes | Admin |

### Flujo de atención

```
Login → Inicio → Nuevo Triaje → Buscar Paciente → Signos Vitales + Síntomas
  → Elegir Proveedor LLM (Groq / OpenAI / Ollama según disponibilidad)
  → [Evaluar Triaje] → Resultado IA (color + justificación + acciones)
  → [Guardar] / [Nueva Consulta] / [Ver Paciente]
```

### Convenciones de UI/UX (aplicadas en todos los formularios)

- Campos obligatorios marcados con **(*) rojo**; opcionales sin marca.
- Icono **(?)** con tooltip en campos ambiguos (`FormField` con hover/click).
- Validación en cliente y servidor; errores junto al campo con guía de corrección.
- Los datos ingresados **nunca se borran** tras un error de validación.
- Máscaras de entrada (CI solo números), `maxLength`, placeholders con ejemplos.
- Diseño responsive: menú hamburguesa en móvil, nav con estado activo en desktop.
- Breadcrumbs automáticos (`Breadcrumb`) + `PageHeader` en cada pantalla protegida.

### Ejecutar el frontend

```bash
cd frontend
npm install
npm run dev        # Desarrollo (http://localhost:3000)
npm run build      # Build de producción
```

## Configurar Ollama (Local)

Si quieres ejecutar modelos localmente:

### Windows

1. Descargar [Ollama para Windows](https://ollama.ai)
2. Instalar y ejecutar
3. Descargar un modelo:
   ```bash
   ollama pull mistral
   ```
4. Ejecutar server:
   ```bash
   ollama serve
   ```

### Linux/Mac

```bash
curl https://ollama.ai/install.sh | sh
ollama pull mistral
ollama serve
```

El servidor estará en `http://localhost:11434`

## Características de Seguridad

- ✅ Autenticación JWT con bcrypt
- ✅ Control de acceso por roles (admin/médico/enfermero)
- ✅ Validación de entrada con Pydantic
- ✅ Manejo seguro de credentials (no commitear .env)
- ✅ Thread-safety para consultas concurrentes
- ✅ Auditoría completa (usuario, prompt, modelo, tiempo, tokens)
- ✅ Logging completo

### Concurrencia con SQLite

SQLite bloquea la base completa durante las escrituras. Para que varios
enfermeros puedan registrar triajes en paralelo sin
`sqlite3.OperationalError: database is locked`, `backend/db/session.py` aplica
en cada conexión:

| Ajuste | Valor | Motivo |
|--------|-------|--------|
| `timeout` (conexión) | 30 s | El escritor espera el lock en vez de fallar |
| `PRAGMA journal_mode` | `WAL` | Los lectores no bloquean al escritor |
| `PRAGMA busy_timeout` | 30 000 ms | Refuerzo del timeout a nivel de driver |
| `PRAGMA synchronous` | `NORMAL` | Seguro y barato bajo WAL |
| `PRAGMA foreign_keys` | `ON` | SQLite las ignora por defecto |

Los PRAGMA se aplican sólo cuando `DATABASE_URL` apunta a SQLite (con
PostgreSQL no se tocan).

## Motor RAG (`ai_service/`)

### Frescura del Índice

El índice no se reconstruye en cada arranque, pero tampoco queda congelado: al
cargarlo se compara lo que hay en `data/` con un **manifiesto** guardado dentro
de la colección de Chroma (huella SHA-256, tamaño y nº de chunks por PDF) y se
aplica solo la diferencia.

| Situación | Acción |
|---|---|
| Sin cambios | Carga el índice existente: **cero embeddings** |
| PDF nuevo | Se indexa solo ese PDF |
| PDF modificado | Se borran sus chunks viejos y se reindexa |
| PDF eliminado | Se borran sus chunks huérfanos |
| Modelo de embeddings o segmentación distintos | **Aborta** (los vectores guardados ya no son comparables con los de la consulta), salvo `RAG_RECONSTRUCCION_AUTOMATICA=true` |

- Antes de tocar la colección se marca el manifiesto como `completo=false` y
  solo se marca `completo=true` al terminar: si el proceso muere a mitad de una
  indexación, el siguiente arranque lo detecta y reconstruye, en lugar de servir
  un corpus mutilado (el antiguo chequeo `count() > 0` no podía detectarlo).
- Un índice construido antes de que existiera el manifiesto se **adopta**
  (registra la huella actual) sin re-embeber nada. Para una línea base limpia:
  `python scripts/reindexar.py --forzar`.
- El arranque precalienta el índice (`RAG_PRECALENTAR_AL_ARRANCAR=true`) para que
  el primer triaje no espere a cargar los modelos; un fallo ahí no impide
  arrancar la API.
- `GET /api/admin/indice` (solo admin) muestra los documentos indexados, su
  huella, cuántos chunks aportan y si hay desviación respecto de `data/`.

```bash
python scripts/reindexar.py --dry-run   # auditar el estado sin modificar nada
python scripts/reindexar.py --forzar    # reconstruir el índice desde cero
```

### Módulos Principales

#### `ai_service.rag_pipeline`

```python
from ai_service.rag_pipeline import cargar_o_crear_indice, obtener_query_engine_con_vitales

# Cargar índice
index = cargar_o_crear_indice(data_dir="./data", chroma_path="./chroma_db")

# Query engine con datos vitales
query_engine = obtener_query_engine_con_vitales(index, llm_model, datos_vitales)

# Ejecutar consulta
response = query_engine.query("Descripción de síntomas")
```

#### `ai_service.providers`

```python
from ai_service.providers import get_llm_models

models = get_llm_models()
# {'Groq (Nube - Rápido)': Groq(...), 'Gemini (Nube - Google)': GoogleGenAI(...), 'Ollama (Local - Privado)': OpenAILike(...)}
```

### Agregar un nuevo proveedor LLM

La arquitectura de proveedores es **pluggable**. Para agregar un LLM de nube
nuevo (Anthropic, Gemini, etc.):

1. Crear `ai_service/providers/<nombre>.py` con una clase que herede `LLMProvider`
   (usar `openai.py` como plantilla):
   - `disponible()`: chequeo barato (API key presente, paquete instalado).
   - `crear()`: instancia el LLM (import diferido dentro del método).
2. Registrar la clase en la lista `PROVEEDORES` de `ai_service/providers/__init__.py`.
3. Instalar el paquete de llama-index correspondiente.

No hay que tocar backend ni CLI: todos consumen `get_llm_models()`.

| Proveedor | Activo si... | Variables |
|-----------|--------------|-----------|
| Groq | `GROQ_API_KEY` definida | `GROQ_MODEL`, `GROQ_TEMPERATURE`, `GROQ_MAX_TOKENS` |
| Gemini | `GEMINI_API_KEY` + paquete instalado | `GEMINI_MODEL`, `GEMINI_TEMPERATURE`, `GEMINI_MAX_TOKENS`, `GEMINI_THINKING_BUDGET` |
| OpenAI | `OPENAI_API_KEY` + paquete instalado | `OPENAI_MODEL`, `OPENAI_TEMPERATURE`, `OPENAI_MAX_TOKENS` |
| Ollama | Siempre (se descarta si no responde) | `OLLAMA_BASE_URL`, `OLLAMA_MODEL`, `OLLAMA_TIMEOUT` |

> **Nota**: `backend/core/config.py` ejecuta `load_dotenv()` al arrancar, de modo
> que las claves del `.env` estén en `os.environ` para los proveedores.
> El orden en `PROVEEDORES` define la prioridad cuando no se especifica modelo
> (actualmente: Groq → Gemini → OpenAI → Ollama).

> **Gemini**: requiere `pip install llama-index-llms-google-genai`. El catálogo
> rota: los modelos 2.x devuelven 404 para cuentas nuevas, por lo que el default
> es `gemini-3.5-flash`. Para latencia baja en triaje se puede fijar
> `GEMINI_THINKING_BUDGET=0` (los Gemini 3 razonan antes de responder y eso añade
> segundos, además de consumir tokens del presupuesto).

### Clasificación de urgencia (Manchester)

| Color | Nivel | Tiempo de atención |
|-------|-------|--------------------|
| 🔴 Rojo | Emergencia | Inmediata |
| 🟠 Naranja | Urgencia Mayor | ~10 min |
| 🟡 Amarillo | Urgencia Menor | ~60 min |
| 🟢 Verde | No Urgente | Diferible |
| 🔵 Azul | Autosanamiento | Orientación |

### Reglas deterministas de red flags (CU-25)

`ai_service/red_flags.py` es una capa de seguridad independiente del LLM: sólo
puede ELEVAR el nivel de urgencia, nunca bajarlo. Sus umbrales de signos
vitales se parametrizan por **grupo etario** (tabla en
`ai_service/rangos_pediatricos.py`), no con valores fijos de adulto.

| Grupo | Edad |
|-------|------|
| Neonato | < 1 mes |
| Lactante | 1-11 meses |
| Preescolar | 1-5 años |
| Escolar | 6-11 años |
| Adolescente | 12-17 años |
| Adulto | 18-64 años |
| Adulto mayor | ≥ 65 años |

Sin esta parametrización, un lactante con **FR 40 rpm** o **FC 140 bpm**
(valores fisiológicos a esa edad) disparaba falsas alertas rojas/naranjas.
La edad se obtiene de `fecha_nacimiento`; para los menores de 1 año se usa
`edad_meses`, porque en años valen 0 y se perdería el grupo etario.

Umbrales de alerta por grupo etario (valor fuera del rango → alerta):

| Grupo | FR naranja | FR rojo | FC naranja | FC rojo | PAS rojo |
|-------|-----------|---------|-----------|---------|----------|
| Neonato | < 28 o ≥ 70 | < 20 o > 90 | < 90 o ≥ 180 | < 80 o > 220 | < 60 |
| Lactante | < 22 o ≥ 60 | < 14 o > 80 | < 90 o ≥ 180 | < 70 o > 220 | < 70 |
| Preescolar | < 18 o ≥ 40 | < 12 o > 55 | < 80 o ≥ 160 | < 60 o > 200 | < 75 |
| Escolar | < 14 o ≥ 30 | < 10 o > 45 | < 70 o ≥ 140 | < 50 o > 180 | < 80 |
| Adolescente | < 12 o ≥ 26 | < 8 o > 38 | < 55 o ≥ 130 | < 45 o > 170 | < 90 |
| Adulto | < 12 o ≥ 30 | < 8 o > 40 | < 45 o ≥ 140 | < 40 o > 160 | < 80 |
| Adulto mayor | < 12 o ≥ 24 | < 8 o > 32 | < 50 o ≥ 120 | < 40 o > 150 | < 90 |

SpO2 (rojo < 90%, naranja < 94%) y temperatura (rojo ≥ 41 °C o < 33 °C,
naranja ≥ 40 °C o < 35 °C) usan el mismo umbral en todos los grupos.

> Los signos vitales no medidos llegan como `None` (= «No registrado») al
> prompt del LLM y **nunca** se sustituyen por 0 ni por valores normales.

## Evaluación del sistema (Componente 2)

La evaluación de la tesis vive en `evaluacion/` y se regenera por completo con
`scripts/evaluar.py`, sin tocar el código del motor. La evidencia cruda de cada
corrida (respuesta completa, fragmentos recuperados con puntaje y página,
tiempos y tokens) se guarda en disco, de modo que cualquier cifra del informe se
puede auditar caso por caso.

```
evaluacion/
├── casos/             # 20 casos clínicos + 10 casos anti-alucinación (fuente de verdad)
├── resultados/        # evidencia cruda de cada corrida (.json) y su resumen (.csv)
├── informes/          # informe técnico (C2.A2/A3) e informe clínico (C2.A4/A5)
└── instrumentos/      # rúbrica clínica y encuesta SUS para el médico colaborador
```

### Comandos

```bash
# 1. Revisa los casos (esquema, niveles válidos, fuentes y detectores) sin llamar a ningún modelo
python scripts/evaluar.py validar

# 2. Ejecuta los casos contra el sistema completo (RAG + reglas) o contra la línea base sin contexto
python scripts/evaluar.py correr --variante rag --modelo groq --ids C-01,C-02 --pausa 5
python scripts/evaluar.py correr --variante sin-contexto --modelo gemini --limite 5

# 3. Recalcula las métricas y escribe el informe (los lotes del mismo experimento se fusionan)
python scripts/evaluar.py informe rag_groq_1 rag_groq_2a --titulo "Corrida final"

# 4. Prepara los instrumentos para el médico y calcula C2.A4/A5 cuando los devuelva
python scripts/evaluar.py instrumentos --run rag_groq_1 rag_groq_2a
python scripts/evaluar.py rubrica --run rag_groq_1 rag_groq_2a
```

Las corridas de 30 casos duran decenas de segundos por caso, así que conviene
partirlas en lotes con `--ids` o `--limite`: cada caso se guarda apenas termina
(`parcial: true` mientras la corrida siga incompleta) y `informe` une los lotes
del mismo variante y modelo en una sola columna comparable.

### Informe Word

El apartado del Componente 2 para el documento de tesis se arma con
`scripts/informe_word.py`, que lee la evidencia de `evaluacion/resultados/`,
reutiliza el formato del Capítulo II (`docs/tesis/generar_documento.py`) y
produce `docs/tesis/Informe_Evaluacion_Componente2_Zelada.docx` con portada,
numeración propia desde 1, índices, tres gráficos y anexos.

```bash
# Genera el .docx reutilizando los gráficos ya descargados
python scripts/informe_word.py

# Vuelve a pedir los tres gráficos a kroki y regenera todo
python scripts/informe_word.py --forzar-graficos

# Arma el documento sin tocar los gráficos (útil sin conexión)
python scripts/informe_word.py --sin-graficos
```

Los gráficos se renderizan con kroki a partir de especificaciones Vega y se
guardan en `docs/tesis/figuras/eval_*.png`; si kroki no responde, el documento se
genera igual y avisa de la figura faltante. Si el `.docx` está abierto en Word, el
script guarda una copia con marca de tiempo en lugar de fallar.

### Qué mide

- **Nivel de urgencia**: exactitud, rango clínicamente aceptable, sub-triage
  (el error grave) y supra-triage, comparando contra el nivel esperado del caso.
- **Recuperación**: Recall@3, Recall@5, Precision@5 y MRR sobre los fragmentos
  efectivamente usados, a nivel de página y de documento.
- **Alucinaciones**: 10 casos diseñados para provocarlas (preguntas capciosas,
  datos contradictorios, entidades inexistentes y citas falsas) con detección
  automática de dosis inventadas, entidades no declaradas y citas fuera del corpus.
- **Costo y estabilidad**: latencia (media, mediana, p95) y tokens reales
  reportados por el proveedor cuando `rag_medir_tokens=true`; repeticiones con
  `--repeticiones N` para medir estabilidad del nivel.
- **Contraste con la línea base**: la variante `sin-contexto` usa el MISMO prompt
  y las MISMAS reglas, pero sin fragmentos recuperados, para aislar el aporte del RAG.

### Criterios de aceptación (Componente 2)

| Indicador | Criterio |
|---|---|
| Casos clínicos en Bueno o Muy bueno (C2.A4) | ≥ 80 % |
| Tasa de alucinaciones (casos anti-alucinación) | < 15 % |
| Usabilidad percibida (C2.A5, encuesta SUS) | ≥ 70 puntos |

### Limitaciones conocidas de la evidencia actual

- **Cuotas de los proveedores en la nube**: las líneas base con Groq y Gemini
  quedaron parciales (límite de 200 000 tokens/día en Groq y de 20
  solicitudes/día en Gemini). La comparación se hace sobre el subconjunto de
  casos ejecutados en común, que el informe declara explícitamente; una corrida
  completa del benchmark requiere esperar el reinicio de cuota, otra clave o un
  modelo local vía Ollama.
- **Memoria RAM**: no medida. Se reporta como trabajo futuro (instrumentar con
  `psutil` o el contador de procesos de Windows), no como resultado.
- **Validación clínica (C2.A4/A5)**: pendiente del médico colaborador. Los
  instrumentos ya están generados; `rubrica` calcula el porcentaje de casos
  aceptables, el puntaje SUS y la concordancia con el veredicto automático.
- **Niveles esperados**: los casos fueron construidos leyendo la norma NNAC y
  están a la espera de validación médica; el informe conserva el rango
  clínicamente aceptable para no tratar las zonas grises de Manchester como error.

## Testing

```bash
pytest tests/ -v
```

Los tests cubren, además del sistema, la instrumentación de la evaluación
(`tests/test_metricas_rag.py`): evidencia de recuperación con puntaje y página,
conteo de tokens reportado por el proveedor (nunca estimado) y las regresiones
de negación y umbrales pediátricos que motivan el Componente 2.

## Logging

Los logs se generan con timestamps completos. Niveles:

- `DEBUG`: Información detallada
- `INFO`: Eventos importantes
- `WARNING`: Advertencias
- `ERROR`: Errores

Configura `LOG_LEVEL` en `.env` para cambiar el nivel.

## Solución de Problemas

### Error: "GROQ_API_KEY not found"

Verifica que:
1. Archivo `.env` existe
2. Contiene `GROQ_API_KEY=tu_api_key`
3. No hay espacios extra

### Error: "No PDFs encontrados en ./data"

Asegúrate de:
1. Crear carpeta `data/`
2. Copiar PDFs ahí
3. Usar formatos: `.pdf`

### Error: "No se pudo conectar a Ollama"

Verifica que:
1. Ollama está corriendo: `ollama serve`
2. URL es correcta en `.env`: `OLLAMA_BASE_URL=http://localhost:11434/v1`
3. Modelo está descargado: `ollama pull mistral`

## Mejoras Futuras

- [ ] Caché de consultas frecuentes
- [ ] Versioning de documentos NNAC
- [ ] App móvil (React Native)
- [ ] Migraciones con Alembic
- [ ] Tests de integración del frontend
- [ ] Code-splitting del bundle frontend (chunk actual > 500 kB)
- [ ] Medición de memoria RAM del proceso RAG (psutil / contador de Windows)
- [ ] Corrida completa de las líneas base cuando se reinicien las cuotas de Groq y Gemini
- [ ] Cláusula de «información insuficiente» en el prompt de producción, medida
      sobre los 10 casos anti-alucinación

## Licencia

MIT

## Contribuir

Las contribuciones son bienvenidas. Por favor:

1. Fork el proyecto
2. Crea una rama para tu feature (`git checkout -b feature/AmazingFeature`)
3. Commit tus cambios (`git commit -m 'Add AmazingFeature'`)
4. Push a la rama (`git push origin feature/AmazingFeature`)
5. Abre un Pull Request

## Soporte

Para soporte, abre un issue o contacta al equipo de desarrollo.

---

**Nota Legal**: Esta herramienta es de apoyo y **no reemplaza** el criterio médico profesional. Siempre consulta con un profesional de salud calificado.