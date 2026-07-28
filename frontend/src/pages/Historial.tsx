import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import api from '../api/client'
import type { ConsultaTriage } from '../types'

const COLOR_MAP: Record<string, string> = {
  rojo: 'bg-red-100 text-red-800',
  naranja: 'bg-orange-100 text-orange-800',
  amarillo: 'bg-yellow-100 text-yellow-800',
  verde: 'bg-green-100 text-green-800',
  azul: 'bg-blue-100 text-blue-800',
}

const FILTROS = ['todos', 'rojo', 'naranja', 'amarillo', 'verde', 'azul'] as const

export default function Historial() {
  const [consultas, setConsultas] = useState<ConsultaTriage[]>([])
  const [filtro, setFiltro] = useState<string>('todos')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const params = filtro !== 'todos' ? `?nivel_urgencia=${filtro}&limit=100` : '?limit=100'
    api.get(`/triage${params}`)
      .then((res) => setConsultas(res.data))
      .finally(() => setLoading(false))
  }, [filtro])

  return (
    <div>
      <h1 className="text-xl font-bold text-gray-800 mb-6">Historial de Consultas</h1>

      {/* Filtros por color */}
      <div className="flex gap-2 mb-4 flex-wrap">
        {FILTROS.map((f) => (
          <button
            key={f}
            onClick={() => setFiltro(f)}
            className={`px-3 py-1.5 rounded-full text-xs font-medium capitalize transition-colors ${
              filtro === f ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            {f}
          </button>
        ))}
      </div>

      {loading ? (
        <p className="text-gray-500 text-center py-8">Cargando...</p>
      ) : consultas.length === 0 ? (
        <p className="text-gray-500 text-center py-8">No hay consultas registradas.</p>
      ) : (
        <div className="space-y-3">
          {consultas.map((c) => (
            <Link
              key={c.id}
              to={`/triage/resultado/${c.id}`}
              className="block bg-white border rounded-lg p-4 hover:shadow-sm transition-shadow"
            >
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-500">
                  {new Date(c.fecha_hora).toLocaleString('es-BO')}
                </span>
                {c.nivel_urgencia && (
                  <span className={`text-xs font-medium px-2 py-1 rounded-full capitalize ${COLOR_MAP[c.nivel_urgencia] || 'bg-gray-100'}`}>
                    {c.nivel_urgencia}
                  </span>
                )}
              </div>
              <p className="text-sm font-medium text-gray-800 mt-1">
                {c.motivo_consulta || c.sintomas?.slice(0, 100) || 'Sin descripción'}
              </p>
              <p className="text-xs text-gray-400 mt-1">
                Paciente #{c.paciente_id} · {c.modelo_utilizado || 'N/D'} · {c.tiempo_respuesta?.toFixed(1)}s
              </p>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
