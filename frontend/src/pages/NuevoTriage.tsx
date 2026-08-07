import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import api from '../api/client'
import type { Paciente, TriageCreate } from '../types'
import PageHeader from '../components/PageHeader'
import FormField from '../components/FormField'

export default function NuevoTriage() {
  const navigate = useNavigate()
  const [pacientes, setPacientes] = useState<Paciente[]>([])
  const [busqueda, setBusqueda] = useState('')
  const [pacienteSeleccionado, setPacienteSeleccionado] = useState<Paciente | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [modelos, setModelos] = useState<string[]>([])
  const [modeloSeleccionado, setModeloSeleccionado] = useState('')
  const [cargandoModelos, setCargandoModelos] = useState(true)

  const { register, handleSubmit, formState: { errors } } = useForm<TriageCreate>()

  useEffect(() => {
    api.get('/pacientes?limit=200').then((res) => setPacientes(res.data))
    api.get('/triage/modelos')
      .then((res) => {
        setModelos(res.data)
        if (res.data.length > 0) setModeloSeleccionado(res.data[0])
      })
      .catch(() => setError('No se pudieron cargar los modelos LLM disponibles.'))
      .finally(() => setCargandoModelos(false))
  }, [])

  const resultados = busqueda.length >= 2
    ? pacientes.filter((p) =>
        `${p.ci} ${p.nombre} ${p.apellido}`.toLowerCase().includes(busqueda.toLowerCase())
      ).slice(0, 5)
    : []

  const onSubmit = async (data: TriageCreate) => {
    if (!pacienteSeleccionado) {
      setError('Selecciona un paciente antes de continuar.')
      return
    }
    setError('')
    setLoading(true)
    try {
      const payload: TriageCreate = {
        ...data,
        paciente_id: pacienteSeleccionado.id,
        ...(modeloSeleccionado ? { modelo: modeloSeleccionado } : {}),
      }
      const res = await api.post('/triage', payload)
      navigate(`/triage/resultado/${res.data.id}`)
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(detail || 'Error al procesar el triaje. Intenta nuevamente.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="max-w-3xl mx-auto">
      <PageHeader title="Nuevo Triaje" subtitle="Evalúa al paciente con apoyo de IA" />

      {/* Buscar paciente */}
      {!pacienteSeleccionado ? (
        <div className="bg-white rounded-lg shadow-sm border p-6 mb-6">
          <FormField label="Buscar Paciente" required tooltip="Busca por CI, nombre o apellido (mínimo 2 caracteres)">
            <input
              type="text"
              value={busqueda}
              onChange={(e) => setBusqueda(e.target.value)}
              placeholder="Ej: 12345678 o Juan Pérez"
              maxLength={50}
              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </FormField>
          {resultados.length > 0 && (
            <ul className="mt-2 border rounded-md divide-y">
              {resultados.map((p) => (
                <li key={p.id}>
                  <button
                    onClick={() => setPacienteSeleccionado(p)}
                    className="w-full text-left px-4 py-2 hover:bg-blue-50 text-sm"
                  >
                    <span className="font-medium">{p.nombre} {p.apellido}</span>
                    <span className="text-gray-500 ml-2">{p.edad} años · CI: {p.ci}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
          {busqueda.length >= 2 && resultados.length === 0 && (
            <p className="text-sm text-gray-400 mt-2">Sin resultados. Intenta con otro término.</p>
          )}
          <p className="text-xs text-gray-400 mt-3">
            ¿Paciente nuevo?{' '}
            <button onClick={() => navigate('/pacientes/nuevo')} className="text-blue-600 underline">
              Registrar aquí
            </button>
          </p>
        </div>
      ) : (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6 flex items-center justify-between">
          <div>
            <p className="font-semibold text-blue-800">
              {pacienteSeleccionado.nombre} {pacienteSeleccionado.apellido}
            </p>
            <p className="text-sm text-blue-600">
              {pacienteSeleccionado.edad} años · {pacienteSeleccionado.sexo} · CI: {pacienteSeleccionado.ci}
            </p>
          </div>
          <button
            onClick={() => setPacienteSeleccionado(null)}
            className="text-sm text-blue-600 hover:text-blue-800 underline"
          >
            Cambiar
          </button>
        </div>
      )}

      {/* Formulario de triaje */}
      {pacienteSeleccionado && (
        <form onSubmit={handleSubmit(onSubmit)} className="bg-white rounded-lg shadow-sm border p-6 space-y-6" noValidate>
          {error && <div className="bg-red-50 border border-red-200 text-red-700 text-sm p-3 rounded">{error}</div>}

          {/* Signos vitales */}
          <div>
            <h2 className="font-semibold text-gray-700 mb-3">Signos Vitales</h2>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
              <VitalField label="Temperatura (°C)" tooltip="Normal: 36.1 - 37.2" {...register('temperatura', { valueAsNumber: true })} type="number" step="0.1" min="30" max="45" placeholder="36.5" />
              <VitalField label="PA Sistólica" tooltip="Normal: 90 - 140 mmHg" {...register('presion_sistolica', { valueAsNumber: true })} type="number" min="50" max="300" placeholder="120" />
              <VitalField label="PA Diastólica" tooltip="Normal: 60 - 90 mmHg" {...register('presion_diastolica', { valueAsNumber: true })} type="number" min="30" max="200" placeholder="80" />
              <VitalField label="Frec. Cardíaca (bpm)" tooltip="Normal: 60 - 100 bpm" {...register('frecuencia_cardiaca', { valueAsNumber: true })} type="number" min="20" max="300" placeholder="72" />
              <VitalField label="Frec. Respiratoria" tooltip="Normal: 12 - 20 rpm" {...register('frecuencia_respiratoria', { valueAsNumber: true })} type="number" min="5" max="80" placeholder="16" />
              <VitalField label="SpO₂ (%)" tooltip="Normal: 95 - 100%" {...register('spo2', { valueAsNumber: true })} type="number" min="50" max="100" placeholder="98" />
            </div>
          </div>

          {/* Motivo y síntomas */}
          <div>
            <h2 className="font-semibold text-gray-700 mb-3">Descripción Clínica</h2>
            <div className="space-y-4">
              <FormField label="Motivo de consulta" tooltip="Resumen breve de la razón de la visita">
                <input
                  {...register('motivo_consulta')}
                  maxLength={100}
                  className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="Ej: Dolor torácico"
                />
              </FormField>
              <FormField
                label="Síntomas y presentación"
                required
                tooltip="Describe inicio, localización, intensidad, síntomas asociados y evolución"
                error={errors.sintomas?.message}
              >
                <textarea
                  {...register('sintomas', { required: 'Describe los síntomas del paciente para poder evaluar el triaje.' })}
                  rows={5}
                  maxLength={2000}
                  className={`w-full border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                    errors.sintomas ? 'border-red-400 bg-red-50' : 'border-gray-300'
                  }`}
                  placeholder={
                    'Sea lo más específico posible.\n\nEjemplo: Dolor opresivo iniciado hace 30 minutos, irradiado al brazo izquierdo, acompañado de dificultad respiratoria y sudoración fría.'
                  }
                />
              </FormField>
            </div>
          </div>

          {/* Modelo LLM */}
          <div>
            <h2 className="font-semibold text-gray-700 mb-3">Modelo de IA</h2>
            <FormField
              label="Proveedor LLM"
              required
              tooltip="Elige el motor de IA para la evaluación: nube (Groq, OpenAI) o local (Ollama, sin internet)"
            >
              {cargandoModelos ? (
                <p className="text-sm text-gray-400 py-2">Cargando modelos disponibles...</p>
              ) : modelos.length > 0 ? (
                <select
                  value={modeloSeleccionado}
                  onChange={(e) => setModeloSeleccionado(e.target.value)}
                  className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  {modelos.map((m) => (
                    <option key={m} value={m}>{m}</option>
                  ))}
                </select>
              ) : (
                <p className="text-sm text-red-600 py-2">
                  No hay modelos LLM disponibles. Verifica la configuración del servidor.
                </p>
              )}
            </FormField>
          </div>

          <button
            type="submit"
            disabled={loading || cargandoModelos || modelos.length === 0}
            className="w-full bg-blue-600 text-white py-3 rounded-lg text-lg font-semibold hover:bg-blue-700 disabled:opacity-50 transition-colors"
          >
            {loading ? '⏳ Evaluando con IA...' : '🔍 Evaluar Triaje'}
          </button>
        </form>
      )}
    </div>
  )
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function VitalField({ label, tooltip, ...props }: { label: string; tooltip?: string } & any) {
  return (
    <FormField label={label} tooltip={tooltip}>
      <input
        {...props}
        className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
      />
    </FormField>
  )
}
