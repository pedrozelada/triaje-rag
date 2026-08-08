import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend, AreaChart, Area,
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

const SEXO_LABEL: Record<string, string> = {
  M: 'Masculino',
  F: 'Femenino',
  Otro: 'Otro',
}

const SEXO_COLOR: Record<string, string> = {
  M: '#3B82F6',
  F: '#EC4899',
  Otro: '#8B5CF6',
}

const PALETA = ['#3B82F6', '#22C55E', '#F97316', '#8B5CF6', '#EC4899', '#EAB308', '#14B8A6']

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

  const sexoData = stats.por_sexo.map((s) => ({
    name: SEXO_LABEL[s.sexo] || s.sexo,
    sexo: s.sexo,
    cantidad: s.cantidad,
  }))

  return (
    <div className="space-y-6">
      <PageHeader
        title="Panel de Administración"
        subtitle="Resumen general del sistema"
        actions={
          <div className="flex gap-2">
            <Link to="/admin/usuarios" className="text-sm bg-gray-100 px-3 py-1.5 rounded-md hover:bg-gray-200">
              Usuarios
            </Link>
            <Link to="/admin/reportes" className="text-sm bg-gray-100 px-3 py-1.5 rounded-md hover:bg-gray-200">
              Reportes
            </Link>
          </div>
        }
      />

      {/* Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <StatCard label="Consultas" value={stats.total_consultas} />
        <StatCard label="Pacientes" value={stats.total_pacientes} />
        <StatCard label="Usuarios" value={stats.total_usuarios} />
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <StatCard label="Tiempo prom. respuesta" value={`${stats.promedio_tiempo_respuesta?.toFixed(2) ?? '—'}s`} />
        <StatCard label="Tokens consumidos" value={stats.total_tokens.toLocaleString('es-BO')} />
        <StatCard label="Modelo más usado" value={stats.modelo_mas_usado || '—'} />
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
              <Bar dataKey="cantidad" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        ) : (
          <p className="text-gray-500 text-sm">Sin datos disponibles.</p>
        )}
      </div>

      {/* Demografía: sexo + edad */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-white rounded-lg shadow-sm border p-6">
          <h2 className="font-semibold text-gray-700 mb-4">Pacientes por Género</h2>
          {sexoData.length > 0 ? (
            <ResponsiveContainer width="100%" height={250}>
              <PieChart>
                <Pie data={sexoData} dataKey="cantidad" nameKey="name" innerRadius={55} outerRadius={85} paddingAngle={2}>
                  {sexoData.map((entry) => (
                    <Cell key={entry.sexo} fill={SEXO_COLOR[entry.sexo] || '#9CA3AF'} />
                  ))}
                </Pie>
                <Tooltip />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <p className="text-gray-500 text-sm">Sin datos disponibles.</p>
          )}
        </div>

        <div className="bg-white rounded-lg shadow-sm border p-6">
          <h2 className="font-semibold text-gray-700 mb-4">Pacientes por Rango de Edad</h2>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={stats.por_rango_edad}>
              <XAxis dataKey="rango" tick={{ fontSize: 11 }} />
              <YAxis allowDecimals={false} />
              <Tooltip />
              <Bar dataKey="cantidad" fill="#8B5CF6" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
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

      {/* Motivos frecuentes + uso de modelos */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-white rounded-lg shadow-sm border p-6">
          <h2 className="font-semibold text-gray-700 mb-1">Motivos de Consulta Frecuentes</h2>
          <p className="text-xs text-gray-400 mb-4">Palabras clave de motivos y síntomas (no es un conteo clínico).</p>
          {stats.motivos_frecuentes.length > 0 ? (
            <ResponsiveContainer width="100%" height={Math.max(220, stats.motivos_frecuentes.length * 30)}>
              <BarChart data={stats.motivos_frecuentes} layout="vertical" margin={{ left: 8 }}>
                <XAxis type="number" allowDecimals={false} tick={{ fontSize: 11 }} />
                <YAxis type="category" dataKey="palabra" width={100} tick={{ fontSize: 12 }} />
                <Tooltip />
                <Bar dataKey="cantidad" fill="#22C55E" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <p className="text-gray-500 text-sm">Sin datos disponibles.</p>
          )}
        </div>

        <div className="bg-white rounded-lg shadow-sm border p-6">
          <h2 className="font-semibold text-gray-700 mb-4">Uso por Modelo LLM</h2>
          {stats.por_modelo.length > 0 ? (
            <ResponsiveContainer width="100%" height={250}>
              <PieChart>
                <Pie data={stats.por_modelo} dataKey="consultas" nameKey="modelo" outerRadius={85}>
                  {stats.por_modelo.map((_, i) => (
                    <Cell key={i} fill={PALETA[i % PALETA.length]} />
                  ))}
                </Pie>
                <Tooltip formatter={(value, _name, item) => {
                  const m = item?.payload as { modelo: string; tokens: number } | undefined
                  return [`${value} consultas · ${m?.tokens.toLocaleString('es-BO') ?? 0} tokens`, m?.modelo]
                }} />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <p className="text-gray-500 text-sm">Sin datos disponibles.</p>
          )}
        </div>
      </div>

      {/* Actividad por usuario */}
      <div className="bg-white rounded-lg shadow-sm border p-6">
        <h2 className="font-semibold text-gray-700 mb-4">Actividad por Usuario (Top 10)</h2>
        {stats.actividad_usuarios.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-gray-500 border-b">
                  <th className="py-2 pr-4 font-medium">Usuario</th>
                  <th className="py-2 pr-4 font-medium w-1/2">Distribución</th>
                  <th className="py-2 font-medium text-right">Consultas</th>
                </tr>
              </thead>
              <tbody>
                {stats.actividad_usuarios.map((u) => {
                  const max = stats.actividad_usuarios[0].consultas || 1
                  return (
                    <tr key={u.usuario_id} className="border-b last:border-0">
                      <td className="py-2 pr-4 text-gray-700">{u.nombre}</td>
                      <td className="py-2 pr-4">
                        <div className="bg-gray-100 rounded-full h-2">
                          <div
                            className="bg-blue-500 h-2 rounded-full"
                            style={{ width: `${Math.max(4, (u.consultas / max) * 100)}%` }}
                          />
                        </div>
                      </td>
                      <td className="py-2 text-right font-medium text-gray-800">{u.consultas}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-gray-500 text-sm">Sin triajes registrados por usuarios.</p>
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
