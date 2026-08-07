export interface Usuario {
  id: number
  ci: string
  nombre_completo: string
  email: string
  rol: 'admin' | 'medico' | 'enfermero_triage'
  centro_salud: string | null
  activo: boolean
}

export interface Paciente {
  id: number
  ci: string
  nombre: string
  apellido: string
  fecha_nacimiento: string
  sexo: 'M' | 'F' | 'Otro'
  telefono: string | null
  direccion: string | null
  edad: number
  fecha_registro: string
  fecha_actualizacion: string | null
}

export interface PacienteCreate {
  ci: string
  nombre: string
  apellido: string
  fecha_nacimiento: string
  sexo: 'M' | 'F' | 'Otro'
  telefono?: string
  direccion?: string
}

export interface TriageCreate {
  paciente_id: number
  temperatura?: number
  presion_sistolica?: number
  presion_diastolica?: number
  frecuencia_cardiaca?: number
  frecuencia_respiratoria?: number
  spo2?: number
  motivo_consulta?: string
  sintomas?: string
  modelo?: string
}

export interface ConsultaTriage {
  id: number
  paciente_id: number
  usuario_id: number | null
  fecha_hora: string
  temperatura: number | null
  presion_sistolica: number | null
  presion_diastolica: number | null
  frecuencia_cardiaca: number | null
  frecuencia_respiratoria: number | null
  spo2: number | null
  motivo_consulta: string | null
  sintomas: string | null
  nivel_urgencia: NivelUrgencia | null
  respuesta_llm: string | null
  prompt_utilizado: string | null
  modelo_utilizado: string | null
  tiempo_respuesta: number | null
  tokens_consumidos: number | null
}

export type NivelUrgencia = 'rojo' | 'naranja' | 'amarillo' | 'verde' | 'azul'

export interface NivelCount {
  nivel: string
  cantidad: number
}

export interface Estadisticas {
  total_consultas: number
  total_pacientes: number
  total_usuarios: number
  por_nivel: NivelCount[]
  promedio_tiempo_respuesta: number | null
  modelo_mas_usado: string | null
}

export interface Token {
  access_token: string
  token_type: string
}
