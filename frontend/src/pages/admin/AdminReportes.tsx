import { useState } from 'react'
import { Link } from 'react-router-dom'
import api from '../../api/client'

export default function AdminReportes() {
  const [pacienteId, setPacienteId] = useState('')
  const [informe, setInforme] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const generarInforme = async () => {
    if (!pacienteId) {
      setError('Ingresa un ID de paciente.')
      return
    }
    setError('')
    setLoading(true)
    try {
      const res = await api.get(`/informes/paciente/${pacienteId}/texto`)
      setInforme(res.data.informe)
    } catch {
      setError('No se pudo generar el informe. Verifica el ID del paciente.')
      setInforme('')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-gray-800">Reportes</h1>
        <Link to="/admin" className="text-sm text-blue-600 hover:underline">← Volver al Dashboard</Link>
      </div>

      {/* Generar informe por paciente */}
      <div className="bg-white rounded-lg shadow-sm border p-6">
        <h2 className="font-semibold text-gray-700 mb-3">Informe por Paciente</h2>
        <div className="flex gap-3">
          <input
            type="number"
            value={pacienteId}
            onChange={(e) => setPacienteId(e.target.value)}
            placeholder="ID del paciente"
            className="flex-1 border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <button
            onClick={generarInforme}
            disabled={loading}
            className="bg-blue-600 text-white px-4 py-2 rounded-md text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
          >
            {loading ? 'Generando...' : 'Generar Informe'}
          </button>
        </div>
        {error && <p className="text-red-600 text-sm mt-2">{error}</p>}
      </div>

      {/* Resultado */}
      {informe && (
        <div className="bg-white rounded-lg shadow-sm border p-6">
          <div className="flex items-center justify-between mb-3">
            <h2 className="font-semibold text-gray-700">Informe Generado</h2>
            <button
              onClick={() => navigator.clipboard.writeText(informe)}
              className="text-xs bg-gray-100 px-3 py-1.5 rounded hover:bg-gray-200"
            >
              📋 Copiar
            </button>
          </div>
          <pre className="bg-gray-50 rounded-md p-4 text-xs text-gray-700 whitespace-pre-wrap overflow-auto max-h-96">
            {informe}
          </pre>
        </div>
      )}
    </div>
  )
}
