import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import api from '../api/client'
import type { ConsultaTriage } from '../types'
import PageHeader from '../components/PageHeader'
import { useTablaDatos, ControlesPaginacion, inputFiltroClass } from '../hooks/useTablaDatos'

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
  const [busqueda, setBusqueda] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const params = filtro !== 'todos' ? `?nivel_urgencia=${filtro}&limit=100` : '?limit=100'
    api.get(`/triage${params}`)
      .then((res) => setConsultas(res.data))
      .finally(() => setLoading(false))
  }, [filtro])

  const filtradas = consultas.filter((c) => {
    if (!busqueda.trim()) return true
    const texto = `${c.motivo_consulta ?? ''} ${c.sintomas ?? ''} ${c.paciente_id}`.toLowerCase()
    return texto.includes(busqueda.trim().toLowerCase())
  })

  const tabla = useTablaDatos(filtradas, {
    columnaInicial: 'fecha',
    direccionInicial: 'desc',
    porPagina: 20,
    obtenerValor: (c, col) => (col === 'fecha' ? new Date(c.fecha_hora).getTime() : null),
  })

  return (
    <div>
      <PageHeader title="Historial de Consultas" subtitle={`${filtradas.length} consulta(s)`} />

      {/* Búsqueda y orden */}
      <div className="flex flex-col sm:flex-row gap-3 mb-4">
        <input
          type="text"
          value={busqueda}
          onChange={(e) => setBusqueda(e.target.value)}
          placeholder="Buscar por motivo, síntomas o paciente..."
          maxLength={50}
          className={`${inputFiltroClass} flex-1`}
        />
        <button
          onClick={() => tabla.ordenarPor('fecha')}
          className="border border-gray-300 rounded-md px-3 py-2 text-sm text-gray-600 hover:bg-gray-50 whitespace-nowrap"
        >
          Fecha: {tabla.ordenDireccion === 'desc' ? 'Más recientes ▼' : 'Más antiguas ▲'}
        </button>
      </div>

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
      ) : filtradas.length === 0 ? (
        <p className="text-gray-500 text-center py-8">No hay consultas registradas.</p>
      ) : (
        <div className="space-y-3">
          {tabla.paginados.map((c) => (
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

      {consultas.length > 0 && filtradas.length > 0 && (
        <ControlesPaginacion
          paginaActual={tabla.paginaActual}
          totalPaginas={tabla.totalPaginas}
          cambiarPagina={tabla.cambiarPagina}
          total={filtradas.length}
          porPagina={20}
        />
      )}
    </div>
  )
}
