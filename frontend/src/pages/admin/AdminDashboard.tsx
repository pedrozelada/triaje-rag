import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  AreaChart, Area, Cell,
} from 'recharts'
import api from '../../api/client'
import type { Estadisticas } from '../../types'
import PageHeader from '../../components/PageHeader'

const COLOR_HEX: Record<string, string> = {
  rojo: '#EF4444',
  naranja: '#F97316',
  amarillo: '#EAB308',
  verde: '#22C55E',
  azul: '#3B82F6',
  sin_clasificar: '#9CA3AF',
}

// "2026-08-07" → "07/08"
const formatoDia = (fecha: string) => {
  const partes = fecha.split('-')
  return `${partes[2]}/${partes[1]}`
}

export default function AdminDashboard() {
  const [stats, setStats] = useState<Estadisticas | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.get('/admin/estadisticas')
      .then((res) => setStats(res.data))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="text-center py-12 text-gray-500">Cargando estadísticas...</div>
  if (!stats) return <div className="text-center py-12 text-red-600">Error al cargar datos.</div>

  const chartData = stats.por_nivel.map((n) => ({
    name: n.nivel,
    cantidad: n.cantidad,
    fill: COLOR_HEX[n.nivel] || '#9CA3AF',
  }))

  return (
    <div className="space-y-6">
      <PageHeader
        title="Panel de Administración"
        subtitle="Resumen general del sistema"
        actions={
          <div className="flex gap-2">
            <Link to="/admin/estadisticas" className="text-sm bg-gray-100 px-3 py-1.5 rounded-md hover:bg-gray-200">
              Estadísticas
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

      {/* Resumen general */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <StatCard label="Consultas" value={stats.total_consultas} />
        <StatCard label="Pacientes" value={stats.total_pacientes} />
        <StatCard label="Usuarios" value={stats.total_usuarios} />
      </div>

      {/* Indicadores de funcionamiento */}
      <div className="bg-white rounded-lg shadow-sm border p-6">
        <h2 className="font-semibold text-gray-700 mb-4">Indicadores de Funcionamiento</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <Indicator label="Tiempo promedio de respuesta" value={`${stats.promedio_tiempo_respuesta?.toFixed(2) ?? '—'} segundos`} />
          <Indicator label="Modelo más utilizado" value={stats.modelo_mas_usado || '—'} />
          <Indicator label="Consultas procesadas" value={stats.total_consultas.toLocaleString('es-BO')} />
          <Indicator label="Tokens consumidos" value={stats.total_tokens.toLocaleString('es-BO')} />
        </div>
      </div>

      {/* Consultas por nivel de urgencia */}
      <div className="bg-white rounded-lg shadow-sm border p-6">
        <h2 className="font-semibold text-gray-700 mb-4">Consultas por Nivel de Urgencia</h2>
        {chartData.length > 0 ? (
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={chartData}>
              <XAxis dataKey="name" tick={{ fontSize: 12 }} />
              <YAxis allowDecimals={false} />
              <Tooltip />
              <Bar dataKey="cantidad" radius={[4, 4, 0, 0]}>
                {chartData.map((entry) => (
                  <Cell key={entry.name} fill={entry.fill} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        ) : (
          <p className="text-gray-500 text-sm">Sin datos disponibles.</p>
        )}
      </div>

      {/* Consultas en el tiempo */}
      <div className="bg-white rounded-lg shadow-sm border p-6">
        <h2 className="font-semibold text-gray-700 mb-4">Consultas — Últimos 30 Días</h2>
        {stats.consultas_por_dia.some((d) => d.cantidad > 0) ? (
          <ResponsiveContainer width="100%" height={250}>
            <AreaChart data={stats.consultas_por_dia}>
              <XAxis dataKey="fecha" tickFormatter={formatoDia} tick={{ fontSize: 11 }} />
              <YAxis allowDecimals={false} />
              <Tooltip labelFormatter={(fecha) => `Día ${formatoDia(String(fecha))}`} />
              <Area type="monotone" dataKey="cantidad" stroke="#3B82F6" fill="#3B82F6" fillOpacity={0.2} name="consultas" />
            </AreaChart>
          </ResponsiveContainer>
        ) : (
          <p className="text-gray-500 text-sm">Sin consultas en los últimos 30 días.</p>
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
    <div className="bg-gray-50 rounded-lg border p-4">
      <p className="text-lg font-semibold text-gray-800">{value}</p>
      <p className="text-xs text-gray-500 mt-1">{label}</p>
    </div>
  )
}