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

export interface SexoCount {
  sexo: string
  cantidad: number
}

export interface EdadRangeCount {
  rango: string
  cantidad: number
}

export interface DiaCount {
  fecha: string
  cantidad: number
}

export interface ModeloCount {
  modelo: string
  consultas: number
  tokens: number
}

export interface UsuarioActividad {
  usuario_id: number
  nombre: string
  consultas: number
}

export interface MotivoFrecuente {
  palabra: string
  cantidad: number
}

export interface Estadisticas {
  total_consultas: number
  total_pacientes: number
  total_usuarios: number
  por_nivel: NivelCount[]
  promedio_tiempo_respuesta: number | null
  modelo_mas_usado: string | null
  por_sexo: SexoCount[]
  por_rango_edad: EdadRangeCount[]
  consultas_por_dia: DiaCount[]
  por_modelo: ModeloCount[]
  total_tokens: number
  actividad_usuarios: UsuarioActividad[]
  motivos_frecuentes: MotivoFrecuente[]
}

export interface EstadisticasTriaje {
  fecha_desde: string
  fecha_hasta: string
  total_consultas: number
  por_nivel: NivelCount[]
  promedio_tiempo_respuesta: number | null
  modelo_mas_usado: string | null
  por_sexo: SexoCount[]
  por_rango_edad: EdadRangeCount[]
  consultas_por_dia: DiaCount[]
  total_tokens: number
  actividad_usuarios: UsuarioActividad[]
  motivos_frecuentes: MotivoFrecuente[]
}

export interface Token {
  access_token: string
  token_type: string
}
