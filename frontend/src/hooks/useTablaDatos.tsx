import { useMemo, useState, type ReactNode } from 'react'

interface OpcionesTabla<T> {
  columnaInicial: string
  direccionInicial?: 'asc' | 'desc'
  porPagina?: number
  /** Extrae el valor de ordenamiento de una fila para una columna dada. */
  obtenerValor: (fila: T, columna: string) => string | number | boolean | null
}

/**
 * Hook de listados: ordenamiento por columna (asc/desc) y paginación
 * del lado del cliente, con total de registros.
 */
export function useTablaDatos<T>(datos: T[], { columnaInicial, direccionInicial = 'asc', porPagina = 20, obtenerValor }: OpcionesTabla<T>) {
  const [ordenColumna, setOrdenColumna] = useState(columnaInicial)
  const [ordenDireccion, setOrdenDireccion] = useState<'asc' | 'desc'>(direccionInicial)
  const [pagina, setPagina] = useState(1)

  const ordenarPor = (columna: string) => {
    if (columna === ordenColumna) {
      setOrdenDireccion((d) => (d === 'asc' ? 'desc' : 'asc'))
    } else {
      setOrdenColumna(columna)
      setOrdenDireccion('asc')
    }
    setPagina(1)
  }

  const ordenados = useMemo(() => {
    const copia = [...datos]
    copia.sort((a, b) => {
      const va = obtenerValor(a, ordenColumna)
      const vb = obtenerValor(b, ordenColumna)
      if (va == null || va === '') return 1
      if (vb == null || vb === '') return -1
      let cmp: number
      if (typeof va === 'number' && typeof vb === 'number') cmp = va - vb
      else if (typeof va === 'boolean' && typeof vb === 'boolean') cmp = Number(va) - Number(vb)
      else cmp = String(va).localeCompare(String(vb), 'es', { sensitivity: 'base' })
      return ordenDireccion === 'asc' ? cmp : -cmp
    })
    return copia
  }, [datos, ordenColumna, ordenDireccion, obtenerValor])

  const totalPaginas = Math.max(1, Math.ceil(ordenados.length / porPagina))
  const paginaActual = Math.min(pagina, totalPaginas)
  const paginados = useMemo(
    () => ordenados.slice((paginaActual - 1) * porPagina, paginaActual * porPagina),
    [ordenados, paginaActual, porPagina],
  )

  return {
    ordenados,
    paginados,
    ordenColumna,
    ordenDireccion,
    ordenarPor,
    paginaActual,
    totalPaginas,
    cambiarPagina: setPagina,
    total: datos.length,
  }
}

/** Indicador de orden (▲/▼) para encabezados de tabla ordenables. */
export function FlechaOrden({ activa, direccion }: { activa: boolean; direccion: 'asc' | 'desc' }) {
  if (!activa) return <span className="text-gray-300 ml-1">↕</span>
  return <span className="text-blue-600 ml-1">{direccion === 'asc' ? '▲' : '▼'}</span>
}

/** Encabezado de tabla ordenable (th clickeable). */
export function ThOrdenable({
  columna, label, ordenColumna, ordenDireccion, ordenarPor, className = '',
}: {
  columna: string
  label: string
  ordenColumna: string
  ordenDireccion: 'asc' | 'desc'
  ordenarPor: (columna: string) => void
  className?: string
}) {
  return (
    <th className={`text-left px-4 py-3 font-medium text-gray-600 ${className}`}>
      <button
        type="button"
        onClick={() => ordenarPor(columna)}
        className="inline-flex items-center hover:text-blue-700 transition-colors"
      >
        {label}
        <FlechaOrden activa={ordenColumna === columna} direccion={ordenDireccion} />
      </button>
    </th>
  )
}

/** Controles de paginación (‹ Anterior / Siguiente ›). */
export function ControlesPaginacion({
  paginaActual, totalPaginas, cambiarPagina, total, porPagina,
}: {
  paginaActual: number
  totalPaginas: number
  cambiarPagina: (pagina: number) => void
  total: number
  porPagina: number
}) {
  if (total === 0) return null
  const desde = (paginaActual - 1) * porPagina + 1
  const hasta = Math.min(paginaActual * porPagina, total)
  return (
    <div className="flex items-center justify-between px-4 py-3 border-t text-sm text-gray-600 flex-wrap gap-2">
      <span>
        Mostrando {desde}–{hasta} de {total} registro(s)
      </span>
      <div className="flex items-center gap-2">
        <button
          onClick={() => cambiarPagina(paginaActual - 1)}
          disabled={paginaActual <= 1}
          className="px-3 py-1 rounded border border-gray-300 hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed"
        >
          ‹ Anterior
        </button>
        <span>
          Página {paginaActual} de {totalPaginas}
        </span>
        <button
          onClick={() => cambiarPagina(paginaActual + 1)}
          disabled={paginaActual >= totalPaginas}
          className="px-3 py-1 rounded border border-gray-300 hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed"
        >
          Siguiente ›
        </button>
      </div>
    </div>
  )
}

/** Estilos comunes para inputs de búsqueda y filtros de listados. */
export const inputFiltroClass = 'border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500'

export function EtiquetaFiltro({ children }: { children: ReactNode }) {
  return <span className="text-sm text-gray-600 whitespace-nowrap">{children}</span>
}