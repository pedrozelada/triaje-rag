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

/**
 * Edad legible del paciente.
 *
 * Los menores de 1 año se muestran en MESES: "0 años" no es información
 * clínicamente usable y oculta que los rangos de referencia de signos vitales
 * dependen de la edad real (un neonato no tiene los mismos que un adulto).
 */
export const formatoEdad = (edad: number, edadMeses?: number | null): string => {
  const anios = edad ?? 0
  if (anios > 0) return anios === 1 ? '1 año' : `${anios} años`
  const meses = edadMeses ?? 0
  return meses === 1 ? '1 mes' : `${meses} meses`
}