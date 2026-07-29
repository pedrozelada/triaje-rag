import { useState } from 'react'
import { Outlet, Link, useNavigate, useLocation } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

export default function Layout() {
  const { usuario, logout, isAdmin } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [menuAbierto, setMenuAbierto] = useState(false)

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  const navItems = [
    { to: '/', label: 'Inicio' },
    { to: '/triage/nuevo', label: 'Nuevo Triaje' },
    { to: '/pacientes', label: 'Pacientes' },
    { to: '/historial', label: 'Historial' },
    ...(isAdmin ? [{ to: '/admin', label: 'Admin' }] : []),
  ]

  const esActivo = (to: string) => {
    if (to === '/') return location.pathname === '/'
    return location.pathname.startsWith(to)
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2 text-lg font-bold text-blue-700">
            🏥 Sistema de Triaje
          </Link>
          <div className="flex items-center gap-3">
            <span className="hidden sm:inline text-sm text-gray-600">
              {usuario?.nombre_completo} <span className="text-gray-400">({usuario?.rol})</span>
            </span>
            <button
              onClick={handleLogout}
              className="text-sm text-red-600 hover:text-red-800 font-medium"
            >
              Salir
            </button>
            {/* Botón hamburguesa (móvil) */}
            <button
              onClick={() => setMenuAbierto(!menuAbierto)}
              className="sm:hidden p-1 rounded text-gray-600 hover:bg-gray-100"
              aria-label="Menú"
            >
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                {menuAbierto ? (
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                ) : (
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
                )}
              </svg>
            </button>
          </div>
        </div>
      </header>

      {/* Nav (desktop) */}
      <nav className="hidden sm:block bg-white border-b">
        <div className="max-w-7xl mx-auto px-4 flex gap-1">
          {navItems.map((item) => (
            <Link
              key={item.to}
              to={item.to}
              className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                esActivo(item.to)
                  ? 'text-blue-700 border-blue-700'
                  : 'text-gray-600 border-transparent hover:text-blue-700 hover:border-blue-300'
              }`}
            >
              {item.label}
            </Link>
          ))}
        </div>
      </nav>

      {/* Nav (móvil) */}
      {menuAbierto && (
        <nav className="sm:hidden bg-white border-b shadow-sm">
          <div className="px-4 py-2 space-y-1">
            {navItems.map((item) => (
              <Link
                key={item.to}
                to={item.to}
                onClick={() => setMenuAbierto(false)}
                className={`block px-3 py-2 rounded-md text-sm font-medium ${
                  esActivo(item.to)
                    ? 'bg-blue-50 text-blue-700'
                    : 'text-gray-600 hover:bg-gray-50'
                }`}
              >
                {item.label}
              </Link>
            ))}
          </div>
        </nav>
      )}

      {/* Content */}
      <main className="max-w-7xl mx-auto px-4 py-6">
        <Outlet />
      </main>
    </div>
  )
}
