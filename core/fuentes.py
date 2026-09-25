"""
Fuentes tipográficas: probamos varias rutas típicas de Linux/Windows/Mac
y usamos la primera que exista. Si no encontramos ninguna, PIL usa una
fuente interna de respaldo (se ve más simple, pero no truena el programa).
"""

from __future__ import annotations

import os
from typing import Optional

from PIL import ImageFont

_CANDIDATOS_BOLD = [
    "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSerifBold.ttf",
    "C:\\Windows\\Fonts\\timesbd.ttf",
    "/System/Library/Fonts/Supplemental/Times New Roman Bold.ttf",
]
_CANDIDATOS_ITALIC = [
    "/usr/share/fonts/truetype/liberation/LiberationSerif-Italic.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Italic.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSerifItalic.ttf",
    "C:\\Windows\\Fonts\\timesi.ttf",
    "/System/Library/Fonts/Supplemental/Times New Roman Italic.ttf",
]


def _primera_existente(rutas: list[str]) -> Optional[str]:
    for r in rutas:
        if os.path.exists(r):
            return r
    return None


FONT_NOMBRE_DEFAULT = _primera_existente(_CANDIDATOS_BOLD)
FONT_MATRICULA_DEFAULT = _primera_existente(_CANDIDATOS_ITALIC)


def _cargar_fuente(ruta: Optional[str], tam: int):
    if ruta:
        try:
            return ImageFont.truetype(ruta, tam)
        except OSError:
            pass
    return ImageFont.load_default()


def _ajustar_fuente(draw, texto, ruta_fuente, tam_max, tam_min, ancho_max):
    """Reduce el tamaño de fuente hasta que el texto quepa en ancho_max."""
    tam = tam_max
    while tam > tam_min:
        font = _cargar_fuente(ruta_fuente, tam)
        bbox = draw.textbbox((0, 0), texto, font=font)
        ancho = bbox[2] - bbox[0]
        if ancho <= ancho_max:
            return font, ancho
        tam -= 1
    font = _cargar_fuente(ruta_fuente, tam_min)
    bbox = draw.textbbox((0, 0), texto, font=font)
    return font, bbox[2] - bbox[0]
