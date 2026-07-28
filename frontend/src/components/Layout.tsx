import { Outlet, Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

export default function Layout() {
  const { usuario, logout, isAdmin } = useAuth()
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2 text-lg font-bold text-blue-700">
            🏥 Sistema de Triaje
          </Link>
          <div className="flex items-center gap-4">
            <span className="text-sm text-gray-600">
              {usuario?.nombre_completo} ({usuario?.rol})
            </span>
            <button
              onClick={handleLogout}
              className="text-sm text-red-600 hover:text-red-800 font-medium"
            >
              Salir
            </button>
          </div>
        </div>
      </header>

      {/* Nav */}
      <nav className="bg-white border-b">
        <div className="max-w-7xl mx-auto px-4 flex gap-1">
          <NavLink to="/">Inicio</NavLink>
          <NavLink to="/triage/nuevo">Nuevo Triaje</NavLink>
          <NavLink to="/pacientes">Pacientes</NavLink>
          <NavLink to="/historial">Historial</NavLink>
          {isAdmin && <NavLink to="/admin">Admin</NavLink>}
        </div>
      </nav>

      {/* Content */}
      <main className="max-w-7xl mx-auto px-4 py-6">
        <Outlet />
      </main>
    </div>
  )
}

function NavLink({ to, children }: { to: string; children: React.ReactNode }) {
  return (
    <Link
      to={to}
      className="px-4 py-2 text-sm font-medium text-gray-600 hover:text-blue-700 hover:border-b-2 hover:border-blue-700 transition-colors"
    >
      {children}
    </Link>
  )
}
