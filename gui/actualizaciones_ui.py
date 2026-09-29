"""
Parte visual del sistema de actualizaciones: el diálogo que le avisa al
usuario que hay una versión nueva, con progreso de descarga.
"""

from __future__ import annotations

import sys
import threading
import webbrowser

import tkinter as tk
from tkinter import ttk, messagebox

from core.actualizaciones import (
    buscar_actualizacion,
    descargar_actualizacion,
    aplicar_actualizacion_y_reiniciar,
    version_actual,
    ErrorActualizacion,
)
from .estilos import CREMA, VERDE_OSCURO, GRIS_TEXTO


def verificar_actualizaciones_en_segundo_plano(parent, url_manifiesto: str, silencioso: bool = True):
    """
    Revisa si hay actualización SIN congelar la ventana (lo hace en un
    hilo aparte). Si encuentra una versión más nueva, muestra el
    diálogo de aviso. Si 'silencioso' es True (revisión automática al
    abrir el programa) y no hay internet o no hay nada nuevo, no
    aparece ningún mensaje ni error — es completamente transparente.
    Si es False (el usuario le dio a "Buscar actualizaciones"), sí
    avisa cuando ya está en la última versión o si algo falla.
    """

    def _trabajo():
        info = buscar_actualizacion(url_manifiesto)
        if info:
            parent.after(0, lambda: DialogoActualizacion(parent, info))
        elif not silencioso:
            parent.after(0, lambda: messagebox.showinfo(
                "Sin actualizaciones",
                f"Ya tienes la última versión instalada (v{version_actual()}).",
            ))

    threading.Thread(target=_trabajo, daemon=True).start()


class DialogoActualizacion(tk.Toplevel):
    """Avisa que hay una versión nueva y ofrece instalarla."""

    def __init__(self, parent, info: dict):
        super().__init__(parent)
        self.info = info
        self.title("Actualización disponible")
        self.configure(bg=CREMA)
        self.transient(parent)
        self.grab_set()
        self.resizable(False, False)

        cont = ttk.Frame(self, style="TFrame", padding=18)
        cont.pack(fill="both", expand=True)

        version_nueva = info.get("version", "?")
        ttk.Label(
            cont, text=f"Hay una nueva versión disponible: v{version_nueva}",
            font=("Liberation Serif", 13, "bold"),
        ).pack(anchor="w")
        ttk.Label(
            cont, text=f"Tienes instalada la versión v{version_actual()}.",
            foreground="#8A8272",
        ).pack(anchor="w", pady=(2, 10))

        notas = info.get("notas", "").strip()
        if notas:
            ttk.Label(cont, text="Qué cambia:", font=("Liberation Serif", 10, "bold")).pack(anchor="w")
            ttk.Label(cont, text=notas, wraplength=420, justify="left").pack(anchor="w", pady=(2, 10))

        self.frame_progreso = ttk.Frame(cont, style="TFrame")
        self.status_var = tk.StringVar(value="")
        self.label_status = ttk.Label(self.frame_progreso, textvariable=self.status_var,
                                       foreground=VERDE_OSCURO)
        self.label_status.pack(anchor="w")
        self.barra = ttk.Progressbar(self.frame_progreso, mode="determinate", length=380)
        self.barra.pack(fill="x", pady=(4, 0))

        self.frame_botones = ttk.Frame(cont, style="TFrame")
        self.frame_botones.pack(fill="x", pady=(10, 0))

        self.puede_auto_actualizar = sys.platform == "win32" and getattr(sys, "frozen", False)

        if self.puede_auto_actualizar:
            ttk.Button(self.frame_botones, text="Actualizar ahora", style="Accent.TButton",
                       command=self._actualizar_ahora).pack(side="left")
        ttk.Button(
            self.frame_botones, text="Descargar manualmente", style="Secondary.TButton",
            command=self._descargar_manualmente,
        ).pack(side="left", padx=(8 if self.puede_auto_actualizar else 0, 0))
        ttk.Button(self.frame_botones, text="Más tarde", style="Secondary.TButton",
                   command=self.destroy).pack(side="right")

        if not self.puede_auto_actualizar:
            ttk.Label(
                cont,
                text=("La instalación automática solo funciona en el .exe de Windows. "
                      "Corriendo como script de Python, descarga la actualización a mano."),
                foreground="#8A8272", font=("Liberation Serif", 9, "italic"), wraplength=420, justify="left",
            ).pack(anchor="w", pady=(8, 0))

    def _descargar_manualmente(self):
        url = self.info.get("url_zip", "")
        if url:
            webbrowser.open(url)
        else:
            messagebox.showwarning("Sin enlace", "El manifiesto no trae un enlace de descarga.")

    def _actualizar_ahora(self):
        for widget in self.frame_botones.winfo_children():
            widget.configure(state="disabled")
        self.frame_progreso.pack(fill="x", pady=(4, 0))
        self.status_var.set("Descargando actualización…")
        threading.Thread(target=self._trabajo_actualizar, daemon=True).start()

    def _trabajo_actualizar(self):
        try:
            def _reportar(hecho, total):
                pct = int(hecho / total * 100) if total else 0
                self.after(0, lambda: self._actualizar_barra(pct))

            ruta_zip = descargar_actualizacion(self.info.get("url_zip", ""), on_progreso=_reportar)
            self.after(0, lambda: self.status_var.set("Instalando y reiniciando…"))
            aplicar_actualizacion_y_reiniciar(ruta_zip)
            # Si todo salió bien, aplicar_actualizacion_y_reiniciar cierra el
            # programa (os._exit) y estas líneas de abajo nunca se ejecutan.
        except ErrorActualizacion as e:
            self.after(0, lambda: self._mostrar_error(str(e)))

    def _actualizar_barra(self, porcentaje):
        self.barra.configure(value=porcentaje)
        self.status_var.set(f"Descargando actualización… {porcentaje}%")

    def _mostrar_error(self, mensaje):
        messagebox.showerror("No se pudo actualizar", mensaje)
        for widget in self.frame_botones.winfo_children():
            widget.configure(state="normal")
        self.status_var.set("")
