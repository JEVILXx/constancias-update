"""
Motor de generación de constancias y QR — dividido en módulos:

  core.fuentes         -> carga y ajuste de tipografías
  core.utils           -> nombres de archivo, orden alfabético, columnas de Excel, guardar PDF
  core.lineas          -> detección automática/manual de la línea del nombre (constancias)
  core.qr              -> ConfigQR, detección del recuadro del QR, procesar_carpeta_qrs
  core.constancias     -> Config, render_certificado, procesar_excel
  core.correo          -> CorreoConfig, CuentaEnvio, envío por SMTP con adjunto
  core.actualizaciones -> revisar/descargar/aplicar actualizaciones del .exe
  core.base_dir        -> carpeta base del programa (script normal o .exe compilado)

Este __init__ reexporta lo que usan generar_constancias.py y
constancias_gui.py, así que se puede seguir haciendo:

    from core import Config, procesar_excel, ...

sin tener que saber en qué submódulo vive cada cosa.
"""

from .base_dir import carpeta_base
from .constancias import (
    Config,
    FilaInvalidaError,
    analizar_plantilla,
    render_certificado,
    procesar_excel,
)
from .lineas import (
    guardar_linea_manual,
    eliminar_linea_manual,
    cargar_linea_manual,
    detectar_linea_horizontal,
)
from .qr import (
    ConfigQR,
    EXTENSIONES_IMAGEN_QR,
    analizar_plantilla_qr,
    colocar_qr_en_plantilla,
    procesar_carpeta_qrs,
    guardar_caja_qr_manual,
    eliminar_caja_qr_manual,
    cargar_caja_qr_manual,
    detectar_caja_qr,
)
from .correo import (
    CorreoConfig,
    CuentaEnvio,
    ErrorEnvioCorreo,
    enviar_correo_con_adjunto,
)
from .utils import (
    quitar_acentos_archivo,
    encontrar_columna,
    limpiar_matricula,
    guardar_como_pdf,
)

__all__ = [
    "carpeta_base",
    "Config", "FilaInvalidaError", "analizar_plantilla", "render_certificado", "procesar_excel",
    "guardar_linea_manual", "eliminar_linea_manual", "cargar_linea_manual", "detectar_linea_horizontal",
    "ConfigQR", "EXTENSIONES_IMAGEN_QR", "analizar_plantilla_qr", "colocar_qr_en_plantilla",
    "procesar_carpeta_qrs", "guardar_caja_qr_manual", "eliminar_caja_qr_manual",
    "cargar_caja_qr_manual", "detectar_caja_qr",
    "CorreoConfig", "CuentaEnvio", "ErrorEnvioCorreo", "enviar_correo_con_adjunto",
    "quitar_acentos_archivo", "encontrar_columna", "limpiar_matricula", "guardar_como_pdf",
]
