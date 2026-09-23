/**
 * Rangos de referencia de signos vitales para MOSTRAR en la UI.
 *
 * Espejo de sólo lectura de `ai_service/rangos_pediatricos.py`, que es la
 * fuente de verdad con la que el motor de reglas deterministas (red flags)
 * evalúa al paciente. Aquí sólo se usa para que el personal vea la referencia
 * correcta según la edad: mostrar "Normal: 60 - 100 bpm" a un lactante induce
 * a error.
 *
 * IMPORTANTE: si se cambian los umbrales del backend, actualizar esta tabla.
 */

export type GrupoEtario =
  | 'neonato'
  | 'lactante'
  | 'preescolar'
  | 'escolar'
  | 'adolescente'
  | 'adulto'
  | 'adulto_mayor'

/** Grupo etario clínico del paciente (misma lógica que el backend). */
export const grupoEtario = (edad: number, edadMeses?: number | null): GrupoEtario => {
  const anios = edad ?? 0
  const meses = anios > 0 ? anios * 12 : (edadMeses ?? 0)
  if (meses < 1) return 'neonato'
  if (meses < 12) return 'lactante'
  const a = anios > 0 ? anios : Math.floor(meses / 12)
  if (a <= 5) return 'preescolar'
  if (a <= 11) return 'escolar'
  if (a <= 17) return 'adolescente'
  if (a <= 64) return 'adulto'
  return 'adulto_mayor'
}

const ETIQUETAS: Record<GrupoEtario, string> = {
  neonato: 'Neonato (< 1 mes)',
  lactante: 'Lactante (1-11 meses)',
  preescolar: 'Preescolar (1-5 años)',
  escolar: 'Escolar (6-11 años)',
  adolescente: 'Adolescente (12-17 años)',
  adulto: 'Adulto (18-64 años)',
  adulto_mayor: 'Adulto mayor (≥ 65 años)',
}

/** Etiqueta legible del grupo etario. */
export const etiquetaGrupoEtario = (grupo: GrupoEtario): string => ETIQUETAS[grupo]

/** Rango respiratorio de referencia (rpm) por grupo etario. */
const FR: Record<GrupoEtario, string> = {
  neonato: '30 - 60 rpm',
  lactante: '25 - 50 rpm',
  preescolar: '20 - 30 rpm',
  escolar: '18 - 25 rpm',
  adolescente: '12 - 20 rpm',
  adulto: '12 - 20 rpm',
  adulto_mayor: '12 - 20 rpm',
}

/** Rango cardíaco de referencia (bpm) por grupo etario (en vigilia). */
const FC: Record<GrupoEtario, string> = {
  neonato: '100 - 180 bpm',
  lactante: '90 - 160 bpm',
  preescolar: '80 - 140 bpm',
  escolar: '70 - 120 bpm',
  adolescente: '60 - 100 bpm',
  adulto: '60 - 100 bpm',
  adulto_mayor: '60 - 100 bpm',
}

/** Presión sistólica de referencia (mmHg) por grupo etario. */
const PAS: Record<GrupoEtario, string> = {
  neonato: '60 - 90 mmHg',
  lactante: '80 - 100 mmHg',
  preescolar: '85 - 110 mmHg',
  escolar: '90 - 120 mmHg',
  adolescente: '95 - 120 mmHg',
  adulto: '90 - 140 mmHg',
  adulto_mayor: '90 - 140 mmHg',
}

export type VitalReferenciable = 'temperatura' | 'presion_sistolica' | 'presion_diastolica' | 'frecuencia_cardiaca' | 'frecuencia_respiratoria' | 'spo2'

/** Tooltip con la referencia del grupo etario del paciente. */
export const referenciaVital = (vital: VitalReferenciable, grupo: GrupoEtario): string => {
  const grupoTexto = etiquetaGrupoEtario(grupo)
  switch (vital) {
    case 'temperatura':
      return `Referencia para ${grupoTexto}: 36.1 - 37.2 °C`
    case 'presion_sistolica':
      return `Referencia para ${grupoTexto}: ${PAS[grupo]}`
    case 'presion_diastolica':
      return `Referencia para ${grupoTexto}: 40 - 90 mmHg (siempre menor que la sistólica)`
    case 'frecuencia_cardiaca':
      return `Referencia para ${grupoTexto}: ${FC[grupo]}. En lactantes y niños pequeños la FC es naturalmente más alta: no es taquicardia.`
    case 'frecuencia_respiratoria':
      return `Referencia para ${grupoTexto}: ${FR[grupo]}. En lactantes y niños pequeños la FR es naturalmente más alta: no es taquipnea.`
    case 'spo2':
      return `Referencia para ${grupoTexto}: 95 - 100%`
  }
}
