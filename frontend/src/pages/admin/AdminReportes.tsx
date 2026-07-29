import { useState } from 'react'
import api from '../../api/client'
import PageHeader from '../../components/PageHeader'
import FormField from '../../components/FormField'

export default function AdminReportes() {
  const [pacienteId, setPacienteId] = useState('')
  const [informe, setInforme] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const generarInforme = async () => {
    if (!pacienteId.trim()) {
      setError('Ingresa el ID del paciente para generar el informe.')
      return
    }
    if (!/^\d+$/.test(pacienteId.trim())) {
      setError('El ID debe ser un número entero.')
      return
    }
    setError('')
    setLoading(true)
    try {
      const res = await api.get(`/informes/paciente/${pacienteId.trim()}/texto`)
      setInforme(res.data.informe)
    } catch {
      setError('No se pudo generar el informe. Verifica que el ID del paciente exista.')
      setInforme('')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <PageHeader title="Reportes" subtitle="Genera informes por paciente" />

      {/* Generar informe por paciente */}
      <div className="bg-white rounded-lg shadow-sm border p-6">
        <h2 className="font-semibold text-gray-700 mb-3">Informe por Paciente</h2>
        <div className="flex flex-col sm:flex-row gap-3">
          <div className="flex-1">
            <FormField label="ID del Paciente" required tooltip="Número identificador del paciente" error={error}>
              <input
                type="number"
                value={pacienteId}
                onChange={(e) => { setPacienteId(e.target.value); setError('') }}
                placeholder="Ej: 1"
                min="1"
                className={`w-full border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                  error ? 'border-red-400 bg-red-50' : 'border-gray-300'
                }`}
              />
            </FormField>
          </div>
          <div className="flex items-end">
            <button
              onClick={generarInforme}
              disabled={loading}
              className="bg-blue-600 text-white px-4 py-2 rounded-md text-sm font-medium hover:bg-blue-700 disabled:opacity-50 whitespace-nowrap"
            >
              {loading ? 'Generando...' : 'Generar Informe'}
            </button>
          </div>
        </div>
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
