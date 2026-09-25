"""
Clase principal de la interfaz. Combina los tres mixins (Comunes,
Constancias, QR) sobre la ventana base (tk.Tk normal, o TkinterDnD.Tk
si "tkinterdnd2" está instalado, para poder arrastrar y soltar archivos).
"""

from __future__ import annotations

import queue
from pathlib import Path

import tkinter as tk

from .dnd import BaseVentana
from .estilos import CREMA
from .rutas import CARPETA, PLANTILLA_DEFAULT, SALIDA_DEFAULT, carpeta_documentos_inicial
from .comunes import ComunesMixin
from .panel_constancias import PanelConstanciasMixin
from .panel_qr import PanelQRMixin
from .actualizaciones import ActualizacionesMixin


class ConstanciasGUI(ComunesMixin, PanelConstanciasMixin, PanelQRMixin, ActualizacionesMixin, BaseVentana):
    def __init__(self):
        super().__init__()
        self.title("Generador de Constancias UAdeO")
        self.geometry("1080x760")
        self.minsize(920, 560)
        self.configure(bg=CREMA)

        # Estado general
        self.modo_var = tk.StringVar(value="constancias")  # "constancias" | "qr"
        self.salida_path: Path = SALIDA_DEFAULT
        self._cola: queue.Queue = queue.Queue()
        self._hilo_generando = False

        # Estado modo Constancias
        self.excel_path: Path | None = None
        self.plantilla_path: Path | None = PLANTILLA_DEFAULT if PLANTILLA_DEFAULT.exists() else None
        self.df_columnas: list[str] = []
        self._info_linea: dict | None = None

        # Envío por correo (opcional, solo modo Constancias) — varias cuentas
        self.enviar_correo_var = tk.BooleanVar(value=False)
        self.cuentas_correo: list[dict] = []       # [{alias, remitente, recordar, contrasena}]
        self._contrasenas_sesion: dict[str, str] = {}  # alias -> contraseña (solo en memoria)
        self._cargar_cuentas()

        # Mensaje del correo: automático (por defecto) o redactado por el usuario
        self.modo_mensaje_var = tk.StringVar(value="automatico")
        self.asunto_personalizado_var = tk.StringVar(value="")
        self._cuerpo_personalizado_inicial = ""  # se llena en _cargar_preferencias

        # Estado modo QR
        self.carpeta_qrs_path: Path | None = None
        self.qr_archivo_individual_path: Path | None = None
        self.qr_origen_var = tk.StringVar(value="carpeta")  # "carpeta" | "archivo"
        self.plantilla_qr_path: Path | None = None
        self._info_caja_qr: dict | None = None

        # Última carpeta usada en cada buscador (se recuerda entre sesiones)
        inicio = carpeta_documentos_inicial()
        self._ultimo_dir_datos = inicio
        self._ultimo_dir_plantilla = str(CARPETA) if PLANTILLA_DEFAULT.exists() else inicio
        self._ultimo_dir_plantilla_qr = inicio
        self._ultimo_dir_qrs = inicio
        self._ultimo_dir_salida = str(CARPETA)
        self._cargar_preferencias()

        self._construir_estilos()
        self._construir_layout()
        self._aplicar_modo()
        self.after(100, self._revisar_cola)
        self._iniciar_actualizaciones_en_segundo_plano()
