import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import api from '../api/client'
import type { Paciente } from '../types'
import PageHeader from '../components/PageHeader'
import { useTablaDatos, ThOrdenable, ControlesPaginacion, inputFiltroClass, EtiquetaFiltro } from '../hooks/useTablaDatos'

export default function Pacientes() {
  const [pacientes, setPacientes] = useState<Paciente[]>([])
  const [busqueda, setBusqueda] = useState('')
  const [filtroSexo, setFiltroSexo] = useState('todos')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.get('/pacientes?limit=500')
      .then((res) => setPacientes(res.data))
      .finally(() => setLoading(false))
  }, [])

  const filtrados = pacientes.filter((p) => {
    const okTexto = busqueda.length >= 1
      ? `${p.ci} ${p.nombre} ${p.apellido}`.toLowerCase().includes(busqueda.toLowerCase())
      : true
    const okSexo = filtroSexo === 'todos' || p.sexo === filtroSexo
    return okTexto && okSexo
  })

  const tabla = useTablaDatos(filtrados, {
    columnaInicial: 'nombre',
    porPagina: 20,
    obtenerValor: (p, col) => {
      switch (col) {
        case 'nombre': return `${p.apellido} ${p.nombre}`
        case 'ci': return p.ci
        case 'edad': return p.edad
        case 'sexo': return p.sexo
        default: return null
      }
    },
  })

  return (
    <div>
      <PageHeader
        title="Pacientes"
        subtitle={`${filtrados.length} de ${pacientes.length} paciente(s) registrado(s)`}
        actions={
          <Link
            to="/pacientes/nuevo"
            className="inline-block bg-blue-600 text-white px-4 py-2 rounded-md text-sm font-medium hover:bg-blue-700"
          >
            + Nuevo Paciente
          </Link>
        }
      />

      {/* Búsqueda y filtros */}
      <div className="flex flex-col sm:flex-row gap-3 mb-4">
        <input
          type="text"
          value={busqueda}
          onChange={(e) => setBusqueda(e.target.value)}
          placeholder="Buscar por CI, nombre o apellido..."
          maxLength={50}
          className={`${inputFiltroClass} flex-1`}
        />
        <EtiquetaFiltro>Sexo:</EtiquetaFiltro>
        <select value={filtroSexo} onChange={(e) => setFiltroSexo(e.target.value)} className={inputFiltroClass}>
          <option value="todos">Todos</option>
          <option value="M">Masculino</option>
          <option value="F">Femenino</option>
          <option value="Otro">Otro</option>
        </select>
      </div>

      {loading ? (
        <p className="text-gray-500 text-center py-8">Cargando...</p>
      ) : filtrados.length === 0 ? (
        <p className="text-gray-500 text-center py-8">No se encontraron pacientes.</p>
      ) : (
        <div className="bg-white rounded-lg shadow-sm border overflow-x-auto">
          <table className="w-full text-sm min-w-[500px]">
            <thead className="bg-gray-50 border-b">
              <tr>
                <ThOrdenable columna="nombre" label="Nombre" ordenColumna={tabla.ordenColumna} ordenDireccion={tabla.ordenDireccion} ordenarPor={tabla.ordenarPor} />
                <ThOrdenable columna="ci" label="CI" ordenColumna={tabla.ordenColumna} ordenDireccion={tabla.ordenDireccion} ordenarPor={tabla.ordenarPor} />
                <ThOrdenable columna="edad" label="Edad" ordenColumna={tabla.ordenColumna} ordenDireccion={tabla.ordenDireccion} ordenarPor={tabla.ordenarPor} />
                <ThOrdenable columna="sexo" label="Sexo" ordenColumna={tabla.ordenColumna} ordenDireccion={tabla.ordenDireccion} ordenarPor={tabla.ordenarPor} />
                <th className="text-left px-4 py-3 font-medium text-gray-600">Acciones</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {tabla.paginados.map((p) => (
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
          <ControlesPaginacion
            paginaActual={tabla.paginaActual}
            totalPaginas={tabla.totalPaginas}
            cambiarPagina={tabla.cambiarPagina}
            total={filtrados.length}
            porPagina={20}
          />
        </div>
      )}
    </div>
  )
}
