import { Link, useLocation } from 'react-router-dom'

const RUTA_NOMBRES: Record<string, string> = {
  '': 'Inicio',
  'triage': 'Triaje',
  'nuevo': 'Nuevo',
  'resultado': 'Resultado',
  'pacientes': 'Pacientes',
  'editar': 'Editar',
  'historial': 'Historial',
  'admin': 'Administración',
  'usuarios': 'Usuarios',
  'reportes': 'Reportes',
}

export default function Breadcrumb() {
  const location = useLocation()
  const partes = location.pathname.split('/').filter(Boolean)

  if (partes.length === 0) return null

  const crumbs = partes.map((parte, i) => {
    const ruta = '/' + partes.slice(0, i + 1).join('/')
    const esUltimo = i === partes.length - 1
    // Si es un ID numérico, mostrar como "Detalle"
    const nombre = /^\d+$/.test(parte)
      ? 'Detalle'
      : RUTA_NOMBRES[parte] || parte.charAt(0).toUpperCase() + parte.slice(1)

    return { ruta, nombre, esUltimo }
  })

  return (
    <nav aria-label="Breadcrumb" className="mb-4">
      <ol className="flex items-center gap-1 text-sm text-gray-500 flex-wrap">
        <li>
          <Link to="/" className="hover:text-blue-600 transition-colors">Inicio</Link>
        </li>
        {crumbs.map((c) => (
          <li key={c.ruta} className="flex items-center gap-1">
            <span className="text-gray-300">/</span>
            {c.esUltimo ? (
              <span className="text-gray-800 font-medium">{c.nombre}</span>
            ) : (
              <Link to={c.ruta} className="hover:text-blue-600 transition-colors">{c.nombre}</Link>
            )}
          </li>
        ))}
      </ol>
    </nav>
  )
}
