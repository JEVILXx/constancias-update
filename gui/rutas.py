"""Rutas y constantes de archivo que usa la interfaz (plantilla por
defecto, carpeta de salida, dónde se guardan preferencias/cuentas)."""

from pathlib import Path

from core import carpeta_base

CARPETA = carpeta_base()
PLANTILLA_DEFAULT = CARPETA / "plantilla.jpeg"
SALIDA_DEFAULT = CARPETA / "salida"
PREFERENCIAS_PATH = CARPETA / ".constancias_preferencias.json"
CUENTAS_CORREO_PATH = CARPETA / ".constancias_cuentas_correo.json"


def carpeta_documentos_inicial() -> str:
    """Punto de partida razonable para los buscadores de archivo la primera vez."""
    for candidata in (Path.home() / "Documentos", Path.home() / "Documents", Path.home() / "Descargas",
                      Path.home() / "Downloads", Path.home()):
        if candidata.exists():
            return str(candidata)
    return str(Path.home())
