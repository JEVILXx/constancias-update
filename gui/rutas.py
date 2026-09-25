"""Rutas y constantes de archivo que usa la interfaz (plantilla por
defecto, carpeta de salida, dónde se guardan preferencias/cuentas).

CARPETA es la carpeta de DATOS del usuario (ver core/rutas_datos.py): con
el sistema de actualizaciones el código cambia de carpeta en cada versión,
pero los datos se quedan siempre en el mismo lugar."""

import sys
from pathlib import Path

from core.rutas_datos import carpeta_datos

CARPETA = carpeta_datos()
PLANTILLA_DEFAULT = CARPETA / "plantilla.jpeg"
PREFERENCIAS_PATH = CARPETA / ".constancias_preferencias.json"
CUENTAS_CORREO_PATH = CARPETA / ".constancias_cuentas_correo.json"


def carpeta_documentos_inicial() -> str:
    """Punto de partida razonable para los buscadores de archivo la primera vez."""
    for candidata in (Path.home() / "Documentos", Path.home() / "Documents", Path.home() / "Descargas",
                      Path.home() / "Downloads", Path.home()):
        if candidata.exists():
            return str(candidata)
    return str(Path.home())


# Como .exe la carpeta de datos queda escondida en AppData, así que los PDFs
# se guardan mejor en Documentos. Ejecutando desde el código, igual que antes.
if getattr(sys, "frozen", False):
    SALIDA_DEFAULT = Path(carpeta_documentos_inicial()) / "Constancias UAdeO" / "salida"
else:
    SALIDA_DEFAULT = CARPETA / "salida"
