"""
Carpeta donde se guardan los datos del usuario (marcas manuales de línea/QR,
preferencias, cuentas de correo).

Antes se guardaban "junto al código". Con el sistema de actualizaciones el
código vive en una carpeta de versión que cambia con cada actualización, así
que los datos se guardan aparte y NO se pierden al actualizar:

  - Ejecutando con  python constancias_gui.py  -> la carpeta del proyecto
    (igual que siempre).
  - Ejecutando el .exe (launcher.py)            -> la carpeta que define el
    lanzador en la variable CONSTANCIAS_DATOS
    (en Windows: %LOCALAPPDATA%\\GeneradorConstancias).
"""

from __future__ import annotations

import os
from pathlib import Path


def carpeta_datos() -> Path:
    env = os.environ.get("CONSTANCIAS_DATOS")
    if env:
        ruta = Path(env)
        try:
            ruta.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        return ruta
    return Path(__file__).resolve().parent.parent
