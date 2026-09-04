/**
 * Utilidades de formato compartidas para fechas y números.
 * Garantizan un único formato en todas las pantallas (configuración regional es-BO).
 */

/** Formato único de fecha y hora: dd/mm/aaaa, hh:mm */
export const formatoFechaHora = (fecha: string | Date): string =>
  new Date(fecha).toLocaleString('es-BO')

/** Formato único de fecha: dd/mm/aaaa */
export const formatoFecha = (fecha: string | Date): string =>
  new Date(fecha).toLocaleDateString('es-BO')

/** Números con separador de miles es-BO; null/undefined → "—" */
export const formatoNumero = (valor: number | null | undefined): string =>
  valor == null ? '—' : valor.toLocaleString('es-BO')