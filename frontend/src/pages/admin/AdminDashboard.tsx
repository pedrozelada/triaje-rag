import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'
import api from '../../api/client'
import type { Estadisticas } from '../../types'

const COLOR_HEX: Record<string, string> = {
  rojo: '#EF4444',
  naranja: '#F97316',
  amarillo: '#EAB308',
  verde: '#22C55E',
  azul: '#3B82F6',
  sin_clasificar: '#9CA3AF',
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
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-gray-800">Panel de Administración</h1>
        <div className="flex gap-2">
          <Link to="/admin/usuarios" className="text-sm bg-gray-100 px-3 py-1.5 rounded-md hover:bg-gray-200">
            Usuarios
          </Link>
          <Link to="/admin/reportes" className="text-sm bg-gray-100 px-3 py-1.5 rounded-md hover:bg-gray-200">
            Reportes
          </Link>
        </div>
      </div>

      {/* Cards */}
      <div className="grid grid-cols-3 gap-4">
        <StatCard label="Consultas" value={stats.total_consultas} />
        <StatCard label="Pacientes" value={stats.total_pacientes} />
        <StatCard label="Usuarios" value={stats.total_usuarios} />
      </div>

      <div className="grid grid-cols-2 gap-4">
        <StatCard label="Tiempo prom. respuesta" value={`${stats.promedio_tiempo_respuesta?.toFixed(2) ?? '—'}s`} />
        <StatCard label="Modelo más usado" value={stats.modelo_mas_usado || '—'} />
      </div>

      {/* Chart */}
      <div className="bg-white rounded-lg shadow-sm border p-6">
        <h2 className="font-semibold text-gray-700 mb-4">Consultas por Nivel de Urgencia</h2>
        {chartData.length > 0 ? (
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={chartData}>
              <XAxis dataKey="name" tick={{ fontSize: 12 }} />
              <YAxis allowDecimals={false} />
              <Tooltip />
              <Bar dataKey="cantidad" radius={[4, 4, 0, 0]} />
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
