import type { ReactNode } from 'react'

type Variante = 'peligro' | 'advertencia' | 'info'

interface ModalConfirmacionProps {
  titulo: string
  mensaje: ReactNode
  onConfirmar: () => void
  onCancelar: () => void
  variante?: Variante
  confirmando?: boolean
  textoConfirmar?: string
  textoCancelar?: string
}

const TITULOS: Record<Variante, { icono: string; color: string; boton: string }> = {
  peligro: { icono: '⚠️', color: 'text-red-700', boton: 'bg-red-600 hover:bg-red-700' },
  advertencia: { icono: '⚠️', color: 'text-yellow-700', boton: 'bg-yellow-600 hover:bg-yellow-700' },
  info: { icono: 'ℹ️', color: 'text-blue-700', boton: 'bg-blue-600 hover:bg-blue-700' },
}

/**
 * Modal de confirmación reutilizable (misma convención visual que el
 * panel de administración). Reemplaza los confirm() nativos del navegador.
 */
export default function ModalConfirmacion({
  titulo, mensaje, onConfirmar, onCancelar, variante = 'info', confirmando = false,
  textoConfirmar = 'Confirmar', textoCancelar = 'Cancelar',
}: ModalConfirmacionProps) {
  const estilo = TITULOS[variante]
  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-md p-6 space-y-4" role="dialog" aria-modal="true">
        <h3 className={`text-lg font-semibold flex items-center gap-2 ${estilo.color}`}>
          <span aria-hidden="true">{estilo.icono}</span> {titulo}
        </h3>
        <div className="text-sm text-gray-600">{mensaje}</div>
        <div className="flex justify-end gap-2">
          <button
            onClick={onCancelar}
            disabled={confirmando}
            className="text-sm px-4 py-2 rounded-md bg-gray-100 hover:bg-gray-200 disabled:opacity-50"
          >
            {textoCancelar}
          </button>
          <button
            onClick={onConfirmar}
            disabled={confirmando}
            className={`text-sm px-4 py-2 rounded-md text-white font-medium disabled:opacity-50 ${estilo.boton}`}
          >
            {confirmando ? 'Procesando...' : textoConfirmar}
          </button>
        </div>
      </div>
    </div>
  )
}