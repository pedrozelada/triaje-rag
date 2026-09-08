import { useState, useEffect } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import api from '../api/client'
import type { Paciente, ConsultaTriage } from '../types'
import ModalConfirmacion from '../components/ModalConfirmacion'
import { formatoFechaHora } from '../utils/format'
import { claseNivel } from '../utils/colores'

export default function PacienteDetalle() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [paciente, setPaciente] = useState<Paciente | null>(null)
  const [consultas, setConsultas] = useState<ConsultaTriage[]>([])
  const [loading, setLoading] = useState(true)
  const [confirmarEliminar, setConfirmarEliminar] = useState(false)
  const [eliminando, setEliminando] = useState(false)

  useEffect(() => {
    Promise.all([
      api.get(`/pacientes/${id}`),
      api.get(`/triage?paciente_id=${id}&limit=50`),
    ]).then(([pRes, cRes]) => {
      setPaciente(pRes.data)
      setConsultas(cRes.data)
    }).finally(() => setLoading(false))
  }, [id])

  const handleEliminar = async () => {
    setEliminando(true)
    try {
      await api.delete(`/pacientes/${id}`)
      navigate('/pacientes')
    } catch {
      setEliminando(false)
      setConfirmarEliminar(false)
    }
  }

  if (loading) return <div className="text-center py-12 text-gray-500">Cargando...</div>
  if (!paciente) return <div className="text-center py-12 text-red-600">Paciente no encontrado.</div>

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      {/* Header */}
      <div className="bg-white rounded-lg shadow-sm border p-6">
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-xl font-bold text-gray-800">
              {paciente.nombre} {paciente.apellido}
            </h1>
            <p className="text-sm text-gray-500 mt-1">
              {paciente.edad} años · {paciente.sexo} · CI: {paciente.ci}
            </p>
            {paciente.telefono && <p className="text-sm text-gray-500">📞 {paciente.telefono}</p>}
            {paciente.direccion && <p className="text-sm text-gray-500">📍 {paciente.direccion}</p>}
          </div>
          <div className="flex gap-2">
            <Link
              to={`/pacientes/${id}/editar`}
              className="text-sm bg-gray-100 px-3 py-1.5 rounded-md hover:bg-gray-200"
            >
              ✏️ Editar
            </Link>
            <button
              onClick={() => setConfirmarEliminar(true)}
              className="text-sm bg-red-50 text-red-700 px-3 py-1.5 rounded-md hover:bg-red-100"
            >
              🗑 Eliminar
            </button>
          </div>
        </div>
      </div>

      {/* Historial de consultas */}
      <div className="bg-white rounded-lg shadow-sm border p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-semibold text-gray-700">Historial de Consultas ({consultas.length})</h2>
          <Link
            to={`/triage/nuevo?paciente_id=${id}`}
            className="text-sm bg-blue-600 text-white px-3 py-1.5 rounded-md hover:bg-blue-700"
          >
            + Nueva Consulta
          </Link>
        </div>

        {consultas.length === 0 ? (
          <p className="text-gray-500 text-sm">Sin consultas registradas.</p>
        ) : (
          <div className="space-y-3">
            {consultas.map((c) => (
              <Link
                key={c.id}
                to={`/triage/resultado/${c.id}`}
                className="block border rounded-lg p-4 hover:bg-gray-50 transition-colors"
              >
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-600">
                    {formatoFechaHora(c.fecha_hora)}
                  </span>
                  {c.nivel_urgencia && (
                    <span className={`text-xs font-medium px-2 py-1 rounded-full capitalize ${claseNivel(c.nivel_urgencia)}`}>
                      {c.nivel_urgencia}
                    </span>
                  )}
                </div>
                <p className="text-sm font-medium text-gray-800 mt-1">
                  {c.motivo_consulta || c.sintomas?.slice(0, 80) || 'Sin descripción'}
                </p>
              </Link>
            ))}
          </div>
        )}
      </div>

      {/* Confirmación de eliminación (modal consistente con el sistema) */}
      {confirmarEliminar && paciente && (
        <ModalConfirmacion
          titulo="Eliminar Paciente"
          variante="peligro"
          confirmando={eliminando}
          textoConfirmar="Sí, Eliminar"
          onConfirmar={handleEliminar}
          onCancelar={() => setConfirmarEliminar(false)}
          mensaje={
            <>
              Vas a eliminar a <strong>{paciente.nombre} {paciente.apellido}</strong> y{' '}
              <strong>todas sus consultas de triaje</strong>. Esta acción{' '}
              <strong>no se puede deshacer</strong>. ¿Deseas continuar?
            </>
          }
        />
      )}
    </div>
  )
}
