"""
Motor del modo "Códigos QR": pega una imagen de QR ya generada dentro
del recuadro/placeholder de una plantilla (póster, diploma, etc.), sin
importar la plantilla que se use. Igual que con las constancias, la
posición del recuadro se detecta automáticamente, se puede marcar a
mano, o cae a un respaldo razonable si todo falla.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import numpy as np
from PIL import Image

from .rutas_datos import carpeta_datos
from .utils import _hash_archivo, quitar_acentos_archivo, _clave_orden_alfabetico

EXTENSIONES_IMAGEN_QR = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}

CAJAS_QR_MANUALES_PATH = carpeta_datos() / ".constancias_cajas_qr.json"


@dataclass
class ConfigQR:
    """Configuración para el modo 'Códigos QR': pega una imagen de QR ya
    generada dentro del recuadro/placeholder de una plantilla (póster,
    diploma, etc.), sin importar la plantilla que se use."""
    plantilla: Path
    # Si se dejan en None, el recuadro donde va el QR se resuelve así:
    # 1) marca manual guardada para esta plantilla
    # 2) detección automática (busca el recuadro claro/checkerboard)
    # 3) respaldo razonable basado en el tamaño de la imagen
    box_x0: Optional[int] = None
    box_y0: Optional[int] = None
    box_x1: Optional[int] = None
    box_y1: Optional[int] = None
    # Margen interno (como fracción del recuadro) para que el QR no
    # quede pegado a las esquinas redondeadas ni al borde.
    margen_relativo: float = 0.05
    fondo_qr: tuple = (255, 255, 255)  # detrás del QR si su imagen tiene transparencia


def _leer_cajas_qr_manuales() -> dict:
    if not CAJAS_QR_MANUALES_PATH.exists():
        return {}
    try:
        return json.loads(CAJAS_QR_MANUALES_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def cargar_caja_qr_manual(plantilla: Path) -> Optional[tuple[int, int, int, int]]:
    """Devuelve (x0, y0, x1, y1) si el usuario marcó esta plantilla a mano."""
    datos = _leer_cajas_qr_manuales()
    entrada = datos.get(_hash_archivo(plantilla))
    if not entrada:
        return None
    try:
        return int(entrada["x0"]), int(entrada["y0"]), int(entrada["x1"]), int(entrada["y1"])
    except (KeyError, TypeError, ValueError):
        return None


def guardar_caja_qr_manual(plantilla: Path, x0: int, y0: int, x1: int, y1: int) -> None:
    """Guarda (o reemplaza) la marca manual del recuadro del QR para esta plantilla."""
    datos = _leer_cajas_qr_manuales()
    if x1 < x0:
        x0, x1 = x1, x0
    if y1 < y0:
        y0, y1 = y1, y0
    datos[_hash_archivo(plantilla)] = {
        "x0": int(x0), "y0": int(y0), "x1": int(x1), "y1": int(y1), "archivo": plantilla.name,
    }
    CAJAS_QR_MANUALES_PATH.write_text(
        json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def eliminar_caja_qr_manual(plantilla: Path) -> None:
    """Borra la marca manual de esta plantilla (para volver al modo automático)."""
    datos = _leer_cajas_qr_manuales()
    clave = _hash_archivo(plantilla)
    if clave in datos:
        del datos[clave]
        CAJAS_QR_MANUALES_PATH.write_text(
            json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8"
        )


def detectar_caja_qr(im: Image.Image) -> Optional[tuple[int, int, int, int]]:
    """
    Busca automáticamente el recuadro claro (blanco/gris tipo
    "checkerboard" de transparencia, o simplemente un recuadro blanco)
    donde debe ir el código QR. Devuelve (x0, y0, x1, y1) en píxeles de
    la imagen original, o None si no encuentra nada confiable.

    Estrategia: la plantilla suele tener un fondo de color/oscuro y un
    recuadro claro bien definido para el QR (o una foto). Agrupamos las
    filas "claras" en corridas verticales; el recuadro real casi
    siempre es, por mucho, la corrida más alta (más filas) de toda la
    imagen — los letreros/banners de texto son mucho más angostos.
    """
    arr = np.array(im.convert("RGB")).astype(int)
    alto, ancho, _ = arr.shape
    if alto == 0 or ancho == 0:
        return None

    gris = arr.mean(axis=2)
    claro = gris > 200

    conteo_fila = claro.sum(axis=1)
    umbral_fila = 0.25 * ancho
    filas_candidatas = conteo_fila > umbral_fila

    grupos = []
    en_grupo = False
    inicio = 0
    for y, es in enumerate(filas_candidatas):
        if es and not en_grupo:
            inicio = y
            en_grupo = True
        elif not es and en_grupo:
            grupos.append((inicio, y - 1))
            en_grupo = False
    if en_grupo:
        grupos.append((inicio, len(filas_candidatas) - 1))

    if not grupos:
        return None

    # Nos quedamos con el grupo más alto (más filas) — el recuadro del
    # QR casi siempre es mucho más grande que cualquier letrero de texto.
    y0, y1 = max(grupos, key=lambda g: g[1] - g[0])
    if (y1 - y0) < 0.10 * alto:
        return None  # demasiado pequeño para ser un recuadro real

    sub = claro[y0:y1 + 1]
    conteo_col = sub.sum(axis=0)
    umbral_col = 0.5 * (y1 - y0 + 1)
    cols_candidatas = np.where(conteo_col > umbral_col)[0]
    if cols_candidatas.size == 0:
        return None
    x0, x1 = int(cols_candidatas.min()), int(cols_candidatas.max())
    if (x1 - x0) < 0.10 * ancho:
        return None

    return x0, y0, x1, y1


def resolver_geometria_caja_qr(config, im: Image.Image) -> tuple[int, int, int, int, str]:
    """Misma idea que resolver_geometria_linea, pero para el recuadro del QR.
    'config' es cualquier objeto con atributos .box_x0/.box_y0/.box_x1/
    .box_y1/.plantilla (duck typing, normalmente un ConfigQR)."""
    if None not in (config.box_x0, config.box_y0, config.box_x1, config.box_y1):
        return config.box_x0, config.box_y0, config.box_x1, config.box_y1, "explicito"

    manual = cargar_caja_qr_manual(Path(config.plantilla))
    if manual:
        return manual[0], manual[1], manual[2], manual[3], "manual"

    auto = detectar_caja_qr(im)
    if auto:
        return auto[0], auto[1], auto[2], auto[3], "auto"

    ancho, alto = im.size
    lado = int(min(ancho, alto) * 0.6)
    x0 = (ancho - lado) // 2
    x1 = x0 + lado
    y0 = int(alto * 0.20)
    y1 = y0 + lado
    return x0, y0, x1, y1, "respaldo"


def analizar_plantilla_qr(plantilla: Path) -> dict:
    """Utilidad para la interfaz: reporta qué recuadro se usaría para el QR."""
    im = Image.open(plantilla).convert("RGB")
    x0, y0, x1, y1, origen = resolver_geometria_caja_qr(ConfigQR(plantilla=plantilla), im)
    return {
        "x0": x0, "y0": y0, "x1": x1, "y1": y1, "origen": origen,
        "ancho_img": im.width, "alto_img": im.height,
    }


def colocar_qr_en_plantilla(
    config: ConfigQR, qr_path: Path, devolver_info: bool = False,
):
    """
    Devuelve la imagen (PIL) de la plantilla con el QR pegado dentro de
    su recuadro, centrado y ajustado al tamaño (conservando su
    proporción, sin deformarlo), sin importar la plantilla ni la
    imagen de QR que se use.
    """
    plantilla_im = Image.open(config.plantilla).convert("RGB")
    x0, y0, x1, y1, origen_caja = resolver_geometria_caja_qr(config, plantilla_im)

    ancho_caja = x1 - x0
    alto_caja = y1 - y0
    margen_x = int(ancho_caja * config.margen_relativo)
    margen_y = int(alto_caja * config.margen_relativo)
    destino_ancho = max(1, ancho_caja - 2 * margen_x)
    destino_alto = max(1, alto_caja - 2 * margen_y)

    qr_im = Image.open(qr_path)
    if qr_im.mode in ("RGBA", "LA") or (qr_im.mode == "P" and "transparency" in qr_im.info):
        qr_im = qr_im.convert("RGBA")
        fondo = Image.new("RGB", qr_im.size, config.fondo_qr)
        fondo.paste(qr_im, mask=qr_im.split()[-1])
        qr_im = fondo
    else:
        qr_im = qr_im.convert("RGB")

    escala = min(destino_ancho / qr_im.width, destino_alto / qr_im.height)
    nuevo_ancho = max(1, round(qr_im.width * escala))
    nuevo_alto = max(1, round(qr_im.height * escala))
    qr_redimensionado = qr_im.resize((nuevo_ancho, nuevo_alto), Image.LANCZOS)

    pos_x = x0 + margen_x + (destino_ancho - nuevo_ancho) // 2
    pos_y = y0 + margen_y + (destino_alto - nuevo_alto) // 2

    resultado = plantilla_im.copy()
    resultado.paste(qr_redimensionado, (pos_x, pos_y))

    if devolver_info:
        info = {"box_x0": x0, "box_y0": y0, "box_x1": x1, "box_y1": y1, "origen_caja": origen_caja}
        return resultado, info
    return resultado


def procesar_carpeta_qrs(
    config: ConfigQR,
    carpeta_qrs: Path,
    carpeta_salida: Path,
    formato_imagen: str = "PNG",
    generar_pdf_combinado: bool = True,
    on_progreso: Optional[Callable[[int, int, str], None]] = None,
) -> list[Path]:
    """
    Toma cada imagen de QR dentro de carpeta_qrs (ya nombradas por
    persona, como las tiene el usuario) y genera una IMAGEN (PNG por
    defecto, se puede abrir con cualquier visor) por cada una, con el
    QR pegado en la plantilla, usando el mismo nombre de archivo que ya
    traía el QR. Además arma un "QRs_TODOS.pdf" con todas juntas, útil
    solo si se quieren mandar a imprimir de un jalón (las imágenes
    individuales son el resultado principal). Devuelve la lista de
    rutas generadas (el PDF combinado, si se genera, queda al final).
    """
    archivos_qr = sorted(
        [p for p in carpeta_qrs.iterdir() if p.suffix.lower() in EXTENSIONES_IMAGEN_QR],
        key=lambda p: _clave_orden_alfabetico(p.stem),
    )
    total = len(archivos_qr)
    generados: list[Path] = []
    imagenes_generadas: list[Image.Image] = []
    nombres_archivo_usados: set[str] = set()

    extension = ".jpg" if formato_imagen.upper() in ("JPG", "JPEG") else f".{formato_imagen.lower()}"

    carpeta_salida.mkdir(parents=True, exist_ok=True)

    for i, qr_path in enumerate(archivos_qr, start=1):
        try:
            im = colocar_qr_en_plantilla(config, qr_path)
        except Exception as e:
            if on_progreso:
                on_progreso(i, total, f"(omitido, error con {qr_path.name}: {e})")
            continue

        base = quitar_acentos_archivo(qr_path.stem)
        nombre_archivo = f"{base}{extension}"
        candidato = nombre_archivo
        contador = 2
        while candidato in nombres_archivo_usados:
            candidato = f"{base}_{contador}{extension}"
            contador += 1
        nombre_archivo = candidato
        nombres_archivo_usados.add(nombre_archivo)

        ruta_imagen = carpeta_salida / nombre_archivo
        if extension == ".jpg":
            im.convert("RGB").save(ruta_imagen, "JPEG", quality=95)
        else:
            im.save(ruta_imagen, formato_imagen.upper())
        generados.append(ruta_imagen)
        imagenes_generadas.append(im)

        if on_progreso:
            on_progreso(i, total, qr_path.stem)

    if generados and generar_pdf_combinado:
        ruta_combinado = carpeta_salida / "QRs_TODOS.pdf"
        primero, *resto = [im.convert("RGB") for im in imagenes_generadas]
        primero.save(ruta_combinado, "PDF", resolution=150.0, save_all=True, append_images=resto)
        generados.append(ruta_combinado)

    return generados
