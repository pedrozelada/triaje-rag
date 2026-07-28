import { useState, useEffect } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import api from '../api/client'
import type { ConsultaTriage, NivelUrgencia } from '../types'

const NIVELES: Record<NivelUrgencia, { color: string; bg: string; label: string; emoji: string }> = {
  rojo: { color: 'text-white', bg: 'bg-red-600', label: 'EMERGENCIA', emoji: '🔴' },
  naranja: { color: 'text-white', bg: 'bg-orange-500', label: 'URGENCIA MAYOR', emoji: '🟠' },
  amarillo: { color: 'text-gray-900', bg: 'bg-yellow-400', label: 'URGENCIA MENOR', emoji: '🟡' },
  verde: { color: 'text-white', bg: 'bg-green-600', label: 'NO URGENTE', emoji: '🟢' },
  azul: { color: 'text-white', bg: 'bg-blue-600', label: 'AUTOSANAMIENTO', emoji: '🔵' },
}

export default function ResultadoTriage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [consulta, setConsulta] = useState<ConsultaTriage | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.get(`/triage/${id}`).then((res) => setConsulta(res.data)).finally(() => setLoading(false))
  }, [id])

  if (loading) return <div className="text-center py-12 text-gray-500">Cargando resultado...</div>
  if (!consulta) return <div className="text-center py-12 text-red-600">Consulta no encontrada.</div>

  const nivel = consulta.nivel_urgencia as NivelUrgencia | null
  const nivelInfo = nivel ? NIVELES[nivel] : null

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      {/* Banner de nivel */}
      {nivelInfo && (
        <div className={`${nivelInfo.bg} ${nivelInfo.color} rounded-xl p-8 text-center`}>
          <span className="text-5xl">{nivelInfo.emoji}</span>
          <h1 className="text-3xl font-bold mt-3">{nivelInfo.label}</h1>
          <p className="text-sm opacity-80 mt-1 capitalize">Nivel: {nivel}</p>
        </div>
      )}

      {/* Respuesta LLM */}
      <div className="bg-white rounded-lg shadow-sm border p-6">
        <h2 className="font-semibold text-gray-700 mb-3">Evaluación Completa</h2>
        <div className="prose prose-sm max-w-none whitespace-pre-wrap text-gray-700">
          {consulta.respuesta_llm || 'Sin respuesta del modelo.'}
        </div>
      </div>

      {/* Metadatos */}
      <div className="bg-gray-50 rounded-lg border p-4 flex flex-wrap gap-6 text-sm text-gray-600">
        <span>⏱️ Tiempo: {consulta.tiempo_respuesta?.toFixed(2)}s</span>
        <span>🤖 Modelo: {consulta.modelo_utilizado || 'N/D'}</span>
        <span>📅 {new Date(consulta.fecha_hora).toLocaleString('es-BO')}</span>
        {consulta.tokens_consumidos && <span>🔢 Tokens: {consulta.tokens_consumidos}</span>}
      </div>

      {/* Acciones */}
      <div className="flex gap-3">
        <button
          onClick={() => navigate('/triage/nuevo')}
          className="flex-1 bg-blue-600 text-white py-3 rounded-lg font-medium hover:bg-blue-700 transition-colors"
        >
          Nueva Consulta
        </button>
        <Link
          to={`/pacientes/${consulta.paciente_id}`}
          className="flex-1 bg-gray-100 text-gray-700 py-3 rounded-lg font-medium text-center hover:bg-gray-200 transition-colors"
        >
          Ver Paciente
        </Link>
        <Link
          to="/historial"
          className="flex-1 bg-gray-100 text-gray-700 py-3 rounded-lg font-medium text-center hover:bg-gray-200 transition-colors"
        >
          Historial
        </Link>
      </div>

      {/* Disclaimer */}
      <p className="text-xs text-gray-400 text-center">
        ⚠️ Herramienta de apoyo a la decisión clínica. No reemplaza la evaluación médica profesional.
      </p>
    </div>
  )
}
