import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
} from 'recharts'
import api from '../../api/client'
import type { EstadisticasLLM } from '../../types'
import PageHeader from '../../components/PageHeader'

const PALETA = ['#3B82F6', '#22C55E', '#F97316', '#8B5CF6', '#EC4899', '#EAB308', '#14B8A6']

const formatoSegundos = (v: number | null) => (v == null ? '—' : `${v.toFixed(2)}s`)

export default function AdminEstadisticasLLM() {
  const [stats, setStats] = useState<EstadisticasLLM | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.get('/admin/estadisticas/llm')
      .then((res) => setStats(res.data))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="text-center py-12 text-gray-500">Cargando estadísticas...</div>
  if (!stats) return <div className="text-center py-12 text-red-600">Error al cargar datos.</div>

  const consultasData = stats.por_modelo.map((m) => ({
    name: m.modelo,
    consultas: m.consultas,
  }))

  const tokensData = stats.por_modelo.map((m) => ({
    name: m.modelo,
    tokens: m.tokens,
  }))

  return (
    <div className="space-y-6">
      <PageHeader
        title="Estadísticas de LLM"
        subtitle="Rendimiento y uso de los modelos de lenguaje"
        actions={
          <div className="flex gap-2">
            <Link to="/admin" className="text-sm bg-gray-100 px-3 py-1.5 rounded-md hover:bg-gray-200">
              Dashboard
            </Link>
            <Link to="/admin/estadisticas" className="text-sm bg-gray-100 px-3 py-1.5 rounded-md hover:bg-gray-200">
              Estadísticas de Triaje
            </Link>
            <Link to="/admin/usuarios" className="text-sm bg-gray-100 px-3 py-1.5 rounded-md hover:bg-gray-200">
              Usuarios
            </Link>
            <Link to="/admin/reportes" className="text-sm bg-gray-100 px-3 py-1.5 rounded-md hover:bg-gray-200">
              Reportes
            </Link>
          </div>
        }
      />

      {/* Resumen global */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <StatCard label="Consultas procesadas" value={stats.total_consultas.toLocaleString('es-BO')} />
        <StatCard label="Tokens consumidos" value={stats.total_tokens.toLocaleString('es-BO')} />
        <StatCard label="Modelos utilizados" value={stats.por_modelo.length} />
      </div>

      {/* Tiempo de respuesta global */}
      <div className="bg-white rounded-lg shadow-sm border p-6">
        <h2 className="font-semibold text-gray-700 mb-4">Tiempo de Respuesta (Global)</h2>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <Indicator label="Tiempo promedio" value={formatoSegundos(stats.tiempo_promedio)} />
          <Indicator label="Tiempo mínimo" value={formatoSegundos(stats.tiempo_minimo)} />
          <Indicator label="Tiempo máximo" value={formatoSegundos(stats.tiempo_maximo)} />
        </div>
      </div>

      {/* Rendimiento por modelo */}
      <div className="bg-white rounded-lg shadow-sm border p-6">
        <h2 className="font-semibold text-gray-700 mb-4">Rendimiento por Modelo</h2>
        {stats.por_modelo.length > 0 ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {stats.por_modelo.map((m, i) => (
              <div key={m.modelo} className="rounded-lg border p-4" style={{ borderTop: `4px solid ${PALETA[i % PALETA.length]}` }}>
                <p className="font-semibold text-gray-800 mb-3">{m.modelo}</p>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-gray-500">Tiempo promedio</span>
                    <span className="font-medium text-gray-800">{formatoSegundos(m.tiempo_promedio)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-500">Tokens utilizados</span>
                    <span className="font-medium text-gray-800">{m.tokens.toLocaleString('es-BO')}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-500">Consultas procesadas</span>
                    <span className="font-medium text-gray-800">{m.consultas.toLocaleString('es-BO')}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-gray-500 text-sm">Sin datos de modelos registrados.</p>
        )}
      </div>

      {/* Uso de modelos */}
      <div className="bg-white rounded-lg shadow-sm border p-6">
        <h2 className="font-semibold text-gray-700 mb-4">Consultas por Modelo</h2>
        {consultasData.length > 0 ? (
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={consultasData}>
              <XAxis dataKey="name" tick={{ fontSize: 12 }} />
              <YAxis allowDecimals={false} />
              <Tooltip />
              <Bar dataKey="consultas" name="Consultas" radius={[4, 4, 0, 0]}>
                {consultasData.map((_, i) => (
                  <Cell key={i} fill={PALETA[i % PALETA.length]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        ) : (
          <p className="text-gray-500 text-sm">Sin datos disponibles.</p>
        )}
      </div>

      {/* Tokens por modelo */}
      <div className="bg-white rounded-lg shadow-sm border p-6">
        <h2 className="font-semibold text-gray-700 mb-4">Tokens por Modelo</h2>
        {tokensData.length > 0 ? (
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={tokensData}>
              <XAxis dataKey="name" tick={{ fontSize: 12 }} />
              <YAxis allowDecimals={false} />
              <Tooltip formatter={(value) => Number(value).toLocaleString('es-BO')} />
              <Bar dataKey="tokens" name="Tokens" radius={[4, 4, 0, 0]}>
                {tokensData.map((_, i) => (
                  <Cell key={i} fill={PALETA[i % PALETA.length]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        ) : (
          <p className="text-gray-500 text-sm">Sin datos disponibles.</p>
        )}
      </div>
    </div>
  )
}

function StatCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="bg-white rounded-lg shadow-sm border p-4 text-center">
      <p className="text-2xl font-bold text-gray-800">{value}</p>
      <p className="text-xs text-gray-500 mt-1">{label}</p>
    </div>
  )
}

function Indicator({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="bg-gray-50 rounded-lg border p-4 text-center">
      <p className="text-lg font-semibold text-gray-800">{value}</p>
      <p className="text-xs text-gray-500 mt-1">{label}</p>
    </div>
  )
}