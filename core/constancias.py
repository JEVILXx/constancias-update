"""
Motor de constancias: arma la imagen de cada constancia (nombre y
matrícula acomodados sobre la línea de la plantilla) y procesa un Excel
completo generando un PDF por persona más un PDF combinado.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

import pandas as pd
from PIL import Image, ImageDraw
from pypdf import PdfReader, PdfWriter

from .fuentes import FONT_NOMBRE_DEFAULT, FONT_MATRICULA_DEFAULT, _ajustar_fuente
from .lineas import resolver_geometria_linea
from .utils import quitar_acentos_archivo, _clave_orden_alfabetico, limpiar_matricula, guardar_como_pdf
from .correo import CorreoConfig, CuentaEnvio, ErrorEnvioCorreo, enviar_correo_con_adjunto, _correo_valido


@dataclass
class Config:
    plantilla: Path
    # Si se dejan en None, la posición de la línea se resuelve automáticamente:
    # 1) override manual guardado para esta plantilla (ver core.lineas)
    # 2) detección automática de la línea/raya en la imagen
    # 3) valor de respaldo razonable basado en el tamaño de la imagen
    line_x0: Optional[int] = None
    line_x1: Optional[int] = None
    line_y: Optional[int] = None
    margen_interno: int = 20
    font_nombre: Optional[str] = field(default_factory=lambda: FONT_NOMBRE_DEFAULT)
    font_matricula: Optional[str] = field(default_factory=lambda: FONT_MATRICULA_DEFAULT)
    # Si se dejan en None, el tamaño máx/mín de fuente se calcula en proporción
    # a la altura de la plantilla, así que se ve bien sin importar la resolución.
    tam_nombre_max: Optional[int] = None
    tam_nombre_min: Optional[int] = None
    tam_matricula_max: Optional[int] = None
    tam_matricula_min: Optional[int] = None
    color_nombre: tuple = (25, 25, 25)
    color_matricula: tuple = (70, 70, 70)


def analizar_plantilla(plantilla: Path) -> dict:
    """Utilidad para la interfaz: reporta qué línea se usaría y de dónde
    salió, sin tener que dibujar nada todavía."""
    im = Image.open(plantilla).convert("RGB")
    x0, x1, y, origen = resolver_geometria_linea(Config(plantilla=plantilla), im)
    return {"x0": x0, "x1": x1, "y": y, "origen": origen, "ancho_img": im.width, "alto_img": im.height}


def render_certificado(
    config: Config, nombre: str, matricula: Optional[str],
    devolver_info: bool = False,
):
    """
    Devuelve la imagen (PIL) de la constancia ya con el nombre/matrícula
    escritos, acomodados automáticamente sobre la línea "A: ______" de
    la plantilla (sin importar cuál plantilla sea).

    Si devolver_info=True, devuelve (imagen, info) donde info incluye
    la geometría usada y su origen ("manual"/"auto"/"respaldo"/"explicito"),
    útil para mostrarlo en la interfaz.
    """
    im = Image.open(config.plantilla).convert("RGB")
    draw = ImageDraw.Draw(im)

    line_x0, line_x1, line_y, origen_linea = resolver_geometria_linea(config, im)

    # Tamaños de fuente proporcionales a la altura de la plantilla si no
    # se fijaron explícitamente, para que se vean bien sin importar la
    # resolución de cada certificado.
    alto_img = im.height
    tam_nombre_max = config.tam_nombre_max or max(14, round(alto_img * 0.039))
    tam_nombre_min = config.tam_nombre_min or max(9, round(alto_img * 0.016))
    tam_matricula_max = config.tam_matricula_max or max(9, round(alto_img * 0.021))
    tam_matricula_min = config.tam_matricula_min or max(7, round(alto_img * 0.012))

    ancho_disponible = (line_x1 - line_x0) - 2 * config.margen_interno
    ancho_disponible = max(ancho_disponible, 10)
    texto_matricula = f"   (Matrícula: {matricula})" if matricula else ""

    if texto_matricula:
        ancho_mat_max = int(ancho_disponible * 0.35)
        font_mat, w_mat = _ajustar_fuente(
            draw, texto_matricula, config.font_matricula,
            tam_matricula_max, tam_matricula_min, ancho_mat_max,
        )
    else:
        font_mat, w_mat = None, 0

    ancho_nombre_max = ancho_disponible - w_mat
    font_nombre, w_nombre = _ajustar_fuente(
        draw, nombre, config.font_nombre,
        tam_nombre_max, tam_nombre_min, ancho_nombre_max,
    )

    total_w = w_nombre + w_mat
    start_x = line_x0 + ((line_x1 - line_x0) - total_w) / 2
    # El texto se apoya justo encima de la línea detectada, con un
    # pequeño respiro proporcional al tamaño de letra (no un número
    # fijo), así queda igual de "pegado" a la línea sin importar la
    # resolución de la plantilla o el tamaño del nombre.
    y_baseline = line_y - max(3, round(tam_nombre_max * 0.12))

    draw.text((start_x, y_baseline), nombre, font=font_nombre, fill=config.color_nombre, anchor="ls")
    if texto_matricula:
        draw.text(
            (start_x + w_nombre, y_baseline),
            texto_matricula, font=font_mat, fill=config.color_matricula, anchor="ls",
        )

    if devolver_info:
        info = {
            "line_x0": line_x0, "line_x1": line_x1, "line_y": line_y,
            "origen_linea": origen_linea,
        }
        return im, info
    return im


class FilaInvalidaError(Exception):
    pass


def procesar_excel(
    config: Config,
    excel_path: Path,
    carpeta_salida: Path,
    col_nombre: str,
    col_matricula: Optional[str],
    hoja=0,
    col_correo: Optional[str] = None,
    correo_config: Optional[CorreoConfig] = None,
    cuentas_envio: Optional[list[CuentaEnvio]] = None,
    on_progreso: Optional[Callable[[int, int, str], None]] = None,
    on_conteo_actualizado: Optional[Callable[[str, int], None]] = None,
) -> list[Path]:
    """
    Genera un PDF por cada fila del Excel. Devuelve la lista de rutas generadas
    (la última es siempre "Constancias_TODAS.pdf").
    on_progreso(i, total, nombre) se llama después de procesar cada fila; si
    se está enviando por correo, el estado del envío se agrega al texto de
    "nombre" que recibe on_progreso (para que se vea en el log de la interfaz).

    Si col_correo y (correo_config o cuentas_envio) se indican, después de
    generar cada PDF se manda por correo a la dirección de esa columna (se
    salta, sin truncar el proceso completo, si la fila no tiene correo válido
    o si el envío falla).

    Si se pasan varias cuentas en cuentas_envio, se usa SIEMPRE la primera
    cuenta con cupo disponible (según su limite_diario y lo que ya lleva
    enviado hoy); cuando esa cuenta se queda sin cupo, se pasa automáticamente
    a la siguiente y se sigue justo donde se quedó (no se reinicia el conteo).
    on_conteo_actualizado(remitente, nuevo_total_de_hoy) se llama justo
    después de cada envío exitoso, para que quien llama pueda guardar el
    avance en disco por si el proceso se interrumpe a la mitad.
    """
    if cuentas_envio:
        cuentas = cuentas_envio
    elif correo_config:
        cuentas = [CuentaEnvio(config=correo_config, limite_diario=10**9)]
    else:
        cuentas = None

    df = pd.read_excel(excel_path, sheet_name=hoja)
    df = df.dropna(how="all")

    # Ordenar alfabéticamente por nombre (ignorando acentos/mayúsculas),
    # así tanto los PDFs individuales como el combinado quedan en orden.
    df["_orden"] = df[col_nombre].apply(lambda v: _clave_orden_alfabetico(v) if pd.notna(v) else "\uffff")
    df = df.sort_values("_orden", kind="stable").drop(columns="_orden")

    filas = list(df.iterrows())
    total = len(filas)
    generados: list[Path] = []
    nombres_archivo_usados: set[str] = set()
    indice_cuenta_activa = 0

    carpeta_salida.mkdir(parents=True, exist_ok=True)

    for i, (_, fila) in enumerate(filas, start=1):
        nombre_val = fila.get(col_nombre)
        nombre = "" if pd.isna(nombre_val) else str(nombre_val).strip()
        if not nombre:
            if on_progreso:
                on_progreso(i, total, "(fila vacía, omitida)")
            continue

        matricula = None
        if col_matricula:
            matricula = limpiar_matricula(fila.get(col_matricula))

        im = render_certificado(config, nombre, matricula)

        base = quitar_acentos_archivo(nombre)
        if matricula:
            base = f"{base}_{quitar_acentos_archivo(matricula)}"
        nombre_archivo = f"Constancia_{base}.pdf"

        # Evitar sobrescribir si dos personas quedan con el mismo nombre de archivo
        candidato = nombre_archivo
        contador = 2
        while candidato in nombres_archivo_usados:
            candidato = f"Constancia_{base}_{contador}.pdf"
            contador += 1
        nombre_archivo = candidato
        nombres_archivo_usados.add(nombre_archivo)

        ruta_pdf = carpeta_salida / nombre_archivo
        guardar_como_pdf(im, ruta_pdf)
        generados.append(ruta_pdf)

        reporte = nombre
        if col_correo and cuentas:
            correo_val = fila.get(col_correo)
            correo_str = "" if pd.isna(correo_val) else str(correo_val).strip()
            if not correo_str or not _correo_valido(correo_str):
                reporte = f"{nombre} — sin correo válido, no se envió"
            else:
                # Avanza a la siguiente cuenta si la actual ya no tiene cupo hoy.
                aviso_cambio = ""
                while indice_cuenta_activa < len(cuentas) and not cuentas[indice_cuenta_activa].le_queda_cupo:
                    agotada = cuentas[indice_cuenta_activa].remitente
                    indice_cuenta_activa += 1
                    if indice_cuenta_activa < len(cuentas):
                        aviso_cambio = (
                            f"[{agotada} llegó a su límite diario, "
                            f"cambiando a {cuentas[indice_cuenta_activa].remitente}] "
                        )

                if indice_cuenta_activa >= len(cuentas):
                    reporte = f"{nombre} — todas las cuentas llegaron a su límite diario, no se envió"
                else:
                    cuenta = cuentas[indice_cuenta_activa]
                    sufijo_cuenta = f" (vía {cuenta.remitente})" if len(cuentas) > 1 else ""
                    try:
                        enviar_correo_con_adjunto(cuenta.config, correo_str, nombre, ruta_pdf)
                        cuenta.ya_enviados_hoy += 1
                        reporte = f"{aviso_cambio}{nombre} — correo enviado a {correo_str}{sufijo_cuenta}"
                        if on_conteo_actualizado:
                            on_conteo_actualizado(cuenta.remitente, cuenta.ya_enviados_hoy)
                    except ErrorEnvioCorreo as e:
                        reporte = f"{aviso_cambio}{nombre} — ERROR al enviar correo a {correo_str}{sufijo_cuenta}: {e}"

        if on_progreso:
            on_progreso(i, total, reporte)

    if generados:
        writer_todas = PdfWriter()
        for ruta_pdf in generados:
            reader = PdfReader(str(ruta_pdf))
            for page in reader.pages:
                writer_todas.add_page(page)
        ruta_combinado = carpeta_salida / "Constancias_TODAS.pdf"
        with open(ruta_combinado, "wb") as f:
            writer_todas.write(f)
        generados.append(ruta_combinado)

    return generados
