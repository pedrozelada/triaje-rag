import { useState, type ReactNode } from 'react'

interface FormFieldProps {
  label: string
  required?: boolean
  tooltip?: string
  error?: string
  children: ReactNode
}

/**
 * Wrapper para campos de formulario.
 * - Muestra (*) rojo en campos obligatorios
 * - Muestra ícono (?) con tooltip para campos que generan dudas
 * - Muestra error junto al campo
 */
export default function FormField({ label, required, tooltip, error, children }: FormFieldProps) {
  const [showTooltip, setShowTooltip] = useState(false)

  return (
    <div>
      <label className="flex items-center gap-1 text-sm font-medium text-gray-700 mb-1">
        <span>{label}</span>
        {required && <span className="text-red-500 font-bold">*</span>}
        {tooltip && (
          <span className="relative inline-flex">
            <button
              type="button"
              onMouseEnter={() => setShowTooltip(true)}
              onMouseLeave={() => setShowTooltip(false)}
              onClick={() => setShowTooltip(!showTooltip)}
              className="w-4 h-4 rounded-full bg-gray-200 text-gray-500 text-[10px] font-bold flex items-center justify-center cursor-help hover:bg-gray-300 transition-colors"
              aria-label={`Ayuda: ${label}`}
            >
              ?
            </button>
            {showTooltip && (
              <span className="absolute bottom-full left-1/2 -translate-x-1/2 mb-1 px-2 py-1 bg-gray-800 text-white text-xs rounded whitespace-nowrap z-50 max-w-[200px] !whitespace-normal text-center">
                {tooltip}
              </span>
            )}
          </span>
        )}
      </label>
      {children}
      {error && (
        <p className="mt-1 text-xs text-red-600 flex items-center gap-1">
          <svg className="w-3 h-3 shrink-0" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
          </svg>
          {error}
        </p>
      )}
    </div>
  )
}
