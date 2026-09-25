"""
Utilidades generales compartidas por los demás módulos del motor:
nombres de archivo seguros, orden alfabético, búsqueda de columnas de
Excel, limpieza de matrícula, huella de archivo y guardado en PDF.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from pathlib import Path
from typing import Optional

import pandas as pd
from PIL import Image


def quitar_acentos_archivo(texto: str) -> str:
    """Convierte un nombre en algo seguro para usar como nombre de archivo."""
    nfkd = unicodedata.normalize("NFKD", texto)
    sin_acentos = "".join(c for c in nfkd if not unicodedata.combining(c))
    limpio = re.sub(r"[^A-Za-z0-9 _-]", "", sin_acentos).strip()
    limpio = re.sub(r"\s+", "_", limpio)
    return limpio or "constancia"


def _clave_orden_alfabetico(texto: str) -> str:
    """Clave para ordenar nombres ignorando acentos/mayúsculas (orden alfabético natural)."""
    nfkd = unicodedata.normalize("NFKD", str(texto))
    sin_acentos = "".join(c for c in nfkd if not unicodedata.combining(c))
    return sin_acentos.strip().lower()


def encontrar_columna(df: pd.DataFrame, candidatos: list[str]) -> Optional[str]:
    """Busca, sin importar mayúsculas/acentos, alguna columna que coincida."""

    def normaliza(s):
        return unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower().strip()

    cols_norm = {normaliza(c): c for c in df.columns}
    for cand in candidatos:
        cand_n = normaliza(cand)
        if cand_n in cols_norm:
            return cols_norm[cand_n]
    return None


def limpiar_matricula(valor) -> Optional[str]:
    """Convierte el valor crudo de la celda de Excel en texto de matrícula limpio."""
    if pd.isna(valor):
        return None
    texto = str(valor).strip()
    if not texto:
        return None
    if texto.endswith(".0"):
        texto = texto[:-2]
    return texto


def _hash_archivo(ruta: Path) -> str:
    """Huella del contenido del archivo, para identificar una plantilla
    sin importar cómo se llame o en qué carpeta esté."""
    h = hashlib.md5()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(65536), b""):
            h.update(bloque)
    return h.hexdigest()


def guardar_como_pdf(im: Image.Image, ruta_salida_pdf: Path):
    ruta_salida_pdf.parent.mkdir(parents=True, exist_ok=True)
    im.save(ruta_salida_pdf, "PDF", resolution=150.0)
