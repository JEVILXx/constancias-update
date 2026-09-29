"""
Carpeta base del programa: de dónde deben colgar los archivos que el
programa lee/escribe junto a sí mismo (plantilla por defecto, carpeta
de salida, preferencias, marcas manuales, etc.).

Corriendo como script normal, es la carpeta del proyecto. Empaquetado
como .exe con PyInstaller, sys.frozen es True y hay que usar la carpeta
donde está el .exe (no la carpeta temporal donde PyInstaller descomprime
el programa, que se borra al cerrar).
"""

from __future__ import annotations

import sys
from pathlib import Path


def carpeta_base() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    # __file__ aquí es .../<carpeta_del_proyecto>/core/base_dir.py
    return Path(__file__).resolve().parent.parent
