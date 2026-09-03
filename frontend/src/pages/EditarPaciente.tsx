import { useState, useEffect, type FormEvent } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import api from '../api/client'
import type { Paciente } from '../types'
import Mensaje from '../components/Mensaje'
import PageHeader from '../components/PageHeader'
import FormField from '../components/FormField'
import { formatTelefono, soloCI, soloDigitos, mapearErrorServidor } from '../utils/masks'

export default function EditarPaciente() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [form, setForm] = useState({
    ci: '', nombre: '', apellido: '', fecha_nacimiento: '', sexo: 'M', telefono: '', direccion: '',
  })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({})

  useEffect(() => {
    api.get(`/pacientes/${id}`).then((res) => {
      const p: Paciente = res.data
      setForm({
        ci: p.ci, nombre: p.nombre, apellido: p.apellido,
        fecha_nacimiento: p.fecha_nacimiento, sexo: p.sexo,
        telefono: p.telefono || '', direccion: p.direccion || '',
      })
    })
  }, [id])

  const update = (field: string, value: string) => {
    setForm((prev) => ({ ...prev, [field]: value }))
    setFieldErrors((prev) => ({ ...prev, [field]: '' }))
  }

  const validar = (): boolean => {
    const errs: Record<string, string> = {}
    if (!form.ci.trim()) errs.ci = 'Ingresa el número de CI.'
    else if (!/^[A-Za-z0-9]{5,20}$/.test(form.ci.trim())) errs.ci = 'Solo letras y números, entre 5 y 20 caracteres.'
    if (!form.nombre.trim()) errs.nombre = 'Ingresa el nombre.'
    else if (form.nombre.trim().length < 2) errs.nombre = 'Mínimo 2 caracteres.'
    if (!form.apellido.trim()) errs.apellido = 'Ingresa el apellido.'
    else if (form.apellido.trim().length < 2) errs.apellido = 'Mínimo 2 caracteres.'
    if (!form.fecha_nacimiento) errs.fecha_nacimiento = 'Selecciona la fecha de nacimiento.'
    else if (new Date(form.fecha_nacimiento) > new Date()) errs.fecha_nacimiento = 'La fecha no puede ser futura.'
    setFieldErrors(errs)
    return Object.keys(errs).length === 0
  }

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError('')
    if (!validar()) return
    setLoading(true)
    try {
      await api.put(`/pacientes/${id}`, {
        ...form,
        ci: form.ci.trim(),
        nombre: form.nombre.trim(),
        apellido: form.apellido.trim(),
      })
      navigate(`/pacientes/${id}`)
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      const erroresServidor = mapearErrorServidor(detail)
      if (Object.keys(erroresServidor).length > 0) {
        // Mostrar el error del servidor junto al campo correspondiente
        setFieldErrors((prev) => ({ ...prev, ...erroresServidor }))
      } else {
        setError(detail || 'Error al actualizar. Verifica los datos.')
      }
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
      <PageHeader title="Editar Paciente" subtitle="Modifica los datos del paciente" />
      <form onSubmit={handleSubmit} className="bg-white rounded-lg shadow-sm border p-6 space-y-4" noValidate>
        {error && <Mensaje variante="error" onCerrar={() => setError('')}>{error}</Mensaje>}

        <FormField label="CI" required tooltip="Números y letras, sin guiones ni espacios" error={fieldErrors.ci}>
          <input value={form.ci} onChange={(e) => update('ci', soloCI(e.target.value))} maxLength={20}
            className={inputClass('ci')} placeholder="Ej: 12345678 o 1234ABC" />
        </FormField>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <FormField label="Nombre" required error={fieldErrors.nombre}>
            <input value={form.nombre} onChange={(e) => update('nombre', e.target.value)} maxLength={50}
              className={inputClass('nombre')} placeholder="Ej: Juan" />
          </FormField>
          <FormField label="Apellido" required error={fieldErrors.apellido}>
            <input value={form.apellido} onChange={(e) => update('apellido', e.target.value)} maxLength={50}
              className={inputClass('apellido')} placeholder="Ej: Pérez" />
          </FormField>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <FormField label="Fecha de Nacimiento" required error={fieldErrors.fecha_nacimiento}>
            <input type="date" value={form.fecha_nacimiento} onChange={(e) => update('fecha_nacimiento', e.target.value)}
              max={new Date().toISOString().split('T')[0]}
              className={inputClass('fecha_nacimiento')} />
          </FormField>
          <FormField label="Sexo" required>
            <select value={form.sexo} onChange={(e) => update('sexo', e.target.value)}
              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
              <option value="M">Masculino</option>
              <option value="F">Femenino</option>
              <option value="Otro">Otro</option>
            </select>
          </FormField>
        </div>
        <FormField label="Teléfono" tooltip="Número de contacto, solo números" error={fieldErrors.telefono}>
          <input value={formatTelefono(form.telefono)} onChange={(e) => update('telefono', soloDigitos(e.target.value).slice(0, 15))} maxLength={19} inputMode="tel"
            className={inputClass('telefono')} placeholder="Ej: 7123 4567" />
        </FormField>
        <FormField label="Dirección">
          <input value={form.direccion} onChange={(e) => update('direccion', e.target.value)} maxLength={200}
            className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" placeholder="Ej: Av. Busch #123" />
        </FormField>
        <div className="flex gap-3">
          <button type="button" onClick={() => navigate(-1)}
            className="flex-1 bg-gray-100 text-gray-700 py-2 rounded-md font-medium hover:bg-gray-200">
            Cancelar
          </button>
          <button type="submit" disabled={loading}
            className="flex-1 bg-blue-600 text-white py-2 rounded-md font-medium hover:bg-blue-700 disabled:opacity-50">
            {loading ? 'Guardando...' : 'Guardar Cambios'}
          </button>
        </div>
      </form>
    </div>
  )
}
