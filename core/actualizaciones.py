"""
Sistema de actualizaciones.

Cómo funciona:
  1. El programa tiene un archivo VERSION con su número de versión
     actual (ej. "1.0.0").
  2. De vez en cuando (al abrir el programa, o cuando el usuario le da
     a "Buscar actualizaciones"), se descarga un pequeño archivo JSON
     ("el manifiesto") desde una URL que tú controlas, con algo así:
         {"version": "1.1.0", "url_zip": "https://.../v1.1.0.zip", "notas": "..."}
  3. Si la versión del manifiesto es más nueva que la instalada, se le
     avisa al usuario. Si acepta, se descarga ese .zip y se reemplazan
     los archivos del programa por los nuevos, reiniciando solo.

Cómo publicar una actualización (tú, cuando corrijas algo o agregues
una función nueva) — ver LEEME.txt, sección 11, para el paso a paso
completo con opciones gratis de dónde subir los archivos.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path
from typing import Callable, Optional

from .base_dir import carpeta_base

VERSION_ACTUAL_PATH = carpeta_base() / "VERSION"


def version_actual() -> str:
    try:
        return VERSION_ACTUAL_PATH.read_text(encoding="utf-8").strip() or "0.0.0"
    except Exception:
        return "0.0.0"


def _version_a_tupla(v: str) -> tuple:
    partes = []
    for p in str(v).strip().split("."):
        try:
            partes.append(int(p))
        except ValueError:
            partes.append(0)
    return tuple(partes)


def hay_version_mas_nueva(local: str, remota: str) -> bool:
    return _version_a_tupla(remota) > _version_a_tupla(local)


class ErrorActualizacion(Exception):
    pass


def buscar_actualizacion(url_manifiesto: str, timeout: int = 8) -> Optional[dict]:
    """
    Descarga el manifiesto remoto. Devuelve el dict con la info de la
    nueva versión si hay una más nueva que la instalada, o None si ya
    estás en la última versión, si la URL está vacía, o si no se pudo
    revisar (sin internet, servidor caído, etc. — falla en silencio,
    nunca debe tronar el programa por esto).
    """
    if not url_manifiesto:
        return None
    try:
        with urllib.request.urlopen(url_manifiesto, timeout=timeout) as resp:
            datos = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None

    remota = str(datos.get("version", "")).strip()
    if not remota:
        return None
    if hay_version_mas_nueva(version_actual(), remota):
        return datos
    return None


def descargar_actualizacion(
    url_zip: str, on_progreso: Optional[Callable[[int, int], None]] = None
) -> Path:
    """Descarga el .zip de la actualización a un archivo temporal y devuelve su ruta."""
    tmp = Path(tempfile.mkdtemp(prefix="actualizacion_")) / "actualizacion.zip"

    def _reportar(bloque_num, tam_bloque, total):
        if on_progreso and total > 0:
            on_progreso(min(bloque_num * tam_bloque, total), total)

    try:
        urllib.request.urlretrieve(url_zip, tmp, _reportar)
    except Exception as e:
        raise ErrorActualizacion(f"No se pudo descargar la actualización: {e}") from e
    return tmp


def aplicar_actualizacion_y_reiniciar(ruta_zip: Path) -> None:
    """
    Extrae el .zip descargado, y lanza un comando externo que espera a
    que este programa se cierre, copia los archivos nuevos encima de
    los actuales, y vuelve a abrir el programa ya actualizado.

    Esta función TERMINA EL PROGRAMA (no regresa) si todo sale bien.
    Solo funciona para el .exe compilado en Windows — si el programa
    está corriendo como script de Python normal, o en otro sistema
    operativo, lanza ErrorActualizacion para que la interfaz ofrezca
    la descarga manual en su lugar.
    """
    if sys.platform != "win32" or not getattr(sys, "frozen", False):
        raise ErrorActualizacion(
            "La instalación automática solo funciona en el .exe compilado de Windows. "
            "Descarga el .zip y reemplaza la carpeta del programa a mano."
        )

    carpeta_actual = carpeta_base()
    carpeta_extraida = Path(tempfile.mkdtemp(prefix="actualizacion_extraida_"))
    try:
        with zipfile.ZipFile(ruta_zip, "r") as z:
            z.extractall(carpeta_extraida)
    except Exception as e:
        raise ErrorActualizacion(f"El archivo descargado no se pudo abrir: {e}") from e

    # Si el .zip trae todo dentro de una sola subcarpeta (lo más común
    # al comprimir la carpeta "dist/GeneradorConstanciasQR"), usamos
    # directamente esa subcarpeta como origen de la copia.
    contenido = list(carpeta_extraida.iterdir())
    origen = contenido[0] if len(contenido) == 1 and contenido[0].is_dir() else carpeta_extraida

    exe_actual = Path(sys.executable)
    nombre_exe = exe_actual.name

    # Comando que: espera 2 segundos a que este proceso termine de
    # cerrarse del todo, copia los archivos nuevos encima de los
    # actuales (robocopy /E copia subcarpetas, /IS /IT vuelve a copiar
    # aunque el destino ya tenga un archivo con ese nombre), y vuelve a
    # abrir el programa. Se ejecuta en una ventana de cmd aparte,
    # desconectada de este proceso, para que sobreviva a que este se cierre.
    comando = (
        f'cmd /c "timeout /t 2 /nobreak >nul & '
        f'robocopy \"{origen}\" \"{carpeta_actual}\" /E /IS /IT /R:3 /W:1 & '
        f'start "" \"{carpeta_actual / nombre_exe}\""'
    )
    subprocess.Popen(comando, shell=True, creationflags=subprocess.DETACHED_PROCESS)
    os._exit(0)
