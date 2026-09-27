"""Routers del panel de administración.

El prefijo y el tag se declaran una sola vez aquí; cada submódulo aporta sus
rutas. Todos exigen rol de administrador (`require_admin`), así que una ruta
nueva no puede olvidar el control de acceso.
"""

from fastapi import APIRouter

from backend.api.admin import estadisticas, indice, usuarios

router = APIRouter(prefix="/api/admin", tags=["admin"])

router.include_router(estadisticas.router)
router.include_router(usuarios.router)
router.include_router(indice.router)
