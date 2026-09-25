"""
Ubicación automática y manual de la línea "A: ______" en las plantillas
de constancias.

Cada plantilla puede tener la línea del nombre en un lugar distinto. En
vez de usar siempre las mismas coordenadas fijas (lo que hacía que el
nombre quedara chueco/encimado en plantillas distintas a la original),
aquí:
  1. Detectamos automáticamente el trazo horizontal más probable.
  2. Si el usuario marcó la línea a mano para esa plantilla exacta,
     esa marca manual tiene prioridad sobre la detección automática.
  3. Si todo falla, usamos una posición de respaldo razonable según el
     tamaño de la imagen (para que nunca truene el programa).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image

from .rutas_datos import carpeta_datos
from .utils import _hash_archivo

LINEAS_MANUALES_PATH = carpeta_datos() / ".constancias_lineas.json"


def _leer_lineas_manuales() -> dict:
    if not LINEAS_MANUALES_PATH.exists():
        return {}
    try:
        return json.loads(LINEAS_MANUALES_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def cargar_linea_manual(plantilla: Path) -> Optional[tuple[int, int, int]]:
    """Devuelve (x0, x1, y) si el usuario marcó esta plantilla a mano."""
    datos = _leer_lineas_manuales()
    entrada = datos.get(_hash_archivo(plantilla))
    if not entrada:
        return None
    try:
        return int(entrada["x0"]), int(entrada["x1"]), int(entrada["y"])
    except (KeyError, TypeError, ValueError):
        return None


def guardar_linea_manual(plantilla: Path, x0: int, x1: int, y: int) -> None:
    """Guarda (o reemplaza) la marca manual de esta plantilla."""
    datos = _leer_lineas_manuales()
    if x1 < x0:
        x0, x1 = x1, x0
    datos[_hash_archivo(plantilla)] = {
        "x0": int(x0), "x1": int(x1), "y": int(y), "archivo": plantilla.name,
    }
    LINEAS_MANUALES_PATH.write_text(
        json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def eliminar_linea_manual(plantilla: Path) -> None:
    """Borra la marca manual de esta plantilla (para volver al modo automático)."""
    datos = _leer_lineas_manuales()
    clave = _hash_archivo(plantilla)
    if clave in datos:
        del datos[clave]
        LINEAS_MANUALES_PATH.write_text(
            json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8"
        )


def _otsu_threshold(arr: np.ndarray) -> float:
    """Umbral de Otsu simple: separa la imagen en 'claro' y 'oscuro' de
    forma automática, sin necesitar un número fijo que dependa del
    fondo/colores de cada plantilla."""
    hist, _ = np.histogram(arr, bins=256, range=(0, 255))
    hist = hist.astype(float)
    total = arr.size
    suma_total = float(np.dot(np.arange(256), hist))
    suma_b = 0.0
    peso_b = 0.0
    mejor_varianza = 0.0
    umbral = 127
    for i in range(256):
        peso_b += hist[i]
        if peso_b == 0:
            continue
        peso_f = total - peso_b
        if peso_f == 0:
            break
        suma_b += i * hist[i]
        media_b = suma_b / peso_b
        media_f = (suma_total - suma_b) / peso_f
        varianza = peso_b * peso_f * (media_b - media_f) ** 2
        if varianza > mejor_varianza:
            mejor_varianza = varianza
            umbral = i
    return umbral


def _corrida_mas_larga(mask: np.ndarray) -> tuple[int, int]:
    """Devuelve (inicio, longitud) de la corrida más larga de True en mask."""
    if not mask.any():
        return 0, 0
    relleno = np.concatenate(([0], mask.astype(int), [0]))
    diferencia = np.diff(relleno)
    inicios = np.where(diferencia == 1)[0]
    finales = np.where(diferencia == -1)[0]
    largos = finales - inicios
    idx = int(np.argmax(largos))
    return int(inicios[idx]), int(largos[idx])


def detectar_linea_horizontal(im: Image.Image) -> Optional[tuple[int, int, int]]:
    """
    Busca automáticamente el trazo horizontal (la raya "A: ______") en
    la imagen de la plantilla y devuelve (x0, x1, y) en píxeles de la
    imagen original, o None si no encuentra nada confiable.
    """
    gris = np.array(im.convert("L"))
    alto, ancho = gris.shape

    margen_x = max(10, int(ancho * 0.06))
    y0 = int(alto * 0.15)
    y1 = int(alto * 0.85)
    if y1 <= y0:
        return None

    banda = gris[y0:y1, margen_x:ancho - margen_x]
    ancho_util = banda.shape[1]
    if ancho_util <= 0 or banda.size == 0:
        return None

    umbral = _otsu_threshold(banda)

    candidatos = []  # (largo, fila_relativa, inicio_col)
    for fila in range(banda.shape[0]):
        mask = banda[fila] < umbral
        inicio, largo = _corrida_mas_larga(mask)
        if largo >= 0.20 * ancho_util:
            candidatos.append((largo, fila, inicio))

    if not candidatos:
        return None

    # Agrupamos filas contiguas (una raya de 1-3 px puede aparecer en
    # varias filas seguidas); nos quedamos con la de mayor largo de
    # cada grupo, y descartamos grupos demasiado gruesos (probablemente
    # no son una línea sino una franja de color de fondo).
    candidatos.sort(key=lambda t: t[1])
    grupos: list[list[tuple[int, int, int]]] = []
    for c in candidatos:
        if grupos and c[1] - grupos[-1][-1][1] <= 3:
            grupos[-1].append(c)
        else:
            grupos.append([c])

    mejores = []
    for grupo in grupos:
        grosor = grupo[-1][1] - grupo[0][1] + 1
        if grosor > 8:
            continue  # muy grueso para ser una simple raya
        largo, fila, inicio = max(grupo, key=lambda t: t[0])
        mejores.append((largo, fila, inicio))

    if not mejores:
        return None

    largo, fila, inicio = max(mejores, key=lambda t: t[0])
    x0 = inicio + margen_x
    x1 = x0 + largo
    y = fila + y0
    return x0, x1, y


def resolver_geometria_linea(config, im: Image.Image) -> tuple[int, int, int, str]:
    """
    Decide qué coordenadas (x0, x1, y) usar para escribir el nombre, y
    de dónde salieron ("explicito" / "manual" / "auto" / "respaldo")
    para poder informarlo en la interfaz. 'config' es cualquier objeto
    con atributos .line_x0, .line_x1, .line_y y .plantilla (duck typing,
    normalmente un core.constancias.Config).
    """
    if config.line_x0 is not None and config.line_x1 is not None and config.line_y is not None:
        return config.line_x0, config.line_x1, config.line_y, "explicito"

    manual = cargar_linea_manual(Path(config.plantilla))
    if manual:
        return manual[0], manual[1], manual[2], "manual"

    auto = detectar_linea_horizontal(im)
    if auto:
        return auto[0], auto[1], auto[2], "auto"

    ancho, alto = im.size
    x0 = int(ancho * 0.15)
    x1 = int(ancho * 0.85)
    y = int(alto * 0.60)
    return x0, x1, y, "respaldo"
