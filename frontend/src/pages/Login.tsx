import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import api from '../api/client'
import FormField from '../components/FormField'

export default function Login() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [mode, setMode] = useState<'login' | 'registro'>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [nombre, setNombre] = useState('')
  const [ci, setCi] = useState('')
  const [rol, setRol] = useState('enfermero_triage')
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [loading, setLoading] = useState(false)
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({})

  const validarLogin = (): boolean => {
    const errs: Record<string, string> = {}
    if (!email.trim()) errs.email = 'Ingresa tu correo electrónico.'
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) errs.email = 'Formato inválido. Ejemplo: usuario@salud.gob.bo'
    if (!password) errs.password = 'Ingresa tu contraseña.'
    setFieldErrors(errs)
    return Object.keys(errs).length === 0
  }

  const validarRegistro = (): boolean => {
    const errs: Record<string, string> = {}
    if (!nombre.trim()) errs.nombre = 'Ingresa tu nombre completo.'
    else if (nombre.trim().length < 3) errs.nombre = 'Mínimo 3 caracteres.'
    if (!ci.trim()) errs.ci = 'Ingresa tu número de CI.'
    else if (!/^\d{5,10}$/.test(ci.trim())) errs.ci = 'Solo números, entre 5 y 10 dígitos.'
    if (!email.trim()) errs.email = 'Ingresa tu correo electrónico.'
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) errs.email = 'Formato inválido. Ejemplo: usuario@salud.gob.bo'
    if (!password) errs.password = 'Ingresa una contraseña.'
    else if (password.length < 6) errs.password = 'Mínimo 6 caracteres.'
    setFieldErrors(errs)
    return Object.keys(errs).length === 0
  }

  const handleLogin = async (e: FormEvent) => {
    e.preventDefault()
    setError('')
    if (!validarLogin()) return
    setLoading(true)
    try {
      await login(email, password)
      navigate('/')
    } catch {
      setError('Credenciales inválidas. Verifica tu email y contraseña.')
    } finally {
      setLoading(false)
    }
  }

  const handleRegistro = async (e: FormEvent) => {
    e.preventDefault()
    setError('')
    setSuccess('')
    if (!validarRegistro()) return
    setLoading(true)
    try {
      await api.post('/auth/registro', {
        ci: ci.trim(),
        nombre_completo: nombre.trim(),
        email: email.trim(),
        password,
        rol,
      })
      setSuccess('Usuario creado exitosamente. Ahora inicia sesión.')
      setMode('login')
      setPassword('')
      setFieldErrors({})
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(msg || 'Error al registrar. Intenta de nuevo.')
    } finally {
      setLoading(false)
    }
  }

  const inputClass = (field: string) =>
    `w-full border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 ${
      fieldErrors[field] ? 'border-red-400 bg-red-50' : 'border-gray-300'
    }`

  return (
    <div className="min-h-screen bg-gray-100 flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <h1 className="text-2xl font-bold text-gray-800">🏥 Sistema de Triaje IA</h1>
          <p className="text-sm text-gray-500 mt-1">NNAC Bolivia - Apoyo a la decisión clínica</p>
        </div>

        {mode === 'login' ? (
          <form onSubmit={handleLogin} className="bg-white rounded-lg shadow p-6 space-y-4" noValidate>
            {error && <div className="bg-red-50 border border-red-200 text-red-700 text-sm p-3 rounded">{error}</div>}
            {success && <div className="bg-green-50 border border-green-200 text-green-700 text-sm p-3 rounded">{success}</div>}

            <FormField label="Email" required error={fieldErrors.email}>
              <input
                type="email"
                value={email}
                onChange={(e) => { setEmail(e.target.value); setFieldErrors(p => ({...p, email: ''})) }}
                maxLength={100}
                className={inputClass('email')}
                placeholder="usuario@salud.gob.bo"
              />
            </FormField>

            <FormField label="Contraseña" required error={fieldErrors.password}>
              <input
                type="password"
                value={password}
                onChange={(e) => { setPassword(e.target.value); setFieldErrors(p => ({...p, password: ''})) }}
                maxLength={50}
                className={inputClass('password')}
                placeholder="••••••••"
              />
            </FormField>

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-blue-600 text-white py-2 rounded-md font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors"
            >
              {loading ? 'Ingresando...' : 'Ingresar'}
            </button>

            <p className="text-center text-sm text-gray-500">
              ¿No tienes cuenta?{' '}
              <button type="button" onClick={() => { setMode('registro'); setError(''); setSuccess(''); setFieldErrors({}) }} className="text-blue-600 font-medium hover:underline">
                Regístrate
              </button>
            </p>
          </form>
        ) : (
          <form onSubmit={handleRegistro} className="bg-white rounded-lg shadow p-6 space-y-4" noValidate>
            {error && <div className="bg-red-50 border border-red-200 text-red-700 text-sm p-3 rounded">{error}</div>}

            <FormField label="Nombre completo" required error={fieldErrors.nombre}>
              <input
                value={nombre}
                onChange={(e) => { setNombre(e.target.value); setFieldErrors(p => ({...p, nombre: ''})) }}
                maxLength={100}
                className={inputClass('nombre')}
                placeholder="Dra. María Pérez"
              />
            </FormField>

            <FormField label="CI" required tooltip="Cédula de Identidad, solo números" error={fieldErrors.ci}>
              <input
                value={ci}
                onChange={(e) => { setCi(e.target.value.replace(/\D/g, '')); setFieldErrors(p => ({...p, ci: ''})) }}
                maxLength={10}
                inputMode="numeric"
                className={inputClass('ci')}
                placeholder="12345678"
              />
            </FormField>

            <FormField label="Email" required error={fieldErrors.email}>
              <input
                type="email"
                value={email}
                onChange={(e) => { setEmail(e.target.value); setFieldErrors(p => ({...p, email: ''})) }}
                maxLength={100}
                className={inputClass('email')}
                placeholder="usuario@salud.gob.bo"
              />
            </FormField>

            <FormField label="Contraseña" required tooltip="Mínimo 6 caracteres" error={fieldErrors.password}>
              <input
                type="password"
                value={password}
                onChange={(e) => { setPassword(e.target.value); setFieldErrors(p => ({...p, password: ''})) }}
                maxLength={50}
                className={inputClass('password')}
                placeholder="Mínimo 6 caracteres"
              />
            </FormField>

            <FormField label="Rol" required tooltip="Determina los permisos de acceso al sistema">
              <select
                value={rol}
                onChange={(e) => setRol(e.target.value)}
                className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="enfermero_triage">Enfermero/a de Triaje</option>
                <option value="medico">Médico/a</option>
                <option value="admin">Administrador</option>
              </select>
            </FormField>

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-blue-600 text-white py-2 rounded-md font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors"
            >
              {loading ? 'Creando cuenta...' : 'Crear Cuenta'}
            </button>

            <p className="text-center text-sm text-gray-500">
              ¿Ya tienes cuenta?{' '}
              <button type="button" onClick={() => { setMode('login'); setError(''); setFieldErrors({}) }} className="text-blue-600 font-medium hover:underline">
                Inicia sesión
              </button>
            </p>
          </form>
        )}
      </div>
    </div>
  )
}
