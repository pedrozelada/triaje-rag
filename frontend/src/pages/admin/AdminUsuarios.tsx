import { useState, useEffect } from 'react'
import api from '../../api/client'
import type { Usuario } from '../../types'
import PageHeader from '../../components/PageHeader'
import FormField from '../../components/FormField'
import { useAuth } from '../../context/AuthContext'

const ROLES: Usuario['rol'][] = ['admin', 'medico', 'enfermero_triage']

interface FormUsuario {
  ci: string
  nombre_completo: string
  email: string
  password: string
  rol: Usuario['rol']
  centro_salud: string
}

const FORM_VACIO: FormUsuario = {
  ci: '',
  nombre_completo: '',
  email: '',
  password: '',
  rol: 'enfermero_triage',
  centro_salud: '',
}

type Confirmacion =
  | { tipo: 'desactivar'; usuario: Usuario }
  | { tipo: 'eliminar'; usuario: Usuario }
  | { tipo: 'guardar_edicion' }

const mensajeError = (e: unknown) =>
  (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
  'Error inesperado. Intenta nuevamente.'

export default function AdminUsuarios() {
  const { usuario: usuarioActual } = useAuth()
  const [usuarios, setUsuarios] = useState<Usuario[]>([])
  const [loading, setLoading] = useState(true)

  // Modal crear/editar
  const [modalAbierto, setModalAbierto] = useState(false)
  const [editando, setEditando] = useState<Usuario | null>(null)
  const [form, setForm] = useState<FormUsuario>(FORM_VACIO)
  const [errores, setErrores] = useState<Partial<Record<keyof FormUsuario, string>>>({})
  const [errorGeneral, setErrorGeneral] = useState('')
  const [guardando, setGuardando] = useState(false)

  // Confirmaciones
  const [confirmacion, setConfirmacion] = useState<Confirmacion | null>(null)
  const [ejecutando, setEjecutando] = useState(false)

  const cargarUsuarios = () => {
    api.get('/admin/usuarios')
      .then((res) => setUsuarios(res.data))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    cargarUsuarios()
  }, [])

  const abrirNuevo = () => {
    setEditando(null)
    setForm(FORM_VACIO)
    setErrores({})
    setErrorGeneral('')
    setModalAbierto(true)
  }

  const abrirEdicion = (u: Usuario) => {
    setEditando(u)
    setForm({
      ci: u.ci,
      nombre_completo: u.nombre_completo,
      email: u.email,
      password: '',
      rol: u.rol,
      centro_salud: u.centro_salud ?? '',
    })
    setErrores({})
    setErrorGeneral('')
    setModalAbierto(true)
  }

  const cerrarModal = () => {
    setModalAbierto(false)
    setEditando(null)
  }

  const validar = (): boolean => {
    const nuevos: Partial<Record<keyof FormUsuario, string>> = {}
    if (!form.ci.trim()) nuevos.ci = 'El CI es obligatorio.'
    else if (!/^\d+$/.test(form.ci)) nuevos.ci = 'El CI debe contener solo números.'
    if (!form.nombre_completo.trim()) nuevos.nombre_completo = 'El nombre es obligatorio.'
    if (!form.email.trim()) nuevos.email = 'El email es obligatorio.'
    else if (!/^\S+@\S+\.\S+$/.test(form.email)) nuevos.email = 'Formato de email inválido (ej: nombre@correo.com).'
    if (!editando && !form.password) nuevos.password = 'La contraseña es obligatoria.'
    if (form.password && form.password.length < 6) nuevos.password = 'Mínimo 6 caracteres.'
    if (!ROLES.includes(form.rol)) nuevos.rol = 'Selecciona un rol válido.'
    setErrores(nuevos)
    return Object.keys(nuevos).length === 0
  }

  const enviarFormulario = () => {
    setErrorGeneral('')
    if (!validar()) return
    if (editando) {
      // Edición: pide confirmación antes de guardar
      setConfirmacion({ tipo: 'guardar_edicion' })
    } else {
      void guardar()
    }
  }

  const guardar = async () => {
    setGuardando(true)
    setErrorGeneral('')
    try {
      if (editando) {
        const payload: Record<string, string> = {
          nombre_completo: form.nombre_completo,
          email: form.email,
          rol: form.rol,
          centro_salud: form.centro_salud,
        }
        if (form.password) payload.password = form.password
        await api.put(`/admin/usuarios/${editando.id}`, payload)
      } else {
        await api.post('/admin/usuarios', form)
      }
      cerrarModal()
      cargarUsuarios()
    } catch (e) {
      // Conserva los datos ingresados y muestra el error del servidor
      setErrorGeneral(mensajeError(e))
    } finally {
      setGuardando(false)
    }
  }

  const cambiarRol = async (u: Usuario, rol: string) => {
    try {
      await api.put(`/admin/usuarios/${u.id}`, { rol })
      setUsuarios((prev) =>
        prev.map((item) => (item.id === u.id ? { ...item, rol: rol as Usuario['rol'] } : item))
      )
    } catch (e) {
      setErrorGeneral(mensajeError(e))
    }
  }

  const toggleActivo = async (u: Usuario) => {
    try {
      await api.put(`/admin/usuarios/${u.id}`, { activo: !u.activo })
      setUsuarios((prev) =>
        prev.map((item) => (item.id === u.id ? { ...item, activo: !item.activo } : item))
      )
    } catch (e) {
      setErrorGeneral(mensajeError(e))
    }
  }

  const eliminar = async (u: Usuario) => {
    try {
      await api.delete(`/admin/usuarios/${u.id}`)
      setUsuarios((prev) => prev.filter((item) => item.id !== u.id))
    } catch (e) {
      setErrorGeneral(mensajeError(e))
    }
  }

  // Ejecuta la acción confirmada en el modal de advertencia
  const ejecutarConfirmacion = async () => {
    if (!confirmacion) return
    setEjecutando(true)
    try {
      if (confirmacion.tipo === 'desactivar') await toggleActivo(confirmacion.usuario)
      else if (confirmacion.tipo === 'eliminar') await eliminar(confirmacion.usuario)
      else if (confirmacion.tipo === 'guardar_edicion') await guardar()
    } finally {
      setEjecutando(false)
      setConfirmacion(null)
    }
  }

  const inputClass = (conError?: string) =>
    `w-full border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 ${
      conError ? 'border-red-400 bg-red-50' : 'border-gray-300'
    }`

  return (
    <div className="space-y-4">
      <PageHeader
        title="Gestión de Usuarios"
        subtitle={`${usuarios.length} usuario(s) registrado(s)`}
        actions={
          <button
            onClick={abrirNuevo}
            className="text-sm bg-blue-600 text-white px-4 py-2 rounded-md font-medium hover:bg-blue-700"
          >
            + Nuevo Usuario
          </button>
        }
      />

      {errorGeneral && !modalAbierto && (
        <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-md px-4 py-3 flex justify-between items-center">
          <span>{errorGeneral}</span>
          <button onClick={() => setErrorGeneral('')} className="text-red-400 hover:text-red-600">✕</button>
        </div>
      )}

      {loading ? (
        <p className="text-gray-500 text-center py-8">Cargando...</p>
      ) : (
        <div className="bg-white rounded-lg shadow-sm border overflow-x-auto">
          <table className="w-full text-sm min-w-[700px]">
            <thead className="bg-gray-50 border-b">
              <tr>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Nombre</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Email</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Centro de Salud</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Rol</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Estado</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Acciones</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {usuarios.map((u) => {
                const esYo = usuarioActual?.id === u.id
                return (
                  <tr key={u.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 font-medium">
                      {u.nombre_completo}
                      {esYo && <span className="ml-2 text-xs text-blue-600">(tú)</span>}
                    </td>
                    <td className="px-4 py-3 text-gray-600">{u.email}</td>
                    <td className="px-4 py-3 text-gray-600">{u.centro_salud || '—'}</td>
                    <td className="px-4 py-3">
                      <select
                        value={u.rol}
                        onChange={(e) => cambiarRol(u, e.target.value)}
                        className="border border-gray-300 rounded px-2 py-1 text-xs"
                      >
                        {ROLES.map((r) => (
                          <option key={r} value={r}>{r}</option>
                        ))}
                      </select>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`text-xs font-medium px-2 py-1 rounded-full ${u.activo ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
                        {u.activo ? 'Activo' : 'Inactivo'}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex flex-wrap gap-2">
                        <button
                          onClick={() => abrirEdicion(u)}
                          className="text-xs font-medium px-3 py-1 rounded bg-blue-50 text-blue-700 hover:bg-blue-100"
                        >
                          Editar
                        </button>
                        <button
                          onClick={() => (u.activo ? setConfirmacion({ tipo: 'desactivar', usuario: u }) : toggleActivo(u))}
                          className={`text-xs font-medium px-3 py-1 rounded ${u.activo ? 'bg-yellow-50 text-yellow-700 hover:bg-yellow-100' : 'bg-green-50 text-green-700 hover:bg-green-100'}`}
                        >
                          {u.activo ? 'Desactivar' : 'Activar'}
                        </button>
                        <button
                          onClick={() => setConfirmacion({ tipo: 'eliminar', usuario: u })}
                          disabled={esYo}
                          title={esYo ? 'No puedes eliminar tu propio usuario' : undefined}
                          className="text-xs font-medium px-3 py-1 rounded bg-red-50 text-red-700 hover:bg-red-100 disabled:opacity-40 disabled:cursor-not-allowed"
                        >
                          Eliminar
                        </button>
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Modal crear/editar usuario */}
      {modalAbierto && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl w-full max-w-lg max-h-[90vh] overflow-y-auto p-6 space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold text-gray-800">
                {editando ? `Editar Usuario: ${editando.nombre_completo}` : 'Nuevo Usuario'}
              </h2>
              <button onClick={cerrarModal} className="text-gray-400 hover:text-gray-600">✕</button>
            </div>

            {errorGeneral && (
              <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-md px-4 py-2">
                {errorGeneral}
              </div>
            )}

            <FormField label="CI" required tooltip="Carnet de identidad, solo números" error={errores.ci}>
              <input
                type="text"
                inputMode="numeric"
                value={form.ci}
                onChange={(e) => setForm({ ...form, ci: e.target.value.replace(/\D/g, '').slice(0, 30) })}
                placeholder="Ej: 1234567"
                maxLength={30}
                className={inputClass(errores.ci)}
              />
            </FormField>

            <FormField label="Nombre completo" required error={errores.nombre_completo}>
              <input
                type="text"
                value={form.nombre_completo}
                onChange={(e) => setForm({ ...form, nombre_completo: e.target.value })}
                placeholder="Ej: María Pérez Flores"
                maxLength={150}
                className={inputClass(errores.nombre_completo)}
              />
            </FormField>

            <FormField label="Email" required error={errores.email}>
              <input
                type="email"
                value={form.email}
                onChange={(e) => setForm({ ...form, email: e.target.value })}
                placeholder="Ej: maria@postasalud.bo"
                maxLength={120}
                className={inputClass(errores.email)}
              />
            </FormField>

            <FormField
              label="Contraseña"
              required={!editando}
              tooltip={editando ? 'Deja vacío para conservar la contraseña actual' : 'Mínimo 6 caracteres'}
              error={errores.password}
            >
              <input
                type="password"
                value={form.password}
                onChange={(e) => setForm({ ...form, password: e.target.value })}
                placeholder={editando ? '•••••••• (sin cambios)' : 'Mínimo 6 caracteres'}
                maxLength={64}
                className={inputClass(errores.password)}
              />
            </FormField>

            <FormField label="Rol" required tooltip="admin: todo el sistema · medico/enfermero_triage: flujo clínico" error={errores.rol}>
              <select
                value={form.rol}
                onChange={(e) => setForm({ ...form, rol: e.target.value as Usuario['rol'] })}
                className={inputClass(errores.rol)}
              >
                {ROLES.map((r) => (
                  <option key={r} value={r}>{r}</option>
                ))}
              </select>
            </FormField>

            <FormField label="Centro de Salud" tooltip="Opcional: posta o centro donde trabaja">
              <input
                type="text"
                value={form.centro_salud}
                onChange={(e) => setForm({ ...form, centro_salud: e.target.value })}
                placeholder="Ej: Posta Rural San Antonio"
                maxLength={100}
                className={inputClass()}
              />
            </FormField>

            <div className="flex justify-end gap-2 pt-2">
              <button
                onClick={cerrarModal}
                className="text-sm px-4 py-2 rounded-md bg-gray-100 hover:bg-gray-200"
              >
                Cancelar
              </button>
              <button
                onClick={enviarFormulario}
                disabled={guardando}
                className="text-sm px-4 py-2 rounded-md bg-blue-600 text-white font-medium hover:bg-blue-700 disabled:opacity-50"
              >
                {guardando ? 'Guardando...' : editando ? 'Guardar Cambios' : 'Crear Usuario'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal de confirmación (desactivar / eliminar / guardar edición) */}
      {confirmacion && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl w-full max-w-md p-6 space-y-4">
            {confirmacion.tipo === 'desactivar' && (
              <>
                <h3 className="text-lg font-semibold text-yellow-700 flex items-center gap-2">
                  ⚠️ Desactivar Usuario
                </h3>
                <p className="text-sm text-gray-600">
                  El usuario <strong>{confirmacion.usuario.nombre_completo}</strong> quedará{' '}
                  <strong>inactivo</strong> y no podrá iniciar sesión en el sistema.
                  ¿Deseas continuar?
                </p>
              </>
            )}
            {confirmacion.tipo === 'eliminar' && (
              <>
                <h3 className="text-lg font-semibold text-red-700 flex items-center gap-2">
                  ⚠️ Eliminar Usuario
                </h3>
                <p className="text-sm text-gray-600">
                  Vas a eliminar a <strong>{confirmacion.usuario.nombre_completo}</strong>.
                  Esta acción <strong>no se puede deshacer</strong>. Sus triajes realizados
                  se conservarán con auditoría anónima. ¿Deseas continuar?
                </p>
              </>
            )}
            {confirmacion.tipo === 'guardar_edicion' && editando && (
              <>
                <h3 className="text-lg font-semibold text-blue-700 flex items-center gap-2">
                  ✏️ Confirmar Cambios
                </h3>
                <p className="text-sm text-gray-600">
                  ¿Confirmas los cambios realizados al usuario{' '}
                  <strong>{editando.nombre_completo}</strong>?
                </p>
              </>
            )}

            <div className="flex justify-end gap-2">
              <button
                onClick={() => setConfirmacion(null)}
                disabled={ejecutando}
                className="text-sm px-4 py-2 rounded-md bg-gray-100 hover:bg-gray-200"
              >
                Cancelar
              </button>
              <button
                onClick={ejecutarConfirmacion}
                disabled={ejecutando}
                className={`text-sm px-4 py-2 rounded-md text-white font-medium disabled:opacity-50 ${
                  confirmacion.tipo === 'eliminar'
                    ? 'bg-red-600 hover:bg-red-700'
                    : confirmacion.tipo === 'desactivar'
                      ? 'bg-yellow-600 hover:bg-yellow-700'
                      : 'bg-blue-600 hover:bg-blue-700'
                }`}
              >
                {ejecutando
                  ? 'Procesando...'
                  : confirmacion.tipo === 'eliminar'
                    ? 'Sí, Eliminar'
                    : confirmacion.tipo === 'desactivar'
                      ? 'Sí, Desactivar'
                      : 'Sí, Guardar'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
