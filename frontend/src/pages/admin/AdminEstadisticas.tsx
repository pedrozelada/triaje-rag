import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend, AreaChart, Area,
} from 'recharts'
import api from '../../api/client'
import type { EstadisticasTriaje } from '../../types'
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

// "2026-08-07" → "07/08/2026"
const formatoFecha = (fecha: string) => {
  const partes = fecha.split('-')
  return `${partes[2]}/${partes[1]}/${partes[0]}`
}

// "2026-08-07" → "07/08"
const formatoDia = (fecha: string) => {
  const partes = fecha.split('-')
  return `${partes[2]}/${partes[1]}`
}

const hoyISO = () => new Date().toISOString().split('T')[0]

const haceNDiasISO = (n: number) => {
  const d = new Date()
  d.setDate(d.getDate() - (n - 1))
  return d.toISOString().split('T')[0]
}

type Periodo = '30' | '90' | 'rango'

export default function AdminEstadisticas() {
  const [stats, setStats] = useState<EstadisticasTriaje | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Rango activo en la UI
  const [periodo, setPeriodo] = useState<Periodo>('30')
  const [desdeInput, setDesdeInput] = useState(haceNDiasISO(30))
  const [hastaInput, setHastaInput] = useState(hoyISO())

  const cargar = (params: Record<string, string | number>) => {
    setLoading(true)
    setError(null)
    api.get('/admin/estadisticas/triaje', { params })
      .then((res) => setStats(res.data))
      .catch(() => setError('Error al cargar las estadísticas.'))
      .finally(() => setLoading(false))
  }

  const aplicarPeriodo = (nuevoPeriodo: Periodo, diasNuevos = 30) => {
    setPeriodo(nuevoPeriodo)
    if (nuevoPeriodo === 'rango') {
      setDesdeInput(haceNDiasISO(30))
      setHastaInput(hoyISO())
      cargar({ fecha_desde: haceNDiasISO(30), fecha_hasta: hoyISO() })
    } else {
      cargar({ dias: diasNuevos })
    }
  }

  const aplicarRango = () => {
    if (!desdeInput || !hastaInput) return
    if (desdeInput > hastaInput) {
      setError('La fecha inicial no puede ser posterior a la final.')
      return
    }
    setError(null)
    setPeriodo('rango')
    cargar({ fecha_desde: desdeInput, fecha_hasta: hastaInput })
  }

  useEffect(() => {
    // Carga inicial: últimos 30 días
    cargar({ dias: 30 })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  if (loading) return <div className="text-center py-12 text-gray-500">Cargando estadísticas...</div>
  if (!stats) return <div className="text-center py-12 text-red-600">{error || 'Error al cargar datos.'}</div>

  const sexoData = stats.por_sexo.map((s) => ({
    name: SEXO_LABEL[s.sexo] || s.sexo,
    sexo: s.sexo,
    cantidad: s.cantidad,
  }))

  const chartData = stats.por_nivel.map((n) => ({
    name: n.nivel,
    cantidad: n.cantidad,
    fill: COLOR_HEX[n.nivel] || '#9CA3AF',
  }))

  const maxActividad = stats.actividad_usuarios[0]?.consultas || 1

  return (
    <div className="space-y-6">
      <PageHeader
        title="Estadísticas de Triaje"
        subtitle="Análisis demográfico y actividad según el período seleccionado"
        actions={
          <div className="flex gap-2">
            <Link to="/admin" className="text-sm bg-gray-100 px-3 py-1.5 rounded-md hover:bg-gray-200">
              Dashboard
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

      {/* Selector de período */}
      <div className="bg-white rounded-lg shadow-sm border p-4">
        <div className="flex flex-col lg:flex-row lg:items-end gap-4">
          <div className="flex flex-col gap-1">
            <span className="text-xs font-medium text-gray-500 uppercase tracking-wide">Período</span>
            <div className="flex gap-2">
              <button
                onClick={() => aplicarPeriodo('30')}
                className={`px-4 py-2 rounded-md text-sm font-medium border ${
                  periodo === '30' ? 'bg-blue-600 text-white border-blue-600' : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
                }`}
              >
                Últimos 30 días
              </button>
              <button
                onClick={() => aplicarPeriodo('90')}
                className={`px-4 py-2 rounded-md text-sm font-medium border ${
                  periodo === '90' ? 'bg-blue-600 text-white border-blue-600' : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
                }`}
              >
                Últimos 90 días
              </button>
              <button
                onClick={() => aplicarPeriodo('rango')}
                className={`px-4 py-2 rounded-md text-sm font-medium border ${
                  periodo === 'rango' ? 'bg-blue-600 text-white border-blue-600' : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
                }`}
              >
                Rango personalizado
              </button>
            </div>
          </div>

          {periodo === 'rango' && (
            <div className="flex flex-col sm:flex-row sm:items-end gap-2">
              <label className="flex flex-col gap-1 text-xs text-gray-500">
                Desde
                <input
                  type="date"
                  value={desdeInput}
                  max={hastaInput}
                  onChange={(e) => setDesdeInput(e.target.value)}
                  className="border border-gray-300 rounded-md px-3 py-1.5 text-sm"
                />
              </label>
              <label className="flex flex-col gap-1 text-xs text-gray-500">
                Hasta
                <input
                  type="date"
                  value={hastaInput}
                  min={desdeInput}
                  max={hoyISO()}
                  onChange={(e) => setHastaInput(e.target.value)}
                  className="border border-gray-300 rounded-md px-3 py-1.5 text-sm"
                />
              </label>
              <button
                onClick={aplicarRango}
                className="px-4 py-1.5 rounded-md text-sm font-medium bg-blue-600 text-white hover:bg-blue-700"
              >
                Aplicar
              </button>
            </div>
          )}
        </div>

        {/* Rango aplicado */}
        <p className="text-xs text-gray-400 mt-3">
          Período aplicado: <span className="font-medium text-gray-600">{formatoFecha(stats.fecha_desde)}</span> —{' '}
          <span className="font-medium text-gray-600">{formatoFecha(stats.fecha_hasta)}</span> ·{' '}
          <span className="font-medium text-gray-600">{stats.total_consultas} consultas</span>
        </p>
        {error && <p className="text-xs text-red-600 mt-2">{error}</p>}
      </div>

      {/* Cards resumen del período */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <StatCard label="Consultas del período" value={stats.total_consultas} />
        <StatCard label="Tiempo prom. respuesta" value={`${stats.promedio_tiempo_respuesta?.toFixed(2) ?? '—'}s`} />
        <StatCard label="Tokens consumidos" value={stats.total_tokens.toLocaleString('es-BO')} />
      </div>

      {/* Consultas por fecha */}
      <div className="bg-white rounded-lg shadow-sm border p-6">
        <h2 className="font-semibold text-gray-700 mb-4">Consultas por Fecha</h2>
        {stats.consultas_por_dia.some((d) => d.cantidad > 0) ? (
          <ResponsiveContainer width="100%" height={250}>
            <AreaChart data={stats.consultas_por_dia}>
              <XAxis dataKey="fecha" tickFormatter={formatoDia} tick={{ fontSize: 11 }} minTickGap={24} />
              <YAxis allowDecimals={false} />
              <Tooltip labelFormatter={(fecha) => `Día ${formatoFecha(String(fecha))}`} />
              <Area type="monotone" dataKey="cantidad" stroke="#3B82F6" fill="#3B82F6" fillOpacity={0.2} name="consultas" />
            </AreaChart>
          </ResponsiveContainer>
        ) : (
          <p className="text-gray-500 text-sm">Sin consultas en el período seleccionado.</p>
        )}
      </div>

      {/* Demografía */}
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
            <p className="text-gray-500 text-sm">Sin datos en el período.</p>
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

      {/* Urgencias del período */}
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

      {/* Motivos frecuentes */}
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
          <p className="text-gray-500 text-sm">Sin datos en el período.</p>
        )}
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
                {stats.actividad_usuarios.map((u) => (
                  <tr key={u.usuario_id} className="border-b last:border-0">
                    <td className="py-2 pr-4 text-gray-700">{u.nombre}</td>
                    <td className="py-2 pr-4">
                      <div className="bg-gray-100 rounded-full h-2">
                        <div
                          className="bg-blue-500 h-2 rounded-full"
                          style={{ width: `${Math.max(4, (u.consultas / maxActividad) * 100)}%` }}
                        />
                      </div>
                    </td>
                    <td className="py-2 text-right font-medium text-gray-800">{u.consultas}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-gray-500 text-sm">Sin triajes registrados por usuarios en el período.</p>
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