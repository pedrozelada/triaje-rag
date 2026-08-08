import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './context/AuthContext'
import Layout from './components/Layout'
import Login from './pages/Login'
import Inicio from './pages/Inicio'
import NuevoTriage from './pages/NuevoTriage'
import ResultadoTriage from './pages/ResultadoTriage'
import Pacientes from './pages/Pacientes'
import NuevoPaciente from './pages/NuevoPaciente'
import PacienteDetalle from './pages/PacienteDetalle'
import EditarPaciente from './pages/EditarPaciente'
import Historial from './pages/Historial'
import AdminDashboard from './pages/admin/AdminDashboard'
import AdminEstadisticas from './pages/admin/AdminEstadisticas'
import AdminUsuarios from './pages/admin/AdminUsuarios'
import AdminReportes from './pages/admin/AdminReportes'

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { usuario, loading } = useAuth()
  if (loading) return <div className="flex items-center justify-center h-screen">Cargando...</div>
  if (!usuario) return <Navigate to="/login" replace />
  return <>{children}</>
}

function AdminRoute({ children }: { children: React.ReactNode }) {
  const { usuario, loading, isAdmin } = useAuth()
  if (loading) return <div className="flex items-center justify-center h-screen">Cargando...</div>
  if (!usuario) return <Navigate to="/login" replace />
  if (!isAdmin) return <Navigate to="/" replace />
  return <>{children}</>
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route element={<ProtectedRoute><Layout /></ProtectedRoute>}>
        <Route path="/" element={<Inicio />} />
        <Route path="/triage/nuevo" element={<NuevoTriage />} />
        <Route path="/triage/resultado/:id" element={<ResultadoTriage />} />
        <Route path="/pacientes" element={<Pacientes />} />
        <Route path="/pacientes/nuevo" element={<NuevoPaciente />} />
        <Route path="/pacientes/:id" element={<PacienteDetalle />} />
        <Route path="/pacientes/:id/editar" element={<EditarPaciente />} />
        <Route path="/historial" element={<Historial />} />
        <Route path="/admin" element={<AdminRoute><AdminDashboard /></AdminRoute>} />
        <Route path="/admin/estadisticas" element={<AdminRoute><AdminEstadisticas /></AdminRoute>} />
        <Route path="/admin/usuarios" element={<AdminRoute><AdminUsuarios /></AdminRoute>} />
        <Route path="/admin/reportes" element={<AdminRoute><AdminReportes /></AdminRoute>} />
      </Route>
    </Routes>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <AppRoutes />
      </BrowserRouter>
    </AuthProvider>
  )
}
