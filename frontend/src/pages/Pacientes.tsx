import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import api from '../api/client'
import type { Paciente } from '../types'

export default function Pacientes() {
  const [pacientes, setPacientes] = useState<Paciente[]>([])
  const [busqueda, setBusqueda] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.get('/pacientes?limit=500')
      .then((res) => setPacientes(res.data))
      .finally(() => setLoading(false))
  }, [])

  const filtrados = busqueda.length >= 1
    ? pacientes.filter((p) =>
        `${p.ci} ${p.nombre} ${p.apellido}`.toLowerCase().includes(busqueda.toLowerCase())
      )
    : pacientes

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-bold text-gray-800">Pacientes</h1>
        <Link
          to="/pacientes/nuevo"
          className="bg-blue-600 text-white px-4 py-2 rounded-md text-sm font-medium hover:bg-blue-700"
        >
          + Nuevo Paciente
        </Link>
      </div>

      {/* Búsqueda */}
      <input
        type="text"
        value={busqueda}
        onChange={(e) => setBusqueda(e.target.value)}
        placeholder="Buscar por CI, nombre o apellido..."
        className="w-full border border-gray-300 rounded-md px-4 py-2 text-sm mb-4 focus:outline-none focus:ring-2 focus:ring-blue-500"
      />

      {loading ? (
        <p className="text-gray-500 text-center py-8">Cargando...</p>
      ) : filtrados.length === 0 ? (
        <p className="text-gray-500 text-center py-8">No se encontraron pacientes.</p>
      ) : (
        <div className="bg-white rounded-lg shadow-sm border overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b">
              <tr>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Nombre</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">CI</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Edad</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Sexo</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Acciones</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {filtrados.map((p) => (
                <tr key={p.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 font-medium">{p.nombre} {p.apellido}</td>
                  <td className="px-4 py-3 text-gray-600">{p.ci}</td>
                  <td className="px-4 py-3 text-gray-600">{p.edad} años</td>
                  <td className="px-4 py-3 text-gray-600">{p.sexo}</td>
                  <td className="px-4 py-3">
                    <div className="flex gap-2">
                      <Link to={`/pacientes/${p.id}`} className="text-blue-600 hover:underline">Ver</Link>
                      <Link to={`/pacientes/${p.id}/editar`} className="text-gray-600 hover:underline">Editar</Link>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
