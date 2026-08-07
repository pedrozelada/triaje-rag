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
  const [mostrarPassword, setMostrarPassword] = useState(false)

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

  const passwordInput = (placeholder: string) => (
    <div className="relative">
      <input
        type={mostrarPassword ? 'text' : 'password'}
        value={password}
        onChange={(e) => { setPassword(e.target.value); setFieldErrors(p => ({...p, password: ''})) }}
        maxLength={50}
        className={`${inputClass('password')} pr-10`}
        placeholder={placeholder}
      />
      <button
        type="button"
        onClick={() => setMostrarPassword(v => !v)}
        aria-label={mostrarPassword ? 'Ocultar contraseña' : 'Mostrar contraseña'}
        className="absolute inset-y-0 right-0 flex items-center px-3 text-gray-400 hover:text-gray-600"
        tabIndex={-1}
      >
        {mostrarPassword ? (
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-5 h-5">
            <path strokeLinecap="round" strokeLinejoin="round" d="M3.98 8.223A10.477 10.477 0 0 0 1.934 12C3.226 16.338 7.244 19.5 12 19.5c.993 0 1.953-.138 2.863-.395M6.228 6.228A10.451 10.451 0 0 1 12 4.5c4.756 0 8.773 3.162 10.065 7.498a10.522 10.522 0 0 1-4.293 5.774M6.228 6.228 3 3m3.228 3.228 3.65 3.65m7.894 7.894L21 21m-3.228-3.228-3.65-3.65m0 0a3 3 0 1 0-4.243-4.243m4.242 4.242L9.88 9.88" />
          </svg>
        ) : (
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-5 h-5">
            <path strokeLinecap="round" strokeLinejoin="round" d="M2.036 12.322a1.012 1.012 0 0 1 0-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178Z" />
            <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z" />
          </svg>
        )}
      </button>
    </div>
  )

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
              {passwordInput('••••••••')}
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
              <button type="button" onClick={() => { setMode('registro'); setError(''); setSuccess(''); setFieldErrors({}); setMostrarPassword(false) }} className="text-blue-600 font-medium hover:underline">
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
              {passwordInput('Mínimo 6 caracteres')}
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
              <button type="button" onClick={() => { setMode('login'); setError(''); setFieldErrors({}); setMostrarPassword(false) }} className="text-blue-600 font-medium hover:underline">
                Inicia sesión
              </button>
            </p>
          </form>
        )}
      </div>
    </div>
  )
}
