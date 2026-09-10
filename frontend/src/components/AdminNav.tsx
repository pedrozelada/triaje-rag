import { Link, useLocation } from 'react-router-dom'

const SECCIONES = [
  { to: '/admin', label: 'Dashboard' },
  { to: '/admin/estadisticas', label: 'Estadísticas de Triaje' },
  { to: '/admin/estadisticas/llm', label: 'Estadísticas de LLM' },
  { to: '/admin/usuarios', label: 'Usuarios' },
  { to: '/admin/reportes', label: 'Reportes' },
]

/** Indica si la sección `to` corresponde a la ruta actual. */
const esActiva = (to: string, pathname: string) => {
  if (to === '/admin') return pathname === '/admin'
  if (to === '/admin/estadisticas') {
    // `/admin/estadisticas/llm` también empieza con `/admin/estadisticas`
    return (
      pathname.startsWith('/admin/estadisticas') &&
      !pathname.startsWith('/admin/estadisticas/llm')
    )
  }
  return pathname.startsWith(to)
}

/**
 * Mini navegador compartido por las pantallas de administración.
 * Muestra links a las demás secciones del admin y oculta el de la página actual.
 */
export default function AdminNav() {
  const { pathname } = useLocation()

  return (
    <div className="flex flex-wrap gap-2">
      {SECCIONES.filter((s) => !esActiva(s.to, pathname)).map((s) => (
        <Link
          key={s.to}
          to={s.to}
          className="text-sm bg-gray-100 px-3 py-1.5 rounded-md hover:bg-gray-200"
        >
          {s.label}
        </Link>
      ))}
    </div>
  )
}