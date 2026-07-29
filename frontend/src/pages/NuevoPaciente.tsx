import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../api/client'
import type { PacienteCreate } from '../types'
import PageHeader from '../components/PageHeader'
import FormField from '../components/FormField'

export default function NuevoPaciente() {
  const navigate = useNavigate()
  const [step, setStep] = useState(1)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({})
  const [form, setForm] = useState<PacienteCreate>({
    ci: '',
    nombre: '',
    apellido: '',
    fecha_nacimiento: '',
    sexo: 'M',
    telefono: '',
    direccion: '',
  })

  const update = (field: keyof PacienteCreate, value: string) => {
    setForm((prev) => ({ ...prev, [field]: value }))
    setFieldErrors((prev) => ({ ...prev, [field]: '' }))
  }

  const validarStep1 = (): boolean => {
    const errs: Record<string, string> = {}
    if (!form.ci.trim()) errs.ci = 'Ingresa el número de CI.'
    else if (!/^\d{5,10}$/.test(form.ci.trim())) errs.ci = 'Solo números, entre 5 y 10 dígitos.'
    if (!form.nombre.trim()) errs.nombre = 'Ingresa el nombre.'
    else if (form.nombre.trim().length < 2) errs.nombre = 'Mínimo 2 caracteres.'
    if (!form.apellido.trim()) errs.apellido = 'Ingresa el apellido.'
    else if (form.apellido.trim().length < 2) errs.apellido = 'Mínimo 2 caracteres.'
    if (!form.fecha_nacimiento) errs.fecha_nacimiento = 'Selecciona la fecha de nacimiento.'
    else {
      const fecha = new Date(form.fecha_nacimiento)
      const hoy = new Date()
      if (fecha > hoy) errs.fecha_nacimiento = 'La fecha no puede ser futura.'
      if (fecha < new Date('1900-01-01')) errs.fecha_nacimiento = 'Fecha inválida.'
    }
    setFieldErrors(errs)
    return Object.keys(errs).length === 0
  }

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await api.post('/pacientes', {
        ...form,
        ci: form.ci.trim(),
        nombre: form.nombre.trim(),
        apellido: form.apellido.trim(),
      })
      navigate('/pacientes')
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(detail || 'Error al registrar paciente. Verifica los datos.')
    } finally {
      setLoading(false)
    }
  }

  const inputClass = (field: string) =>
    `w-full border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 ${
      fieldErrors[field] ? 'border-red-400 bg-red-50' : 'border-gray-300'
    }`

  return (
    <div className="max-w-lg mx-auto">
      <PageHeader title="Registrar Paciente" subtitle="Completa los datos del paciente" />

      {/* Steps indicator */}
      <div className="flex gap-2 mb-6">
        <span className={`px-3 py-1 rounded-full text-xs font-medium ${step === 1 ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-600'}`}>
          1. Datos Personales
        </span>
        <span className={`px-3 py-1 rounded-full text-xs font-medium ${step === 2 ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-600'}`}>
          2. Contacto
        </span>
      </div>

      <form onSubmit={handleSubmit} className="bg-white rounded-lg shadow-sm border p-6 space-y-4" noValidate>
        {error && <div className="bg-red-50 border border-red-200 text-red-700 text-sm p-3 rounded">{error}</div>}

        {step === 1 && (
          <>
            <FormField label="Cédula de Identidad (CI)" required tooltip="Solo números, sin guiones ni espacios" error={fieldErrors.ci}>
              <input
                value={form.ci}
                onChange={(e) => update('ci', e.target.value.replace(/\D/g, ''))}
                maxLength={10}
                inputMode="numeric"
                className={inputClass('ci')}
                placeholder="Ej: 12345678"
              />
            </FormField>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <FormField label="Nombre" required error={fieldErrors.nombre}>
                <input
                  value={form.nombre}
                  onChange={(e) => update('nombre', e.target.value)}
                  maxLength={50}
                  className={inputClass('nombre')}
                  placeholder="Ej: Juan"
                />
              </FormField>
              <FormField label="Apellido" required error={fieldErrors.apellido}>
                <input
                  value={form.apellido}
                  onChange={(e) => update('apellido', e.target.value)}
                  maxLength={50}
                  className={inputClass('apellido')}
                  placeholder="Ej: Pérez"
                />
              </FormField>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <FormField label="Fecha de Nacimiento" required error={fieldErrors.fecha_nacimiento}>
                <input
                  type="date"
                  value={form.fecha_nacimiento}
                  onChange={(e) => update('fecha_nacimiento', e.target.value)}
                  max={new Date().toISOString().split('T')[0]}
                  className={inputClass('fecha_nacimiento')}
                />
              </FormField>
              <FormField label="Sexo" required>
                <select
                  value={form.sexo}
                  onChange={(e) => update('sexo', e.target.value)}
                  className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="M">Masculino</option>
                  <option value="F">Femenino</option>
                  <option value="Otro">Otro</option>
                </select>
              </FormField>
            </div>
            <button
              type="button"
              onClick={() => { if (validarStep1()) setStep(2) }}
              className="w-full bg-blue-600 text-white py-2 rounded-md font-medium hover:bg-blue-700"
            >
              Siguiente →
            </button>
          </>
        )}

        {step === 2 && (
          <>
            <FormField label="Teléfono" tooltip="Número de contacto, solo números" error={fieldErrors.telefono}>
              <input
                value={form.telefono}
                onChange={(e) => update('telefono', e.target.value.replace(/[^\d+\-\s]/g, ''))}
                maxLength={15}
                inputMode="tel"
                className={inputClass('telefono')}
                placeholder="Ej: 71234567"
              />
            </FormField>
            <FormField label="Dirección">
              <input
                value={form.direccion}
                onChange={(e) => update('direccion', e.target.value)}
                maxLength={200}
                className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="Ej: Av. Busch #123, Zona Central"
              />
            </FormField>
            <div className="flex gap-3">
              <button
                type="button"
                onClick={() => setStep(1)}
                className="flex-1 bg-gray-100 text-gray-700 py-2 rounded-md font-medium hover:bg-gray-200"
              >
                ← Atrás
              </button>
              <button
                type="submit"
                disabled={loading}
                className="flex-1 bg-blue-600 text-white py-2 rounded-md font-medium hover:bg-blue-700 disabled:opacity-50"
              >
                {loading ? 'Guardando...' : 'Registrar Paciente'}
              </button>
            </div>
          </>
        )}
      </form>
    </div>
  )
}
