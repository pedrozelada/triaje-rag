import Breadcrumb from './Breadcrumb'

interface PageHeaderProps {
  title: string
  subtitle?: string
  actions?: React.ReactNode
}

/**
 * Encabezado de página con breadcrumb, título y acciones opcionales.
 */
export default function PageHeader({ title, subtitle, actions }: PageHeaderProps) {
  return (
    <div className="mb-6">
      <Breadcrumb />
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-gray-800">{title}</h1>
          {subtitle && <p className="text-sm text-gray-500 mt-0.5">{subtitle}</p>}
        </div>
        {actions && <div className="shrink-0">{actions}</div>}
      </div>
    </div>
  )
}
