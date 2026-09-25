"""
ActualizacionesMixin: indicador de versión, botón "Buscar actualizaciones"
y revisión silenciosa cada 30 minutos mientras el programa está abierto.

La descarga se hace en un hilo (la ventana nunca se congela). Cuando hay una
versión nueva ya instalada, el botón cambia a "Reiniciar para actualizar"; el
usuario decide cuándo reiniciar (nunca se cierra solo a media generación).
"""

from __future__ import annotations

import queue
import threading
from pathlib import Path

import tkinter as tk
from tkinter import messagebox

from .estilos import GRANATE, VERDE_OSCURO, BLANCO

try:
    import actualizador  # vive junto al lanzador; no se actualiza remotamente
except ImportError:  # p. ej. si alguien mueve la carpeta gui/ sin el lanzador
    actualizador = None

INTERVALO_REVISION_MS = 30 * 60 * 1000


class ActualizacionesMixin:
    # ------------------------------------------------------------------
    def _version_texto(self) -> str:
        if actualizador is not None:
            return actualizador.version_actual()
        try:
            import json
            return json.loads((Path(__file__).resolve().parent.parent / "version.json").read_text())["version"]
        except Exception:
            return "?"

    def _construir_barra_actualizaciones(self, header):
        self._act_pendiente = None
        self._act_ocupado = False
        self._act_boton = None
        marco = tk.Frame(header, bg=GRANATE)
        marco.place(relx=1.0, x=-24, y=16, anchor="ne")
        tk.Label(marco, text=f"Versión {self._version_texto()}", bg=GRANATE, fg="#F3D9DC",
                 font=("Liberation Serif", 10)).pack(anchor="e")
        if actualizador is None:
            return
        self._act_estado_lbl = tk.Label(marco, text="", bg=GRANATE, fg="#F3D9DC", font=("Liberation Serif", 9))
        self._act_estado_lbl.pack(anchor="e")
        self._act_boton = tk.Button(
            marco, text="Buscar actualizaciones", command=self._act_click, relief="flat", cursor="hand2",
            bg=VERDE_OSCURO, fg=BLANCO, activebackground="#1E4D3B", activeforeground=BLANCO,
            font=("Liberation Serif", 10, "bold"), padx=10, pady=3,
        )
        self._act_boton.pack(anchor="e", pady=(6, 0))

    def _iniciar_actualizaciones_en_segundo_plano(self):
        if actualizador is None:
            return
        self._cola_act: queue.Queue = queue.Queue()
        self.after(500, self._act_revisar_cola)
        self.after(INTERVALO_REVISION_MS, self._act_revision_periodica)

    # ------------------------------------------------------------------
    def _act_click(self):
        if self._act_pendiente:
            self._act_reiniciar()
        else:
            self._act_buscar(manual=True)

    def _act_revision_periodica(self):
        if not self._act_pendiente:
            self._act_buscar(manual=False)
        self.after(INTERVALO_REVISION_MS, self._act_revision_periodica)

    def _act_buscar(self, manual: bool):
        if self._act_ocupado:
            return
        self._act_ocupado = True
        if manual:
            self._act_boton.configure(state="disabled", text="Buscando…")
            self._act_estado_lbl.configure(text="")

        def trabajo():
            self._cola_act.put((actualizador.buscar_e_instalar(), manual))

        threading.Thread(target=trabajo, daemon=True).start()

    def _act_revisar_cola(self):
        try:
            while True:
                res, manual = self._cola_act.get_nowait()
                self._act_ocupado = False
                self._act_mostrar_resultado(res, manual)
        except queue.Empty:
            pass
        self.after(400, self._act_revisar_cola)

    def _act_mostrar_resultado(self, res: dict, manual: bool):
        estado = res.get("estado")
        self._act_boton.configure(state="normal", text="Buscar actualizaciones")
        if estado == "instalada":
            self._act_pendiente = res
            self._act_boton.configure(text=f"Reiniciar para usar v{res['version']}")
            self._act_estado_lbl.configure(text="¡Actualización lista!")
            notas = f"\n\nNovedades:\n{res['notas']}" if res.get("notas") else ""
            if messagebox.askyesno(
                "Actualización lista",
                f"Se descargó la versión {res['version']}.{notas}\n\n¿Reiniciar ahora para usarla?",
            ):
                self._act_reiniciar()
        elif manual:
            if estado == "al_dia":
                messagebox.showinfo("Actualizaciones", res["mensaje"])
            elif estado == "sin_config":
                messagebox.showinfo(
                    "Actualizaciones",
                    "Aún no se configuró de dónde descargar las actualizaciones.\n\n"
                    "Edita el archivo actualizaciones.json y pon el origen (ver LEEME).",
                )
            else:
                messagebox.showwarning("Actualizaciones", res.get("mensaje", "No se pudo actualizar."))
        elif estado == "error":
            self._act_estado_lbl.configure(text="Sin conexión para actualizar")

    def _act_reiniciar(self):
        if getattr(self, "_hilo_generando", False):
            messagebox.showinfo("Espera un momento",
                                "Se está generando algo ahora mismo. Reinicia cuando termine.")
            return
        try:
            self._guardar_preferencias()
        except Exception:
            pass
        actualizador.reiniciar()
        self.destroy()
