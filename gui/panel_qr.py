"""
PanelQRMixin: todo lo específico del modo "Códigos QR" — construcción
del panel, selección de carpeta de QRs o archivo individual, plantilla,
posición del recuadro del QR, y la generación en sí (hilo aparte que
llama a core.procesar_carpeta_qrs / core.colocar_qr_en_plantilla).

Se combina con ComunesMixin y PanelConstanciasMixin en gui.app.ConstanciasGUI.
"""

from __future__ import annotations

import threading
import traceback
from pathlib import Path

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image

from core import (
    ConfigQR, procesar_carpeta_qrs, colocar_qr_en_plantilla,
    analizar_plantilla_qr, guardar_caja_qr_manual, eliminar_caja_qr_manual,
    EXTENSIONES_IMAGEN_QR,
)
from .dnd import DND_DISPONIBLE
from .dialogos import MarcadorCajaDialog
from .estilos import VERDE_OSCURO


class PanelQRMixin:
    # ---- Sub-panel: modo Códigos QR ----
    def _construir_panel_qr(self, card):
        # ---- Origen de los QR: carpeta (varios) o un solo archivo ----
        fila_origen = ttk.Frame(card, style="Card.TFrame")
        fila_origen.pack(fill="x", pady=(0, 8))
        ttk.Label(fila_origen, text="Origen de los QR:", style="Card.TLabel", width=16).pack(side="left")
        ttk.Radiobutton(
            fila_origen, text="Carpeta (varios)", variable=self.qr_origen_var, value="carpeta",
            command=self._cambiar_origen_qr,
        ).pack(side="left", padx=(0, 12))
        ttk.Radiobutton(
            fila_origen, text="Un solo archivo", variable=self.qr_origen_var, value="archivo",
            command=self._cambiar_origen_qr,
        ).pack(side="left")

        # Carpeta con QRs (modo "varios")
        self.fila_carpeta_qrs = ttk.Frame(card, style="Card.TFrame")
        self.fila_carpeta_qrs.pack(fill="x", pady=4)
        ttk.Label(self.fila_carpeta_qrs, text="Carpeta con QRs:", style="Card.TLabel", width=16).pack(side="left")
        self.carpeta_qrs_var = tk.StringVar(value="(sin seleccionar)")
        ttk.Label(self.fila_carpeta_qrs, textvariable=self.carpeta_qrs_var, style="Card.TLabel",
                  foreground=VERDE_OSCURO).pack(side="left", fill="x", expand=True)
        ttk.Button(self.fila_carpeta_qrs, text="Examinar…", style="Secondary.TButton",
                   command=self._elegir_carpeta_qrs).pack(side="right")

        # Un solo archivo QR (modo "individual")
        self.fila_archivo_qr = ttk.Frame(card, style="Card.TFrame")
        ttk.Label(self.fila_archivo_qr, text="Archivo QR:", style="Card.TLabel", width=16).pack(side="left")
        self.archivo_qr_var = tk.StringVar(value="(sin seleccionar)")
        ttk.Label(self.fila_archivo_qr, textvariable=self.archivo_qr_var, style="Card.TLabel",
                  foreground=VERDE_OSCURO).pack(side="left", fill="x", expand=True)
        ttk.Button(self.fila_archivo_qr, text="Examinar…", style="Secondary.TButton",
                   command=self._elegir_archivo_qr_individual).pack(side="right")

        # Plantilla del QR
        fila2 = ttk.Frame(card, style="Card.TFrame")
        fila2.pack(fill="x", pady=4)
        self.fila_plantilla_qr = fila2
        ttk.Label(fila2, text="Plantilla imagen:", style="Card.TLabel", width=16).pack(side="left")
        self.plantilla_qr_var = tk.StringVar(value="(sin seleccionar)")
        ttk.Label(fila2, textvariable=self.plantilla_qr_var, style="Card.TLabel",
                  foreground=VERDE_OSCURO).pack(side="left", fill="x", expand=True)
        ttk.Button(fila2, text="Examinar…", style="Secondary.TButton",
                   command=self._elegir_plantilla_qr).pack(side="right")

        self.nota_qr_var = tk.StringVar()
        ttk.Label(
            card, textvariable=self.nota_qr_var,
            style="Card.TLabel", foreground="#8A8272", font=("Liberation Serif", 9, "italic"),
            wraplength=520, justify="left",
        ).pack(anchor="w", pady=(6, 0))

        ttk.Label(
            card,
            text=("Arrastra aquí la carpeta de QRs, la imagen del QR, o la plantilla "
                  "(a cualquier parte de este panel), desde tu explorador de archivos."
                  if DND_DISPONIBLE else
                  "Tip: instala \"tkinterdnd2\" (pip install tkinterdnd2) para poder arrastrar "
                  "archivos aquí en vez de usar \"Examinar…\"."),
            style="Card.TLabel", foreground="#8A8272", font=("Liberation Serif", 9, "italic"),
            wraplength=520, justify="left",
        ).pack(anchor="w", pady=(2, 0))

        self._cambiar_origen_qr()

        sep2 = ttk.Separator(card)
        sep2.pack(fill="x", pady=10)

        # ---- Posición del QR sobre la plantilla ----
        fila_pos = ttk.Frame(card, style="Card.TFrame")
        fila_pos.pack(fill="x", pady=4)
        ttk.Label(fila_pos, text="Posición del QR:", style="Card.TLabel", width=18).pack(side="left")
        self.caja_qr_estado_var = tk.StringVar(value="Sin plantilla cargada")
        ttk.Label(fila_pos, textvariable=self.caja_qr_estado_var, style="Card.TLabel",
                  foreground=VERDE_OSCURO).pack(side="left", fill="x", expand=True)

        fila_pos2 = ttk.Frame(card, style="Card.TFrame")
        fila_pos2.pack(fill="x", pady=(0, 4))
        ttk.Label(fila_pos2, text="", width=18).pack(side="left")
        ttk.Button(
            fila_pos2, text="Marcar recuadro manualmente", style="Secondary.TButton",
            command=self._abrir_marcador_caja_qr,
        ).pack(side="left")
        ttk.Button(
            fila_pos2, text="Volver a automático", style="Secondary.TButton",
            command=self._quitar_marca_manual_qr,
        ).pack(side="left", padx=8)

        ttk.Label(
            card,
            text=("El QR se acomoda solo dentro del recuadro claro que detectamos en la plantilla "
                  "(como el cuadro a cuadros donde va la foto/QR). Si en la vista previa se ve mal "
                  "ubicado, usa \"Marcar recuadro manualmente\" (esquina superior izquierda y luego "
                  "inferior derecha)."),
            style="Card.TLabel", foreground="#8A8272", font=("Liberation Serif", 9, "italic"),
            wraplength=520, justify="left",
        ).pack(anchor="w", pady=(2, 0))

    def _cambiar_origen_qr(self):
        if self.qr_origen_var.get() == "carpeta":
            self.fila_archivo_qr.pack_forget()
            self.fila_carpeta_qrs.pack(fill="x", pady=4, before=self.fila_plantilla_qr)
            self.nota_qr_var.set(
                "Cada imagen de la carpeta debe estar ya nombrada por persona "
                "(ej. Juan_Perez_214.png); ese mismo nombre se usa para la imagen "
                "PNG de salida (además se arma un QRs_TODOS.pdf con todas juntas, "
                "por si quieres mandarlas a imprimir de un jalón). Usa este modo "
                "cuando tengas MUCHOS códigos QR que procesar de un jalón."
            )
        else:
            self.fila_carpeta_qrs.pack_forget()
            self.fila_archivo_qr.pack(fill="x", pady=4, before=self.fila_plantilla_qr)
            self.nota_qr_var.set(
                "Elige un solo archivo de imagen QR (no hace falta una carpeta). "
                "Se genera una sola imagen PNG con ese QR ya colocado en la plantilla, "
                "con el mismo nombre del archivo original."
            )
        self._refrescar_preview_qr()

    # ------------------------------------------------------------------
    # Selección manual de archivos
    # ------------------------------------------------------------------
    def _elegir_carpeta_qrs(self):
        self._traer_al_frente()
        ruta = filedialog.askdirectory(
            parent=self,
            title="Selecciona la carpeta con los códigos QR",
            initialdir=self._ultimo_dir_qrs,
        )
        if not ruta:
            return
        self.carpeta_qrs_path = Path(ruta)
        self.carpeta_qrs_var.set(self.carpeta_qrs_path.name)
        self._ultimo_dir_qrs = str(self.carpeta_qrs_path)
        self._guardar_preferencias()
        n = len([p for p in self.carpeta_qrs_path.iterdir()
                 if p.suffix.lower() in EXTENSIONES_IMAGEN_QR])
        self._log(f"Carpeta de QRs cargada: {self.carpeta_qrs_path.name} — {n} imagen(es) encontradas.")
        self._refrescar_preview_qr()

    def _elegir_archivo_qr_individual(self):
        self._traer_al_frente()
        ruta = filedialog.askopenfilename(
            parent=self,
            title="Selecciona la imagen del código QR",
            initialdir=self._ultimo_dir_qrs,
            filetypes=[("Imágenes", "*.png *.jpg *.jpeg *.webp *.bmp"), ("Todos los archivos", "*.*")],
        )
        if not ruta:
            return
        self.qr_archivo_individual_path = Path(ruta)
        self.archivo_qr_var.set(self.qr_archivo_individual_path.name)
        self._ultimo_dir_qrs = str(self.qr_archivo_individual_path.parent)
        self._guardar_preferencias()
        self._log(f"QR individual cargado: {self.qr_archivo_individual_path.name}")
        self._refrescar_preview_qr()

    def _elegir_plantilla_qr(self):
        self._traer_al_frente()
        ruta = filedialog.askopenfilename(
            parent=self,
            title="Selecciona la imagen de la plantilla",
            initialdir=self._ultimo_dir_plantilla_qr,
            filetypes=[("Imágenes", "*.jpg *.jpeg *.png"), ("Todos los archivos", "*.*")],
        )
        if not ruta:
            return
        self.plantilla_qr_path = Path(ruta)
        self.plantilla_qr_var.set(self.plantilla_qr_path.name)
        self._ultimo_dir_plantilla_qr = str(self.plantilla_qr_path.parent)
        self._guardar_preferencias()
        self._refrescar_preview_plantilla_qr()
        self._refrescar_preview_qr()

    # ------------------------------------------------------------------
    # Arrastrar y soltar (carpeta / archivo / plantilla del QR)
    # ------------------------------------------------------------------
    def _al_soltar_plantilla_qr(self, ruta: str):
        p = Path(ruta)
        if p.suffix.lower() not in (".jpg", ".jpeg", ".png"):
            messagebox.showwarning("Archivo no válido", f"Eso no es una imagen (.jpg/.png):\n{p.name}")
            return
        self.plantilla_qr_path = p
        self.plantilla_qr_var.set(p.name)
        self._ultimo_dir_plantilla_qr = str(p.parent)
        self._guardar_preferencias()
        self._refrescar_preview_plantilla_qr()
        self._refrescar_preview_qr()

    def _al_soltar_qr_origen(self, ruta: str):
        """Se usa al soltar sobre la carpeta o el archivo QR: detecta solo
        si soltaste una carpeta o un archivo, y cambia de modo si hace falta."""
        p = Path(ruta)
        if p.is_dir():
            self.qr_origen_var.set("carpeta")
            self._cambiar_origen_qr()
            self.carpeta_qrs_path = p
            self.carpeta_qrs_var.set(p.name)
            self._ultimo_dir_qrs = str(p)
            self._guardar_preferencias()
            n = len([f for f in p.iterdir() if f.suffix.lower() in EXTENSIONES_IMAGEN_QR])
            self._log(f"Carpeta de QRs cargada (arrastrada): {p.name} — {n} imagen(es) encontradas.")
            self._refrescar_preview_qr()
        elif p.suffix.lower() in EXTENSIONES_IMAGEN_QR:
            self.qr_origen_var.set("archivo")
            self._cambiar_origen_qr()
            self.qr_archivo_individual_path = p
            self.archivo_qr_var.set(p.name)
            self._ultimo_dir_qrs = str(p.parent)
            self._guardar_preferencias()
            self._log(f"QR individual cargado (arrastrado): {p.name}")
            self._refrescar_preview_qr()
        else:
            messagebox.showwarning(
                "Archivo no válido",
                f"Eso no es una carpeta ni una imagen de QR reconocida:\n{p.name}",
            )

    # ------------------------------------------------------------------
    # Vista previa — modo QR
    # ------------------------------------------------------------------
    def _refrescar_preview_plantilla_qr(self):
        if self.modo_var.get() != "qr":
            return
        if self.plantilla_qr_path and Path(self.plantilla_qr_path).exists():
            self._mostrar_preview_imagen(Image.open(self.plantilla_qr_path).convert("RGB"))
        else:
            self.preview_label.configure(image="", text="(sin plantilla)")
        self._actualizar_estado_caja_qr()

    def _actualizar_estado_caja_qr(self):
        if not self.plantilla_qr_path or not Path(self.plantilla_qr_path).exists():
            self.caja_qr_estado_var.set("Sin plantilla cargada")
            self._info_caja_qr = None
            return
        try:
            info = analizar_plantilla_qr(Path(self.plantilla_qr_path))
        except Exception as e:
            self.caja_qr_estado_var.set(f"No se pudo analizar la plantilla ({e})")
            self._info_caja_qr = None
            return

        self._info_caja_qr = info
        origen = info["origen"]
        if origen == "manual":
            self.caja_qr_estado_var.set("Marcado manualmente por ti")
        elif origen == "auto":
            self.caja_qr_estado_var.set("Detectado automáticamente")
        else:
            self.caja_qr_estado_var.set("No se detectó el recuadro — usando posición aproximada")

    def _quitar_marca_manual_qr(self):
        if not self.plantilla_qr_path or not Path(self.plantilla_qr_path).exists():
            return
        eliminar_caja_qr_manual(Path(self.plantilla_qr_path))
        self._log("Se quitó la marca manual del recuadro; ahora se usará la detección automática.")
        self._actualizar_estado_caja_qr()
        self._refrescar_preview_qr()

    def _abrir_marcador_caja_qr(self):
        if not self.plantilla_qr_path or not Path(self.plantilla_qr_path).exists():
            messagebox.showwarning("Falta la plantilla", "Primero selecciona la imagen de la plantilla.")
            return
        MarcadorCajaDialog(self, Path(self.plantilla_qr_path), self._info_caja_qr,
                            on_guardado=self._al_guardar_marca_manual_qr)

    def _al_guardar_marca_manual_qr(self):
        self._log("Recuadro marcado manualmente y guardado para esta plantilla.")
        self._actualizar_estado_caja_qr()
        self._refrescar_preview_qr()

    def _refrescar_preview_qr(self):
        if self.modo_var.get() != "qr":
            return
        if not self.plantilla_qr_path:
            return
        try:
            if self.qr_origen_var.get() == "archivo":
                if not self.qr_archivo_individual_path:
                    return
                qr_muestra = self.qr_archivo_individual_path
            else:
                if not self.carpeta_qrs_path:
                    return
                archivos = sorted(
                    [p for p in self.carpeta_qrs_path.iterdir() if p.suffix.lower() in EXTENSIONES_IMAGEN_QR]
                )
                if not archivos:
                    return
                qr_muestra = archivos[0]
            config = ConfigQR(plantilla=Path(self.plantilla_qr_path))
            im = colocar_qr_en_plantilla(config, qr_muestra)
            self._mostrar_preview_imagen(im)
        except Exception:
            pass  # la vista previa es solo cosmética, no debe interrumpir al usuario

    # ------------------------------------------------------------------
    # Generación
    # ------------------------------------------------------------------
    def _iniciar_generacion_qr(self):
        modo_origen = self.qr_origen_var.get()
        if modo_origen == "carpeta":
            if not self.carpeta_qrs_path or not self.carpeta_qrs_path.exists():
                messagebox.showwarning("Falta la carpeta", "Primero selecciona la carpeta con tus códigos QR.")
                return
        else:
            if not self.qr_archivo_individual_path or not self.qr_archivo_individual_path.exists():
                messagebox.showwarning("Falta el archivo", "Primero selecciona la imagen del código QR.")
                return
        if not self.plantilla_qr_path or not Path(self.plantilla_qr_path).exists():
            messagebox.showwarning("Falta la plantilla", "Selecciona la imagen de la plantilla.")
            return

        self._preparar_ui_generando("Generando QRs…")
        hilo = threading.Thread(target=self._trabajo_generacion_qr, args=(modo_origen,), daemon=True)
        hilo.start()

    def _trabajo_generacion_qr(self, modo_origen: str = "carpeta"):
        try:
            config = ConfigQR(plantilla=Path(self.plantilla_qr_path))

            def on_progreso(i, total, nombre):
                self._cola.put(("progreso", i, total, nombre))

            if modo_origen == "archivo":
                # Un solo QR: no hace falta recorrer carpeta ni armar PDF combinado.
                qr_path = Path(self.qr_archivo_individual_path)
                on_progreso(1, 1, qr_path.stem)
                im = colocar_qr_en_plantilla(config, qr_path)
                carpeta_salida = Path(self.salida_path)
                carpeta_salida.mkdir(parents=True, exist_ok=True)
                ruta_salida = carpeta_salida / f"{qr_path.stem}.png"
                im.save(ruta_salida, "PNG")
                generados = [ruta_salida]
            else:
                generados = procesar_carpeta_qrs(
                    config,
                    carpeta_qrs=Path(self.carpeta_qrs_path),
                    carpeta_salida=Path(self.salida_path),
                    on_progreso=on_progreso,
                )
            self._cola.put(("listo", generados, "QRs", modo_origen == "carpeta"))
        except Exception as e:
            self._cola.put(("error", str(e), traceback.format_exc()))
