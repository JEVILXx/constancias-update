"""
ComunesMixin: todo lo que no pertenece específicamente al panel de
Constancias ni al de QR — estilos, armado del layout general, la cola
de progreso que conecta el hilo de generación con la ventana, el
soporte de arrastrar-y-soltar, y utilidades compartidas (preferencias,
carpeta de salida, vista previa, log).

Se combina con PanelConstanciasMixin y PanelQRMixin en gui.app.ConstanciasGUI.
"""

from __future__ import annotations

import json
import queue
import subprocess
import sys
from pathlib import Path

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from .dnd import DND_DISPONIBLE, DND_FILES, parsear_rutas_dnd, parece_codigo_qr
from .estilos import GRANATE, GRANATE_OSCURO, VERDE, VERDE_OSCURO, CREMA, GRIS_TEXTO, BLANCO, BORDE
from .rutas import PREFERENCIAS_PATH


class ComunesMixin:
    # ------------------------------------------------------------------
    # Estilos
    # ------------------------------------------------------------------
    def _construir_estilos(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure("TFrame", background=CREMA)
        style.configure("Card.TFrame", background=BLANCO, relief="flat")
        style.configure("Header.TFrame", background=GRANATE)

        style.configure("TLabel", background=CREMA, foreground=GRIS_TEXTO, font=("Liberation Serif", 11))
        style.configure("Card.TLabel", background=BLANCO, foreground=GRIS_TEXTO, font=("Liberation Serif", 11))
        style.configure("Card.TCheckbutton", background=BLANCO, foreground=GRIS_TEXTO,
                         font=("Liberation Serif", 10))
        style.configure("CardTitle.TLabel", background=BLANCO, foreground=VERDE_OSCURO,
                         font=("Liberation Serif", 13, "bold"))
        style.configure("Header.TLabel", background=GRANATE, foreground=BLANCO,
                         font=("Liberation Serif", 20, "bold"))
        style.configure("HeaderSub.TLabel", background=GRANATE, foreground="#F3D9DC",
                         font=("Liberation Serif", 11))
        style.configure("Status.TLabel", background=VERDE_OSCURO, foreground=BLANCO,
                         font=("Liberation Serif", 10))

        style.configure("Accent.TButton", font=("Liberation Serif", 12, "bold"),
                         foreground=BLANCO, background=VERDE, padding=10, borderwidth=0)
        style.map("Accent.TButton", background=[("active", VERDE_OSCURO), ("disabled", "#9BB3A8")])

        style.configure("Secondary.TButton", font=("Liberation Serif", 10),
                         foreground=VERDE_OSCURO, background="#EDE7D6", padding=8, borderwidth=0)
        style.map("Secondary.TButton", background=[("active", BORDE)])

        style.configure("Modo.TRadiobutton", background=CREMA, foreground=GRIS_TEXTO,
                         font=("Liberation Serif", 11, "bold"))

        style.configure("TEntry", padding=6)
        style.configure("TCombobox", padding=6)

        style.configure("Horizontal.TProgressbar", troughcolor="#EDE7D6", background=GRANATE,
                         bordercolor=CREMA, lightcolor=GRANATE, darkcolor=GRANATE)

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------
    def _construir_layout(self):
        # ---- Encabezado ----
        header = ttk.Frame(self, style="Header.TFrame")
        header.pack(fill="x")
        ttk.Label(header, text="Generador de Constancias y QR", style="Header.TLabel").pack(
            anchor="w", padx=24, pady=(18, 0)
        )
        ttk.Label(
            header,
            text="Universidad Autónoma de Occidente · Unidad Regional Mazatlán",
            style="HeaderSub.TLabel",
        ).pack(anchor="w", padx=24, pady=(0, 12))

        # ---- Selector de modo ----
        modo_frame = ttk.Frame(header, style="Header.TFrame")
        modo_frame.pack(anchor="w", padx=24, pady=(0, 16))
        tk.Radiobutton(
            modo_frame, text="Constancias (Excel)", variable=self.modo_var, value="constancias",
            command=self._aplicar_modo, indicatoron=False, selectcolor=VERDE_OSCURO,
            bg=GRANATE, fg=BLANCO, activebackground=VERDE_OSCURO, activeforeground=BLANCO,
            font=("Liberation Serif", 11, "bold"), relief="flat", padx=14, pady=6, cursor="hand2",
        ).pack(side="left", padx=(0, 8))
        tk.Radiobutton(
            modo_frame, text="Códigos QR (carpeta)", variable=self.modo_var, value="qr",
            command=self._aplicar_modo, indicatoron=False, selectcolor=VERDE_OSCURO,
            bg=GRANATE, fg=BLANCO, activebackground=VERDE_OSCURO, activeforeground=BLANCO,
            font=("Liberation Serif", 11, "bold"), relief="flat", padx=14, pady=6, cursor="hand2",
        ).pack(side="left")

        # Versión + botón "Buscar actualizaciones" (esquina superior derecha)
        if hasattr(self, "_construir_barra_actualizaciones"):
            self._construir_barra_actualizaciones(header)

        # ---- Cuerpo: dos columnas ----
        cuerpo = ttk.Frame(self)
        cuerpo.pack(fill="both", expand=True, padx=20, pady=16)
        cuerpo.columnconfigure(0, weight=3)
        cuerpo.columnconfigure(1, weight=2)
        cuerpo.rowconfigure(0, weight=1)

        # La columna izquierda va dentro de un canvas con scroll, así el
        # contenido siempre se puede ver completo sin importar el tamaño
        # de la ventana o de la pantalla del usuario.
        izquierda_contenedor = ttk.Frame(cuerpo)
        izquierda_contenedor.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        izquierda_contenedor.rowconfigure(0, weight=1)
        izquierda_contenedor.columnconfigure(0, weight=1)

        izquierda_canvas = tk.Canvas(izquierda_contenedor, bg=CREMA, highlightthickness=0)
        izquierda_canvas.grid(row=0, column=0, sticky="nsew")
        izquierda_scroll = ttk.Scrollbar(izquierda_contenedor, orient="vertical", command=izquierda_canvas.yview)
        izquierda_scroll.grid(row=0, column=1, sticky="ns")
        izquierda_canvas.configure(yscrollcommand=izquierda_scroll.set)

        izquierda = ttk.Frame(izquierda_canvas)
        _id_ventana_izq = izquierda_canvas.create_window((0, 0), window=izquierda, anchor="nw")

        def _al_cambiar_tamano_contenido(event):
            izquierda_canvas.configure(scrollregion=izquierda_canvas.bbox("all"))

        def _al_cambiar_ancho_canvas(event):
            izquierda_canvas.itemconfigure(_id_ventana_izq, width=event.width)

        izquierda.bind("<Configure>", _al_cambiar_tamano_contenido)
        izquierda_canvas.bind("<Configure>", _al_cambiar_ancho_canvas)

        def _al_rueda_mouse(event):
            delta = -1 * (event.delta // 120) if event.delta else (1 if event.num == 5 else -1)
            izquierda_canvas.yview_scroll(int(delta), "units")

        izquierda_canvas.bind_all("<MouseWheel>", _al_rueda_mouse)   # Windows/Mac
        izquierda_canvas.bind_all("<Button-4>", _al_rueda_mouse)     # Linux, scroll arriba
        izquierda_canvas.bind_all("<Button-5>", _al_rueda_mouse)     # Linux, scroll abajo

        derecha = ttk.Frame(cuerpo)
        derecha.grid(row=0, column=1, sticky="nsew")

        self._construir_panel_datos(izquierda)
        self._construir_panel_consola(izquierda)
        self._construir_panel_preview(derecha)

        # Un solo punto de "soltar archivo": cualquier parte del panel
        # izquierdo (Excel, plantilla, QR, carpeta, consola...) acepta que
        # arrastres un archivo/carpeta y el programa adivina qué es.
        self._activar_drop_recursivo(izquierda, self._al_soltar_inteligente)

        # ---- Barra de estado ----
        self.status_var = tk.StringVar(value="Listo. Selecciona tu Excel para comenzar.")
        barra = tk.Label(self, textvariable=self.status_var, bg=VERDE_OSCURO, fg=BLANCO,
                          font=("Liberation Serif", 10), anchor="w", padx=14, pady=6)
        barra.pack(fill="x", side="bottom")

    def _tarjeta(self, parent, titulo) -> ttk.Frame:
        contenedor = tk.Frame(parent, bg=BORDE)
        contenedor.pack(fill="x", pady=(0, 14))
        interior = ttk.Frame(contenedor, style="Card.TFrame", padding=16)
        interior.pack(fill="both", expand=True, padx=1, pady=1)
        ttk.Label(interior, text=titulo, style="CardTitle.TLabel").pack(anchor="w", pady=(0, 10))
        return interior

    # ---- Panel de datos (archivo, columnas, salida) ----
    def _construir_panel_datos(self, parent):
        self.card_datos = self._tarjeta(parent, "1. Datos de entrada")

        # Carpeta salida (compartida entre los dos modos)
        fila_salida = ttk.Frame(self.card_datos, style="Card.TFrame")
        fila_salida.pack(fill="x", pady=4)
        ttk.Label(fila_salida, text="Carpeta de salida:", style="Card.TLabel", width=16).pack(side="left")
        self.salida_var = tk.StringVar(value=str(self.salida_path))
        ttk.Label(fila_salida, textvariable=self.salida_var, style="Card.TLabel",
                  foreground=VERDE_OSCURO).pack(side="left", fill="x", expand=True)
        ttk.Button(fila_salida, text="Cambiar…", style="Secondary.TButton",
                   command=self._elegir_salida).pack(side="right")

        sep_top = ttk.Separator(self.card_datos)
        sep_top.pack(fill="x", pady=10)

        # Contenedor donde se intercambia el panel según el modo
        self.subpanel_datos = ttk.Frame(self.card_datos, style="Card.TFrame")
        self.subpanel_datos.pack(fill="x")

        self.panel_constancias = ttk.Frame(self.subpanel_datos, style="Card.TFrame")
        self.panel_qr = ttk.Frame(self.subpanel_datos, style="Card.TFrame")
        self._construir_panel_constancias(self.panel_constancias)
        self._construir_panel_qr(self.panel_qr)

        # Botones de acción (compartidos; el comando de "Generar" cambia según el modo)
        acciones = ttk.Frame(self.card_datos, style="Card.TFrame")
        acciones.pack(fill="x", pady=(16, 0))
        self.btn_generar = ttk.Button(acciones, text="Generar", style="Accent.TButton",
                                       command=self._iniciar_generacion)
        self.btn_generar.pack(side="left")
        ttk.Button(acciones, text="Abrir carpeta de salida", style="Secondary.TButton",
                   command=self._abrir_salida).pack(side="left", padx=10)

        self.progreso = ttk.Progressbar(self.card_datos, mode="determinate", style="Horizontal.TProgressbar")
        self.progreso.pack(fill="x", pady=(14, 0))

    # ---- Panel de consola / log ----
    def _construir_panel_consola(self, parent):
        card = self._tarjeta(parent, "2. Progreso")
        self.log_text = tk.Text(card, height=10, bg="#FBFAF5", fg=GRIS_TEXTO, relief="flat",
                                 font=("Consolas", 10), wrap="word", state="disabled")
        self.log_text.pack(fill="both", expand=True)
        scroll = ttk.Scrollbar(self.log_text, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scroll.set)

    # ---- Panel de vista previa ----
    def _construir_panel_preview(self, parent):
        card = self._tarjeta(parent, "Vista previa")
        self.preview_label = tk.Label(card, bg=BLANCO)
        self.preview_label.pack(fill="both", expand=True)
        self.preview_nota_var = tk.StringVar(value="Se actualiza con el primer registro de tu Excel.")
        ttk.Label(card, textvariable=self.preview_nota_var,
                  style="Card.TLabel", foreground="#8A8272",
                  font=("Liberation Serif", 9, "italic")).pack(anchor="w", pady=(8, 0))
        self._preview_imgtk = None  # referencia para que no la borre el garbage collector

    def _mostrar_preview_imagen(self, im):
        from PIL import ImageTk
        ancho_max = 380
        ratio = ancho_max / im.width
        im_reducida = im.resize((ancho_max, int(im.height * ratio)))
        self._preview_imgtk = ImageTk.PhotoImage(im_reducida)
        self.preview_label.configure(image=self._preview_imgtk, text="")

    # ------------------------------------------------------------------
    # Cambio de modo (Constancias <-> QR)
    # ------------------------------------------------------------------
    def _aplicar_modo(self):
        modo = self.modo_var.get()
        if modo == "constancias":
            self.panel_qr.pack_forget()
            self.panel_constancias.pack(fill="x")
            self.btn_generar.configure(text="Generar constancias")
            self.preview_nota_var.set("Se actualiza con el primer registro de tu Excel.")
            self._refrescar_preview_plantilla()
            self.status_var.set("Modo Constancias. Selecciona tu Excel para comenzar.")
        else:
            self.panel_constancias.pack_forget()
            self.panel_qr.pack(fill="x")
            self.btn_generar.configure(text="Generar QRs")
            self.preview_nota_var.set("Se actualiza con el primer QR de la carpeta.")
            self._refrescar_preview_plantilla_qr()
            self.status_var.set("Modo Códigos QR. Selecciona la carpeta con tus QRs.")

    # ------------------------------------------------------------------
    # Preferencias (recuerda la última carpeta usada entre sesiones)
    # ------------------------------------------------------------------
    def _cargar_preferencias(self):
        if not PREFERENCIAS_PATH.exists():
            return
        try:
            datos = json.loads(PREFERENCIAS_PATH.read_text(encoding="utf-8"))
            for clave, atributo in (
                ("dir_datos", "_ultimo_dir_datos"),
                ("dir_plantilla", "_ultimo_dir_plantilla"),
                ("dir_plantilla_qr", "_ultimo_dir_plantilla_qr"),
                ("dir_qrs", "_ultimo_dir_qrs"),
                ("dir_salida", "_ultimo_dir_salida"),
            ):
                valor = datos.get(clave)
                if valor and Path(valor).exists():
                    setattr(self, atributo, valor)
            self.modo_mensaje_var.set(datos.get("modo_mensaje", "automatico"))
            self.asunto_personalizado_var.set(datos.get("asunto_personalizado", ""))
            self._cuerpo_personalizado_inicial = datos.get("cuerpo_personalizado", "")
        except Exception:
            pass  # si el archivo está corrupto, simplemente usamos los valores por defecto

    def _guardar_preferencias(self):
        try:
            cuerpo_personalizado = ""
            if hasattr(self, "texto_cuerpo_personalizado"):
                cuerpo_personalizado = self.texto_cuerpo_personalizado.get("1.0", "end").strip()
            PREFERENCIAS_PATH.write_text(
                json.dumps({
                    "dir_datos": self._ultimo_dir_datos,
                    "dir_plantilla": self._ultimo_dir_plantilla,
                    "dir_plantilla_qr": self._ultimo_dir_plantilla_qr,
                    "dir_qrs": self._ultimo_dir_qrs,
                    "dir_salida": self._ultimo_dir_salida,
                    "modo_mensaje": self.modo_mensaje_var.get(),
                    "asunto_personalizado": self.asunto_personalizado_var.get(),
                    "cuerpo_personalizado": cuerpo_personalizado,
                }, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass  # guardar la preferencia es un extra, no debe interrumpir el uso normal

    # ------------------------------------------------------------------
    # Acciones de archivos compartidas
    # ------------------------------------------------------------------
    def _traer_al_frente(self):
        """Asegura que la ventana (y por lo tanto el buscador de archivos) tenga el foco."""
        self.lift()
        self.attributes("-topmost", True)
        self.after_idle(lambda: self.attributes("-topmost", False))
        self.update_idletasks()

    def _elegir_salida(self):
        self._traer_al_frente()
        ruta = filedialog.askdirectory(
            parent=self,
            title="Selecciona la carpeta de salida",
            initialdir=self._ultimo_dir_salida,
        )
        if not ruta:
            return
        self.salida_path = Path(ruta)
        self.salida_var.set(str(self.salida_path))
        self._ultimo_dir_salida = str(self.salida_path)
        self._guardar_preferencias()

    def _abrir_salida(self):
        self.salida_path.mkdir(parents=True, exist_ok=True)
        try:
            if sys.platform.startswith("linux"):
                subprocess.Popen(["xdg-open", str(self.salida_path)])
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(self.salida_path)])
            else:
                import os
                os.startfile(str(self.salida_path))  # type: ignore
        except Exception as e:
            messagebox.showwarning("No se pudo abrir", f"No pude abrir la carpeta automáticamente:\n{e}")

    # ------------------------------------------------------------------
    # Arrastrar y soltar (drag & drop)
    # ------------------------------------------------------------------
    def _activar_drop(self, widget, on_soltar):
        """
        Convierte 'widget' en zona donde se puede soltar un archivo o
        carpeta arrastrado desde el explorador de archivos. on_soltar(ruta)
        se llama con la primera ruta soltada (str). No hace nada si
        tkinterdnd2 no está instalado (el programa sigue funcionando
        normal, solo sin esta comodidad).
        """
        if not DND_DISPONIBLE:
            return
        try:
            widget.drop_target_register(DND_FILES)
            widget.dnd_bind("<<Drop>>", lambda event: on_soltar(parsear_rutas_dnd(event.data)[0]))
        except tk.TclError:
            pass

    def _activar_drop_recursivo(self, widget, on_soltar):
        """Activa el drop en 'widget' y en TODOS sus descendientes (sin
        importar qué tan anidados estén), para que soltar en cualquier
        parte de esa zona funcione igual."""
        self._activar_drop(widget, on_soltar)
        for hijo in widget.winfo_children():
            self._activar_drop_recursivo(hijo, on_soltar)

    def _al_soltar_inteligente(self, ruta: str):
        """
        Punto de entrada único para soltar CUALQUIER archivo/carpeta en
        cualquier parte del panel izquierdo: adivina de qué se trata según
        el modo activo (Constancias/QR) y qué tipo de archivo es, y lo
        manda al lugar correcto — no hace falta soltar sobre un renglón
        específico.
        """
        p = Path(ruta)
        extension = p.suffix.lower()
        es_imagen = extension in (".jpg", ".jpeg", ".png")

        if self.modo_var.get() == "constancias":
            if extension in (".xlsx", ".xls"):
                self._al_soltar_excel(ruta)
            elif es_imagen:
                self._al_soltar_plantilla(ruta)
            elif p.is_dir():
                messagebox.showinfo(
                    "Eso es una carpeta",
                    "En modo Constancias no se usan carpetas. Si quieres soltar una carpeta "
                    "de códigos QR, cambia primero al modo \"Códigos QR\".",
                )
            else:
                messagebox.showwarning(
                    "No reconocido",
                    f"No sé qué hacer con este archivo en modo Constancias:\n{p.name}\n\n"
                    "Esperaba un Excel (.xlsx) o una imagen (.jpg/.png) de plantilla.",
                )
            return

        # Modo QR
        if p.is_dir():
            self._al_soltar_qr_origen(ruta)
        elif es_imagen:
            if not self.plantilla_qr_path:
                # Sin plantilla todavía: lo primero que sueltes se toma como
                # la plantilla, sin importar si "parece" QR o no.
                self._al_soltar_plantilla_qr(ruta)
            elif parece_codigo_qr(p):
                self._al_soltar_qr_origen(ruta)
            else:
                self._al_soltar_plantilla_qr(ruta)
        else:
            messagebox.showwarning(
                "No reconocido",
                f"No sé qué hacer con este archivo en modo QR:\n{p.name}\n\n"
                "Esperaba una carpeta de QRs, una imagen de QR, o una imagen de plantilla.",
            )

    # ------------------------------------------------------------------
    # Generación (dispatcher + cola de progreso, en hilo aparte)
    # ------------------------------------------------------------------
    def _iniciar_generacion(self):
        if self._hilo_generando:
            return
        if self.modo_var.get() == "constancias":
            self._iniciar_generacion_constancias()
        else:
            self._iniciar_generacion_qr()

    def _preparar_ui_generando(self, mensaje: str):
        self.btn_generar.configure(state="disabled")
        self.progreso.configure(value=0)
        self._limpiar_log()
        self._log("Iniciando generación…")
        self.status_var.set(mensaje)
        self._hilo_generando = True

    def _revisar_cola(self):
        try:
            while True:
                evento = self._cola.get_nowait()
                tipo = evento[0]
                if tipo == "progreso":
                    _, i, total, nombre = evento
                    self.progreso.configure(maximum=total, value=i)
                    self._log(f"  [{i}/{total}] {nombre}")
                elif tipo == "conteo_correo":
                    _, remitente, nuevo_total = evento
                    self._actualizar_conteo_cuenta(remitente, nuevo_total)
                elif tipo == "listo":
                    _, generados, etiqueta, tiene_combinado = evento
                    n = max(len(generados) - 1, 0) if tiene_combinado else len(generados)
                    self._log(f"\nListo: {n} {etiqueta} generados.")
                    if tiene_combinado and generados:
                        self._log(f"Archivo combinado: {generados[-1]}")
                    self.status_var.set(f"Listo — {n} {etiqueta} generados en {self.salida_path}")
                    self.btn_generar.configure(state="normal")
                    self._hilo_generando = False
                    messagebox.showinfo("Listo", f"Se generaron {n} {etiqueta} en:\n{self.salida_path}")
                elif tipo == "error":
                    _, msg, tb = evento
                    self._log(f"\nERROR: {msg}")
                    self.status_var.set("Ocurrió un error. Revisa la consola de progreso.")
                    self.btn_generar.configure(state="normal")
                    self._hilo_generando = False
                    messagebox.showerror("Error al generar", msg)
        except queue.Empty:
            pass
        self.after(100, self._revisar_cola)

    # ------------------------------------------------------------------
    def _log(self, texto: str):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", texto + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _limpiar_log(self):
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")
