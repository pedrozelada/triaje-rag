import { useState, useEffect } from 'react'
import api from '../../api/client'
import PageHeader from '../../components/PageHeader'
import AdminNav from '../../components/AdminNav'
import FormField from '../../components/FormField'
import { useAuth } from '../../context/AuthContext'
import { formatoFechaHora } from '../../utils/format'
import type { Paciente } from '../../types'

export default function AdminReportes() {
  const { usuario: usuarioActual } = useAuth()
  const [pacientes, setPacientes] = useState<Paciente[]>([])
  const [busqueda, setBusqueda] = useState('')
  const [pacienteSel, setPacienteSel] = useState<Paciente | null>(null)
  const [mostrarLista, setMostrarLista] = useState(false)
  const [informe, setInforme] = useState('')
  const [generadoEn, setGeneradoEn] = useState('')
  const [loading, setLoading] = useState(false)
  const [descargando, setDescargando] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    api.get('/pacientes?limit=500')
      .then((res) => setPacientes(res.data))
      .catch(() => setError('No se pudo cargar la lista de pacientes.'))
  }, [])

  const normalizar = (texto: string) =>
    texto.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '')

  const filtrados = pacientes.filter((p) => {
    const texto = normalizar(`${p.nombre} ${p.apellido} ${p.ci}`)
    return texto.includes(normalizar(busqueda.trim()))
  })

  const seleccionarPaciente = (p: Paciente) => {
    setPacienteSel(p)
    setBusqueda(`${p.nombre} ${p.apellido}`)
    setMostrarLista(false)
    setError('')
  }

  const limpiarSeleccion = () => {
    setPacienteSel(null)
    setBusqueda('')
    setMostrarLista(false)
    setError('')
  }

  const generarInforme = async () => {
    if (!pacienteSel) {
      setError('Busca y selecciona un paciente para generar el informe.')
      return
    }
    setError('')
    setLoading(true)
    try {
      const res = await api.get(`/informes/paciente/${pacienteSel.id}/texto`)
      setInforme(res.data.informe)
      setGeneradoEn(formatoFechaHora(new Date()))
    } catch {
      setError('No se pudo generar el informe. Verifica que el paciente tenga consultas registradas.')
      setInforme('')
      setGeneradoEn('')
    } finally {
      setLoading(false)
    }
  }

  const descargarPdf = async () => {
    if (!pacienteSel) return
    setDescargando(true)
    try {
      // responseType 'blob' + JWT en el header (un <a href> simple no autenticaría)
      const res = await api.get(`/informes/paciente/${pacienteSel.id}/pdf`, {
        responseType: 'blob',
      })
      const url = URL.createObjectURL(res.data)
      const a = document.createElement('a')
      a.href = url
      // Preferir el nombre que envía el backend (Content-Disposition)
      const disposicion = res.headers['content-disposition'] as string | undefined
      const coincidencia = disposicion?.match(/filename="?([^";]+)"?/i)
      a.download = coincidencia?.[1] || `informe_paciente_${pacienteSel.id}.pdf`
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(url)
    } catch {
      setError('No se pudo descargar el PDF.')
    } finally {
      setDescargando(false)
    }
  }

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <PageHeader title="Reportes" subtitle="Genera informes por paciente" actions={<AdminNav />} />

      {/* Generar informe por paciente */}
      <div className="bg-white rounded-lg shadow-sm border p-6">
        <h2 className="font-semibold text-gray-700 mb-3">Informe por Paciente</h2>
        <div className="flex flex-col sm:flex-row gap-3">
          <div className="flex-1 relative">
            <FormField label="Buscar Paciente (nombre)" required tooltip="Busca por nombre, apellido o CI" error={error}>
              <div className="relative">
                <input
                  type="text"
                  value={busqueda}
                  onChange={(e) => {
                    setBusqueda(e.target.value)
                    setPacienteSel(null)
                    setMostrarLista(true)
                    setError('')
                  }}
                  onFocus={() => setMostrarLista(true)}
                  placeholder="Escribe nombre, apellido o CI..."
                  autoComplete="off"
                  className={`w-full border rounded-md px-3 py-2 pr-9 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                    error ? 'border-red-400 bg-red-50' : 'border-gray-300'
                  }`}
                />
                {busqueda && (
                  <button
                    type="button"
                    onClick={limpiarSeleccion}
                    className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                    aria-label="Limpiar búsqueda"
                  >
                    ✕
                  </button>
                )}
              </div>
            </FormField>
            {/* Lista de resultados (combobox ligero) */}
            {mostrarLista && busqueda.trim() && (
              <div className="absolute z-10 w-full mt-1 bg-white border border-gray-200 rounded-md shadow-lg max-h-60 overflow-auto">
                {filtrados.length === 0 ? (
                  <div className="px-3 py-2 text-sm text-gray-500">
                    No se encontraron pacientes con «{busqueda.trim()}».
                  </div>
                ) : (
                  filtrados.map((p) => (
                    <button
                      key={p.id}
                      type="button"
                      onClick={() => seleccionarPaciente(p)}
                      className="w-full text-left px-3 py-2 text-sm hover:bg-blue-50 focus:bg-blue-50 focus:outline-none border-b border-gray-50 last:border-b-0"
                    >
                      <span className="font-medium text-gray-800">{p.apellido} {p.nombre}</span>
                      <span className="ml-2 text-xs text-gray-500">CI {p.ci}</span>
                      <span className="ml-2 text-xs text-gray-400">#{p.id}</span>
                    </button>
                  ))
                )}
              </div>
            )}
          </div>

          <div className="flex items-end gap-2">
            <button
              onClick={generarInforme}
              disabled={loading || !pacienteSel}
              className="bg-blue-600 text-white px-4 py-2 rounded-md text-sm font-medium hover:bg-blue-700 disabled:opacity-50 whitespace-nowrap"
            >
              {loading ? 'Generando...' : 'Generar Informe'}
            </button>
            <button
              onClick={descargarPdf}
              disabled={descargando || !pacienteSel}
              className="bg-gray-100 text-gray-700 px-4 py-2 rounded-md text-sm font-medium hover:bg-gray-200 disabled:opacity-50 whitespace-nowrap"
            >
              {descargando ? 'Descargando...' : '📄 Descargar PDF'}
            </button>
          </div>
        </div>
        {pacienteSel && (
          <p className="mt-2 text-xs text-gray-500">
            Paciente seleccionado: <span className="font-medium text-gray-700">{pacienteSel.apellido} {pacienteSel.nombre}</span> (CI {pacienteSel.ci})
          </p>
        )}
      </div>

      {/* Resultado */}
      {informe && (
        <div className="bg-white rounded-lg shadow-sm border p-6">
          <div className="flex items-center justify-between mb-2">
            <h2 className="font-semibold text-gray-700">Informe Generado</h2>
            <button
              onClick={() => navigator.clipboard.writeText(informe)}
              className="text-xs bg-gray-100 px-3 py-1.5 rounded hover:bg-gray-200"
            >
              📋 Copiar
            </button>
          </div>
          {/* Metadatos del reporte: fecha, usuario y filtros utilizados */}
          <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-gray-500 mb-3 border-b pb-3">
            <span>📅 Generado: {generadoEn}</span>
            <span>👤 Usuario: {usuarioActual?.nombre_completo || '—'}</span>
            <span>🔎 Filtro: {pacienteSel ? `${pacienteSel.apellido} ${pacienteSel.nombre} (CI ${pacienteSel.ci})` : '—'}</span>
          </div>
          <pre className="bg-gray-50 rounded-md p-4 text-xs text-gray-700 whitespace-pre-wrap overflow-auto max-h-96">
            {informe}
          </pre>
        </div>
      )}
    </div>
  )
}
