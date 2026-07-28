import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import api from '../api/client'
import type { Paciente, TriageCreate } from '../types'

export default function NuevoTriage() {
  const navigate = useNavigate()
  const [pacientes, setPacientes] = useState<Paciente[]>([])
  const [busqueda, setBusqueda] = useState('')
  const [pacienteSeleccionado, setPacienteSeleccionado] = useState<Paciente | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const { register, handleSubmit, formState: { errors } } = useForm<TriageCreate>()

  useEffect(() => {
    api.get('/pacientes?limit=200').then((res) => setPacientes(res.data))
  }, [])

  const resultados = busqueda.length >= 2
    ? pacientes.filter((p) =>
        `${p.ci} ${p.nombre} ${p.apellido}`.toLowerCase().includes(busqueda.toLowerCase())
      ).slice(0, 5)
    : []

  const onSubmit = async (data: TriageCreate) => {
    if (!pacienteSeleccionado) {
      setError('Selecciona un paciente primero.')
      return
    }
    setError('')
    setLoading(true)
    try {
      const payload: TriageCreate = {
        ...data,
        paciente_id: pacienteSeleccionado.id,
      }
      const res = await api.post('/triage', payload)
      navigate(`/triage/resultado/${res.data.id}`)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Error al procesar el triaje.'
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="max-w-3xl mx-auto">
      <h1 className="text-xl font-bold text-gray-800 mb-6">Nuevo Triaje</h1>

      {/* Buscar paciente */}
      {!pacienteSeleccionado ? (
        <div className="bg-white rounded-lg shadow-sm border p-6 mb-6">
          <h2 className="font-semibold text-gray-700 mb-3">Buscar Paciente</h2>
          <input
            type="text"
            value={busqueda}
            onChange={(e) => setBusqueda(e.target.value)}
            placeholder="Buscar por CI, nombre o apellido..."
            className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
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
          <p className="text-xs text-gray-400 mt-2">
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
        <form onSubmit={handleSubmit(onSubmit)} className="bg-white rounded-lg shadow-sm border p-6 space-y-6">
          {error && <div className="bg-red-50 text-red-700 text-sm p-3 rounded">{error}</div>}

          {/* Signos vitales */}
          <div>
            <h2 className="font-semibold text-gray-700 mb-3">Signos Vitales</h2>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
              <Field label="Temperatura (°C)" {...register('temperatura', { valueAsNumber: true })} type="number" step="0.1" />
              <Field label="PA Sistólica" {...register('presion_sistolica', { valueAsNumber: true })} type="number" />
              <Field label="PA Diastólica" {...register('presion_diastolica', { valueAsNumber: true })} type="number" />
              <Field label="Frec. Cardíaca (bpm)" {...register('frecuencia_cardiaca', { valueAsNumber: true })} type="number" />
              <Field label="Frec. Respiratoria" {...register('frecuencia_respiratoria', { valueAsNumber: true })} type="number" />
              <Field label="SpO₂ (%)" {...register('spo2', { valueAsNumber: true })} type="number" />
            </div>
          </div>

          {/* Motivo y síntomas */}
          <div>
            <h2 className="font-semibold text-gray-700 mb-3">Descripción Clínica</h2>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-600 mb-1">Motivo de consulta</label>
                <input
                  {...register('motivo_consulta')}
                  className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="Ej: Dolor torácico"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-600 mb-1">Síntomas y presentación</label>
                <textarea
                  {...register('sintomas', { required: 'Describe los síntomas' })}
                  rows={5}
                  className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder={
                    'Sea lo más específico posible.\n\nEjemplo: Dolor opresivo iniciado hace 30 minutos, irradiado al brazo izquierdo, acompañado de dificultad respiratoria y sudoración fría.'
                  }
                />
                {errors.sintomas && (
                  <p className="text-red-600 text-xs mt-1">{errors.sintomas.message}</p>
                )}
              </div>
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
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
function Field({ label, ...props }: { label: string } & any) {
  return (
    <div>
      <label className="block text-xs font-medium text-gray-600 mb-1">{label}</label>
      <input
        {...props}
        className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
      />
    </div>
  )
}
