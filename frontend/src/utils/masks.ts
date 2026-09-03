/**
 * Utilidades de máscaras de entrada y mapeo de errores del servidor.
 *
 * Las máscaras son solo visuales: el estado del formulario siempre guarda
 * dígitos limpios, por lo que las validaciones y el envío al servidor no
 * cambian.
 */

/** Deja solo los dígitos de un valor. */
export const soloDigitos = (valor: string | undefined | null): string =>
  (valor ?? '').replace(/\D/g, '')

/**
 * Sanitiza un CI permitiendo letras y números (algunos CI bolivianos
 * llevan letras), sin espacios, guiones ni otros símbolos.
 */
export const soloCI = (valor: string | undefined | null): string =>
  (valor ?? '').replace(/[^a-zA-Z0-9]/g, '').toUpperCase()

/**
 * Máscara visual de teléfono boliviano: 4 dígitos + espacio + 4 dígitos
 * (ej: 7123 4567). El estado guarda solo dígitos.
 */
export function formatTelefono(valor: string | undefined | null): string {
  const digitos = soloDigitos(valor).slice(0, 15)
  const grupos = digitos.match(/.{1,4}/g) ?? []
  return grupos.join(' ')
}

/**
 * Convierte el `detail` de error de la API en errores por campo, usando
 * mensajes claros y comprensibles. Nunca expone texto técnico (SQL,
 * trazas, mensajes internos de Pydantic en inglés, etc.).
 *
 * Devuelve un objeto campo → mensaje. Si no se puede mapear a un campo,
 * devuelve {} y el llamador debe mostrar un mensaje genérico.
 */
const PATRONES_TECNICOS: Array<[RegExp, string]> = [
  [/shorter than|min_length/i, 'es demasiado corto.'],
  [/longer than|max_length/i, 'es demasiado largo.'],
  [/not a valid (email|integer|number|datetime|date)|value_error/i, 'no tiene un formato válido.'],
  [/unable to parse|invalid date/i, 'no es una fecha válida.'],
  [/string_type|valid string/i, 'debe ser texto.'],
  [/number_type|valid number|valid integer/i, 'debe ser un número.'],
  [/missing/i, 'es obligatorio.'],
  [/greater than|less than/i, 'está fuera del rango permitido.'],
]

function mensajeAmigable(campo: string, msg: string): string {
  for (const [patron, texto] of PATRONES_TECNICOS) {
    if (patron.test(msg)) return `El campo ${campo} ${texto}`
  }
  return `Revisa el campo ${campo}.`
}

export function mapearErrorServidor(detail: unknown): Record<string, string> {
  const errores: Record<string, string> = {}
  if (typeof detail === 'string') {
    const d = detail.toLowerCase()
    if (d.includes('cédula') || d.includes('cedula') || d.includes(' ci ')) errores.ci = detail
    else if (d.includes('email') || d.includes('correo')) errores.email = detail
    else if (d.includes('contraseña') || d.includes('password')) errores.password = detail
    else if (d.includes('apellido')) errores.apellido = detail
    else if (d.includes('nombre')) errores.nombre = detail
    else if (d.includes('fecha')) errores.fecha_nacimiento = detail
    else if (d.includes('teléfono') || d.includes('telefono')) errores.telefono = detail
  } else if (Array.isArray(detail)) {
    // Errores de validación de Pydantic (HTTP 422): traducir a español
    for (const item of detail) {
      const loc = (item as { loc?: unknown[] })?.loc
      const campo = Array.isArray(loc) ? loc[loc.length - 1] : undefined
      const msg = (item as { msg?: string })?.msg ?? ''
      if (typeof campo === 'string' && campo !== 'body') {
        errores[campo] = mensajeAmigable(campo, msg)
      }
    }
  }
  // Cualquier otro formato (dict, null, etc.) devuelve {} → mensaje genérico.
  return errores
}