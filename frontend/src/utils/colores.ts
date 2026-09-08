/**
 * Paleta Manchester del sistema — ÚNICA fuente de verdad.
 *
 * Convención de colores (significado consistente en todo el sistema):
 * - Azul 600/700: acción primaria | Rojo: peligro/error/eliminar
 * - Verde: éxito/activo | Amarillo: advertencia | Gris: neutro
 * - Niveles Manchester: siempre color + emoji + texto (nunca solo color).
 */

/** Clases Tailwind para badges de nivel de urgencia. */
export const COLOR_MANCHESTER_CLASES: Record<string, string> = {
  rojo: 'bg-red-100 text-red-800',
  naranja: 'bg-orange-100 text-orange-800',
  amarillo: 'bg-yellow-100 text-yellow-800',
  verde: 'bg-green-100 text-green-800',
  azul: 'bg-blue-100 text-blue-800',
}

/** Colores hex para gráficos (recharts). */
export const COLOR_MANCHESTER_HEX: Record<string, string> = {
  rojo: '#EF4444',
  naranja: '#F97316',
  amarillo: '#EAB308',
  verde: '#22C55E',
  azul: '#3B82F6',
  sin_clasificar: '#9CA3AF',
}

/** Clases de badge para un nivel (fallback gris neutro). */
export const claseNivel = (nivel: string | null | undefined): string =>
  (nivel && COLOR_MANCHESTER_CLASES[nivel]) || 'bg-gray-100 text-gray-700'

/** Color hex para un nivel en gráficos (fallback gris). */
export const hexNivel = (nivel: string | null | undefined): string =>
  (nivel && COLOR_MANCHESTER_HEX[nivel]) || COLOR_MANCHESTER_HEX.sin_clasificar