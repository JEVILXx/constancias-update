"""
Soporte de arrastrar y soltar (drag & drop), opcional: si el paquete
"tkinterdnd2" está instalado (pip install tkinterdnd2), la ventana
principal se construye sobre TkinterDnD.Tk y se activa soltar archivos
sobre la ventana. Si no está instalado, todo funciona igual, solo sin
esa comodidad (se usan los botones "Examinar…" normalmente).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import tkinter as tk
from PIL import Image

try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
    DND_DISPONIBLE = True
except ImportError:
    DND_DISPONIBLE = False
    DND_FILES = None

BaseVentana = TkinterDnD.Tk if DND_DISPONIBLE else tk.Tk


def parsear_rutas_dnd(data: str) -> list[str]:
    """
    tkinterdnd2 entrega las rutas soltadas como un solo string, separadas
    por espacios, con las que tienen espacios envueltas en llaves {}.
    Esta función las separa en una lista de rutas normales.
    """
    rutas = []
    actual = ""
    dentro_llaves = False
    for ch in data:
        if ch == "{":
            dentro_llaves = True
            actual = ""
        elif ch == "}":
            dentro_llaves = False
            rutas.append(actual)
            actual = ""
        elif ch == " " and not dentro_llaves:
            if actual:
                rutas.append(actual)
                actual = ""
        else:
            actual += ch
    if actual:
        rutas.append(actual)
    return rutas


def parece_codigo_qr(ruta: Path) -> bool:
    """
    Heurística simple para adivinar si una imagen es un código QR (en vez
    de una plantilla/póster): los QR son casi perfectamente cuadrados y
    solo tienen dos colores (blanco y negro), mientras que una plantilla
    normalmente no es cuadrada y tiene varios colores/decoración.
    """
    try:
        im = Image.open(ruta)
        ancho, alto = im.size
        if not alto:
            return False
        aspecto = ancho / alto
        if not (0.85 <= aspecto <= 1.15):
            return False  # las plantillas casi nunca son cuadradas
        gris = np.array(im.convert("L").resize((100, 100)))
        oscuros = (gris < 60).mean()
        claros = (gris > 200).mean()
        return (oscuros + claros) > 0.75 and oscuros > 0.05
    except Exception:
        return False
