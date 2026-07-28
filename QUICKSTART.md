# 🚀 Quick Start - Primeros Pasos

## 1️⃣ Instalación (5 minutos)

### Paso 1: Crear ambiente virtual

```bash
python -m venv venv

# Activar (elige según tu OS)
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate
```

### Paso 2: Instalar dependencias

```bash
pip install -r requirements.txt
```

## 2️⃣ Configuración (3 minutos)

### Paso 1: Copiar .env.example

```bash
cp .env.example .env
```

### Paso 2: Editar .env

Abre `.env` con tu editor favorito y configura:

```env
# REQUERIDO: Obtén tu key en https://console.groq.com
GROQ_API_KEY=gsk_your_api_key_here

# Opcional: Si ejecutas Ollama localmente
OLLAMA_BASE_URL=http://localhost:1234/v1

# Opcional: Logging (DEBUG, INFO, WARNING, ERROR)
LOG_LEVEL=INFO
```

## 3️⃣ Preparar Documentos (2 minutos)

Copia tus PDFs de las NNAC a la carpeta `data/`:

```bash
mkdir -p data
cp /ruta/a/nnac_urgencias.pdf data/
```

**Soportados**: `.pdf` y otros formatos que soporta `SimpleDirectoryReader`

## 4️⃣ Ejecutar (1 minuto)

```bash
python main.py
```

Verás en consola:

```
============================================================
🏥 Sistema de Triaje Médico con RAG (NNAC Bolivia)
============================================================

📦 Cargando modelos LLM...
✅ Modelos disponibles: ['Groq (Nube - Rápido)']

📚 Inicializando índice vectorial...
📂 Cargando documentos desde ./data ...
✅ 2 documentos cargados.
✅ Segmentado en 45 chunks.
✅ Índice vectorial creado y guardado en ChromaDB.

🎨 Creando interfaz Gradio...

🚀 Lanzando aplicación...
Accede a http://localhost:7860
```

Abre en tu navegador: **http://localhost:7860**

## 5️⃣ Usar la Aplicación

1. **Selecciona modelo**: Groq (nube) o Ollama (local)
2. **Ingresa síntomas**: Describe el caso del paciente
3. **Haz click en "Evaluar Triaje"**
4. **Revisa resultado**: 
   - Nivel de urgencia
   - Justificación
   - Fuentes
   - Tiempo empleado

## ⚙️ Configurar Ollama (Opcional)

Si quieres ejecutar modelos **completamente locales**:

### Windows

1. Descargar: https://ollama.ai
2. Instalar y ejecutar
3. En otra terminal:
   ```bash
   ollama pull mistral
   ```
4. Verificar en http://localhost:11434

### Linux

```bash
curl https://ollama.ai/install.sh | sh
ollama pull mistral
ollama serve
```

### macOS

```bash
# Instalar con Homebrew
brew install ollama

# Descargar modelo
ollama pull mistral

# Ejecutar
ollama serve
```

Luego en `.env`:
```env
OLLAMA_BASE_URL=http://localhost:11434/v1
```

## 🆘 Solución Rápida de Problemas

### ❌ "GROQ_API_KEY not found"

```bash
# Verifica que .env existe y tiene tu API key
cat .env | grep GROQ_API_KEY

# Debe ver algo como:
# GROQ_API_KEY=gsk_xxxxxxx
```

### ❌ "No PDFs encontrados"

```bash
# Verifica que hay archivos en data/
ls data/

# Debe ver al menos un PDF
# nnac_urgencias.pdf
```

### ❌ "ModuleNotFoundError"

```bash
# Asegúrate que ambiente virtual está activado
# Windows: venv\Scripts\activate
# Linux/Mac: source venv/bin/activate

# Reinstala dependencias
pip install -r requirements.txt
```

### ❌ "Ollama connection refused"

```bash
# Asegúrate de ejecutar Ollama en otra terminal
ollama serve

# En .env verifica:
OLLAMA_BASE_URL=http://localhost:1234/v1
```

## 📚 Documentación

- **README.md** - Documentación completa
- **UPGRADE_GUIDE.md** - Qué cambió en la refactorización
- **src/** - Código fuente comentado

## 🧪 Ejecutar Tests

```bash
pip install pytest

# Todos los tests
pytest tests/ -v

# Un archivo específico
pytest tests/test_utils.py -v

# Con cobertura
pytest tests/ --cov=src --cov-report=html
```

## 💡 Tips

- **Aumenta verbosidad**: Cambia `LOG_LEVEL=DEBUG` en `.env`
- **Modelo por defecto**: Groq es más rápido, Ollama es privado
- **Primeros PDFs**: Pueden tardar en indexarse, es normal
- **Consultas largas**: Aguarda, los modelos pueden tardar

## 🎯 ¿Qué Sigue?

Ahora puedes:

1. ✅ Agregar más documentos a `data/`
2. ✅ Personalizar el prompt en `src/rag_pipeline.py`
3. ✅ Agregar nuevas funcionalidades en `src/`
4. ✅ Crear interfaces alternas (Streamlit, FastAPI)

---

**¿Problemas?** Abre un issue o revisa el README completo.
