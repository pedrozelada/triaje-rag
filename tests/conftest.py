"""Configuración de pytest."""

import pytest
import sys
import os

# Agregar root al path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
