# 🚀 Quick Start - Primeros Pasos
python -m uvicorn backend.app.main:app --reload --port 8000                                     
cd frontend
npm install
npm run dev
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
pip install .
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

Se necesitan **dos terminales**:

```bash
# Terminal 1: Backend API (puerto 8000)
uvicorn backend.app.main:app --reload --port 8000

# Terminal 2: Frontend React (puerto 3000)
cd frontend
npm install
npm run dev
```

Abre en tu navegador: **http://localhost:3000**
- **Backend API**: http://localhost:8000
- **Documentación API**: http://localhost:8000/docs

## 5️⃣ Usar la Aplicación

1. **Selecciona modelo**: Groq (nube) u Ollama/local (LM Studio)
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
pip install .
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
- **ai_service/** - Código fuente del motor RAG comentado

## 🧪 Ejecutar Tests

```bash
pip install pytest

# Todos los tests
pytest tests/ -v

# Un archivo específico
pytest tests/test_utils.py -v

# Con cobertura
pytest tests/ --cov=ai_service --cov-report=html
```

## 💡 Tips

- **Aumenta verbosidad**: Cambia `LOG_LEVEL=DEBUG` en `.env`
- **Modelo por defecto**: Groq es más rápido, Ollama es privado
- **Primeros PDFs**: Pueden tardar en indexarse, es normal
- **Consultas largas**: Aguarda, los modelos pueden tardar

## 🎯 ¿Qué Sigue?

Ahora puedes:

1. ✅ Agregar más documentos a `data/`
2. ✅ Personalizar el prompt en `ai_service/rag_pipeline.py`
3. ✅ Agregar nuevas funcionalidades en `ai_service/`
4. ✅ Extender la API en `backend/` o el frontend React

---

**¿Problemas?** Abre un issue o revisa el README completo.