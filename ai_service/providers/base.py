"""Clase base para proveedores LLM.

Cualquier proveedor nuevo (nube o local) debe heredar de `LLMProvider`
e implementar sus dos métodos: `disponible()` y `crear()`.
"""

from abc import ABC, abstractmethod
from typing import Any


class LLMProvider(ABC):
    """Contrato para proveedores de modelos LLM.

    Atributos de clase esperados:
        nombre: Nombre legible usado como clave del diccionario de modelos
            (es el valor que se muestra en la UI y se guarda en auditoría).
        descripcion: Breve descripción del proveedor (para logs).
    """

    nombre: str = ""
    descripcion: str = ""

    @abstractmethod
    def disponible(self) -> bool:
        """Indica si el proveedor cumple los requisitos para cargarse.

        Debe ser una comprobación barata y sin efectos secundarios
        (ej: presencia de API key, paquete instalado, etc.).
        """
        raise NotImplementedError

    @abstractmethod
    def crear(self) -> Any:
        """Crea y devuelve la instancia del LLM (compatible con llama-index).

        Raises:
            ConfigurationError: Si la configuración es inválida.
        """
        raise NotImplementedError
