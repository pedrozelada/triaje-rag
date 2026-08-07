# 🏥 Sistema de Triaje Médico con RAG (NNAC Bolivia)

Sistema de apoyo a la decisión clínica para postas rurales usando Retrieval-Augmented Generation (RAG) con las Normas Nacionales de Atención Clínica (NNAC) de Bolivia.

## Características

- ✅ **RAG Multimodal**: Groq (nube, rápido) + Ollama (local, privado) + OpenAI (opcional)
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
├── config.py                 # Configuración central
├── main.py                   # Entry point (Gradio/Streamlit)
├── requirements.txt          # Dependencias Python
├── .env.example              # Template de variables de entorno
├── data/                     # PDFs de las NNAC
├── chroma_db/                # Base vectorial persistente
├── ai_service/               # Motor RAG (servicio de IA)
│   ├── errors.py             # Excepciones custom
│   ├── embeddings.py         # Embeddings multilingües
│   ├── models.py             # DatosVitales dataclass
│   ├── rag_pipeline.py       # Index + Query Engine
│   ├── utils.py              # Validaciones y formateo
│   └── providers/            # Proveedores LLM (pluggable)
│       ├── base.py           # Clase base LLMProvider
│       ├── groq.py           # Groq (nube)
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
│   │   └── types/            # Interfaces TypeScript
│   └── vite.config.ts        # Proxy /api → :8000
├── ui/                       # Interfaces legacy (Gradio/Streamlit)
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
pip install -r requirements.txt
```

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
LOG_LEVEL=INFO
DATABASE_URL=sqlite:///./triaje.db
JWT_SECRET_KEY=cambia-este-secreto-en-produccion
```

### 5. Agregar documentos PDF

Copia tus archivos PDF de las NNAC en la carpeta `data/`:

```bash
cp /ruta/a/nnac_urgencias.pdf data/
```

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

### Alternativa: Interfaz Gradio (legacy)

```bash
python main.py
```

La interfaz Gradio estará disponible en `http://localhost:7860`

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

#### Administración (`/api/admin`) — requiere rol `admin`

| Método | Ruta | Descripción |
|--------|------|-------------|
| `GET` | `/api/admin/estadisticas` | Estadísticas generales |
| `GET` | `/api/admin/usuarios` | Listar usuarios |
| `PUT` | `/api/admin/usuarios/{id}` | Actualizar usuario (rol, estado) |

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
| `/admin` | Dashboard con estadísticas | Admin |
| `/admin/usuarios` | Gestión de usuarios | Admin |
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

## Motor RAG (`ai_service/`)

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
# {'Groq (Nube - Rápido)': Groq(...), 'Ollama (Local - Privado)': OpenAILike(...)}
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

No hay que tocar backend, UI ni CLI: todos consumen `get_llm_models()`.

| Proveedor | Activo si... | Variables |
|-----------|--------------|-----------|
| Groq | `GROQ_API_KEY` definida | `GROQ_MODEL`, `GROQ_TEMPERATURE`, `GROQ_MAX_TOKENS` |
| OpenAI | `OPENAI_API_KEY` + paquete instalado | `OPENAI_MODEL`, `OPENAI_TEMPERATURE`, `OPENAI_MAX_TOKENS` |
| Ollama | Siempre (se descarta si no responde) | `OLLAMA_BASE_URL`, `OLLAMA_MODEL`, `OLLAMA_TIMEOUT` |

> **Nota**: `backend/core/config.py` ejecuta `load_dotenv()` al arrancar, de modo
> que las claves del `.env` estén en `os.environ` para los proveedores.
> El orden en `PROVEEDORES` define la prioridad cuando no se especifica modelo
> (actualmente: Groq → OpenAI → Ollama).

### Clasificación de urgencia (Manchester)

| Color | Nivel | Tiempo de atención |
|-------|-------|--------------------|
| 🔴 Rojo | Emergencia | Inmediata |
| 🟠 Naranja | Urgencia Mayor | ~10 min |
| 🟡 Amarillo | Urgencia Menor | ~60 min |
| 🟢 Verde | No Urgente | Diferible |
| 🔵 Azul | Autosanamiento | Orientación |

## Testing

```bash
pytest tests/ -v
```

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

- [ ] Exportar reportes a PDF
- [ ] Caché de consultas frecuentes
- [ ] Versioning de documentos NNAC
- [ ] App móvil (React Native)
- [ ] Migraciones con Alembic
- [ ] Tests de integración del frontend
- [ ] Code-splitting del bundle frontend (chunk actual > 500 kB)

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