import { Link } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import PageHeader from '../components/PageHeader'

export default function Inicio() {
  const { usuario, isAdmin } = useAuth()

  return (
    <div className="max-w-2xl mx-auto">
      <PageHeader title="Inicio" subtitle={`Bienvenido/a, ${usuario?.nombre_completo ?? ''}`} />
      <div className="grid grid-cols-2 gap-4 py-6">
        <ActionCard
          to="/triage/nuevo"
          icon="➕"
          title="Nuevo Triaje"
          desc="Evaluar paciente con IA"
        />
        <ActionCard
          to="/pacientes"
          icon="👤"
          title="Pacientes"
          desc="Buscar, registrar, editar"
        />
        <ActionCard
          to="/historial"
          icon="📋"
          title="Historial"
          desc="Consultas anteriores"
        />
        {isAdmin ? (
          <ActionCard
            to="/admin"
            icon="📈"
            title="Administración"
            desc="Dashboard, usuarios, reportes"
          />
        ) : (
          <ActionCard
            to="/historial"
            icon="📈"
            title="Estadísticas"
            desc="Resumen de actividad"
          />
        )}
      </div>
    </div>
  )
}

function ActionCard({ to, icon, title, desc }: { to: string; icon: string; title: string; desc: string }) {
  return (
    <Link
      to={to}
      className="bg-white rounded-xl shadow-sm border p-6 hover:shadow-md hover:border-blue-300 transition-all text-left"
    >
      <span className="text-3xl">{icon}</span>
      <h2 className="mt-3 font-semibold text-gray-800">{title}</h2>
      <p className="text-sm text-gray-500 mt-1">{desc}</p>
    </Link>
  )
}
