"""
Ventanas secundarias (Toplevel) de la interfaz:

  MarcadorLineaDialog -> marcar a mano la línea del nombre (constancias)
  MarcadorCajaDialog   -> marcar a mano el recuadro del QR
  DialogoCuenta         -> agregar una cuenta de correo remitente
"""

from __future__ import annotations

from pathlib import Path

import tkinter as tk
from tkinter import ttk, messagebox

from PIL import Image, ImageTk

from core import guardar_linea_manual, guardar_caja_qr_manual
from .estilos import CREMA, BLANCO, BORDE, GRANATE, VERDE_OSCURO


class MarcadorLineaDialog(tk.Toplevel):
    """
    Ventana para marcar a mano dónde va la línea "A: ______" en una
    plantilla, para los casos en que la detección automática no acierte.
    El usuario da dos clics sobre la imagen: inicio y final de la línea.
    """

    ANCHO_MAX = 900
    ALTO_MAX = 640

    def __init__(self, parent, plantilla_path: Path,
                 info_previa: dict | None, on_guardado):
        super().__init__(parent)
        self.title("Marcar línea del nombre")
        self.configure(bg=CREMA)
        self.transient(parent)
        self.grab_set()

        self.plantilla_path = plantilla_path
        self.on_guardado = on_guardado
        self._puntos: list[tuple[int, int]] = []  # coords en la imagen ORIGINAL
        self._id_puntos_preview: list[int] = []

        self.im_original = Image.open(plantilla_path).convert("RGB")
        ancho_o, alto_o = self.im_original.size
        self.escala = min(self.ANCHO_MAX / ancho_o, self.ALTO_MAX / alto_o, 1.0)
        ancho_c = max(1, int(ancho_o * self.escala))
        alto_c = max(1, int(alto_o * self.escala))

        im_mostrar = self.im_original.resize((ancho_c, alto_c))
        self._imgtk = ImageTk.PhotoImage(im_mostrar)

        ttk.Label(
            self,
            text="Haz clic en el INICIO de la línea (justo después de \"A:\") y luego en el FINAL de la línea.",
            style="Card.TLabel", background=CREMA, wraplength=ancho_c,
            font=("Liberation Serif", 11, "bold"),
        ).pack(padx=12, pady=(12, 6), anchor="w")

        self.canvas = tk.Canvas(self, width=ancho_c, height=alto_c,
                                 bg=BLANCO, highlightthickness=1, highlightbackground=BORDE)
        self.canvas.pack(padx=12, pady=6)
        self.canvas.create_image(0, 0, anchor="nw", image=self._imgtk)
        self.canvas.bind("<Button-1>", self._al_hacer_clic)

        # Si ya había una línea (auto o manual previa), la mostramos de entrada
        # como referencia, en gris, para que el usuario vea de dónde parte.
        if info_previa and info_previa.get("origen") in ("auto", "manual"):
            x0 = info_previa["x0"] * self.escala
            x1 = info_previa["x1"] * self.escala
            y = info_previa["y"] * self.escala
            self.canvas.create_line(x0, y, x1, y, fill="#B0A99B", width=2, dash=(4, 2))

        self.status_var = tk.StringVar(value="Esperando el primer clic (inicio de la línea)…")
        ttk.Label(self, textvariable=self.status_var, style="Card.TLabel",
                  background=CREMA, foreground=VERDE_OSCURO).pack(padx=12, anchor="w")

        botones = ttk.Frame(self, style="TFrame")
        botones.pack(fill="x", padx=12, pady=12)
        ttk.Button(botones, text="Reintentar", style="Secondary.TButton",
                   command=self._reiniciar).pack(side="left")
        ttk.Button(botones, text="Cancelar", style="Secondary.TButton",
                   command=self.destroy).pack(side="right")
        self.btn_guardar = ttk.Button(botones, text="Guardar línea", style="Accent.TButton",
                                       command=self._guardar, state="disabled")
        self.btn_guardar.pack(side="right", padx=8)

    def _al_hacer_clic(self, event):
        if len(self._puntos) >= 2:
            return
        x_orig = event.x / self.escala
        y_orig = event.y / self.escala
        self._puntos.append((x_orig, y_orig))

        radio = 4
        punto_id = self.canvas.create_oval(
            event.x - radio, event.y - radio, event.x + radio, event.y + radio,
            fill=GRANATE, outline=""
        )
        self._id_puntos_preview.append(punto_id)

        if len(self._puntos) == 1:
            self.status_var.set("Ahora haz clic en el FINAL de la línea.")
        elif len(self._puntos) == 2:
            (x1o, y1o), (x2o, y2o) = self._puntos
            self.canvas.create_line(x1o * self.escala, y1o * self.escala,
                                     x2o * self.escala, y2o * self.escala,
                                     fill=GRANATE, width=2)
            self.status_var.set("Línea marcada. Presiona \"Guardar línea\" o \"Reintentar\" si no quedó bien.")
            self.btn_guardar.configure(state="normal")

    def _reiniciar(self):
        self._puntos = []
        self._id_puntos_preview = []
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor="nw", image=self._imgtk)
        self.status_var.set("Esperando el primer clic (inicio de la línea)…")
        self.btn_guardar.configure(state="disabled")

    def _guardar(self):
        if len(self._puntos) != 2:
            return
        (x1, y1), (x2, y2) = self._puntos
        x0, x1f = sorted([x1, x2])
        y = (y1 + y2) / 2
        guardar_linea_manual(self.plantilla_path, round(x0), round(x1f), round(y))
        self.destroy()
        if self.on_guardado:
            self.on_guardado()


class MarcadorCajaDialog(tk.Toplevel):
    """
    Ventana para marcar a mano el recuadro donde va el código QR en una
    plantilla, para los casos en que la detección automática no acierte.
    El usuario da dos clics: esquina superior izquierda y luego esquina
    inferior derecha del recuadro.
    """

    ANCHO_MAX = 900
    ALTO_MAX = 640

    def __init__(self, parent, plantilla_path: Path,
                 info_previa: dict | None, on_guardado):
        super().__init__(parent)
        self.title("Marcar recuadro del QR")
        self.configure(bg=CREMA)
        self.transient(parent)
        self.grab_set()

        self.plantilla_path = plantilla_path
        self.on_guardado = on_guardado
        self._puntos: list[tuple[int, int]] = []  # coords en la imagen ORIGINAL

        self.im_original = Image.open(plantilla_path).convert("RGB")
        ancho_o, alto_o = self.im_original.size
        self.escala = min(self.ANCHO_MAX / ancho_o, self.ALTO_MAX / alto_o, 1.0)
        ancho_c = max(1, int(ancho_o * self.escala))
        alto_c = max(1, int(alto_o * self.escala))

        im_mostrar = self.im_original.resize((ancho_c, alto_c))
        self._imgtk = ImageTk.PhotoImage(im_mostrar)

        ttk.Label(
            self,
            text=("Haz clic en la esquina SUPERIOR IZQUIERDA del recuadro donde va el QR, "
                  "y luego en la esquina INFERIOR DERECHA."),
            style="Card.TLabel", background=CREMA, wraplength=ancho_c,
            font=("Liberation Serif", 11, "bold"),
        ).pack(padx=12, pady=(12, 6), anchor="w")

        self.canvas = tk.Canvas(self, width=ancho_c, height=alto_c,
                                 bg=BLANCO, highlightthickness=1, highlightbackground=BORDE)
        self.canvas.pack(padx=12, pady=6)
        self.canvas.create_image(0, 0, anchor="nw", image=self._imgtk)
        self.canvas.bind("<Button-1>", self._al_hacer_clic)

        # Si ya había un recuadro (auto o manual previo), lo mostramos de
        # entrada como referencia, en gris, para que el usuario vea de dónde parte.
        if info_previa and info_previa.get("origen") in ("auto", "manual"):
            x0 = info_previa["x0"] * self.escala
            y0 = info_previa["y0"] * self.escala
            x1 = info_previa["x1"] * self.escala
            y1 = info_previa["y1"] * self.escala
            self.canvas.create_rectangle(x0, y0, x1, y1, outline="#B0A99B", width=2, dash=(4, 2))

        self.status_var = tk.StringVar(value="Esperando el primer clic (esquina superior izquierda)…")
        ttk.Label(self, textvariable=self.status_var, style="Card.TLabel",
                  background=CREMA, foreground=VERDE_OSCURO).pack(padx=12, anchor="w")

        botones = ttk.Frame(self, style="TFrame")
        botones.pack(fill="x", padx=12, pady=12)
        ttk.Button(botones, text="Reintentar", style="Secondary.TButton",
                   command=self._reiniciar).pack(side="left")
        ttk.Button(botones, text="Cancelar", style="Secondary.TButton",
                   command=self.destroy).pack(side="right")
        self.btn_guardar = ttk.Button(botones, text="Guardar recuadro", style="Accent.TButton",
                                       command=self._guardar, state="disabled")
        self.btn_guardar.pack(side="right", padx=8)

    def _al_hacer_clic(self, event):
        if len(self._puntos) >= 2:
            return
        x_orig = event.x / self.escala
        y_orig = event.y / self.escala
        self._puntos.append((x_orig, y_orig))

        radio = 4
        self.canvas.create_oval(
            event.x - radio, event.y - radio, event.x + radio, event.y + radio,
            fill=GRANATE, outline=""
        )

        if len(self._puntos) == 1:
            self.status_var.set("Ahora haz clic en la esquina INFERIOR DERECHA del recuadro.")
        elif len(self._puntos) == 2:
            (x1o, y1o), (x2o, y2o) = self._puntos
            self.canvas.create_rectangle(x1o * self.escala, y1o * self.escala,
                                          x2o * self.escala, y2o * self.escala,
                                          outline=GRANATE, width=2)
            self.status_var.set("Recuadro marcado. Presiona \"Guardar recuadro\" o \"Reintentar\" si no quedó bien.")
            self.btn_guardar.configure(state="normal")

    def _reiniciar(self):
        self._puntos = []
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor="nw", image=self._imgtk)
        self.status_var.set("Esperando el primer clic (esquina superior izquierda)…")
        self.btn_guardar.configure(state="disabled")

    def _guardar(self):
        if len(self._puntos) != 2:
            return
        (x1, y1), (x2, y2) = self._puntos
        x0, x1f = sorted([x1, x2])
        y0, y1f = sorted([y1, y2])
        guardar_caja_qr_manual(self.plantilla_path, round(x0), round(y0), round(x1f), round(y1f))
        self.destroy()
        if self.on_guardado:
            self.on_guardado()


class DialogoCuenta(tk.Toplevel):
    """Ventana pequeña para agregar una cuenta de correo remitente (alias,
    dirección y contraseña de app), con la opción de recordarla en disco."""

    def __init__(self, parent, on_guardar):
        super().__init__(parent)
        self.title("Agregar cuenta de correo")
        self.configure(bg=CREMA)
        self.transient(parent)
        self.grab_set()
        self.resizable(False, False)
        self.on_guardar = on_guardar

        cont = ttk.Frame(self, style="TFrame", padding=16)
        cont.pack(fill="both", expand=True)

        self.var_alias = tk.StringVar(value="")
        self.var_correo = tk.StringVar(value="")
        self.var_pass = tk.StringVar(value="")
        self.var_recordar = tk.BooleanVar(value=False)
        self.var_limite = tk.StringVar(value="500")

        def _fila(etiqueta, var, show=None):
            f = ttk.Frame(cont, style="TFrame")
            f.pack(fill="x", pady=4)
            ttk.Label(f, text=etiqueta, width=16).pack(side="left")
            kwargs = {"show": show} if show else {}
            entrada = ttk.Entry(f, textvariable=var, width=32, **kwargs)
            entrada.pack(side="left", fill="x", expand=True)
            return entrada

        _fila("Alias (para ti):", self.var_alias)
        _fila("Correo:", self.var_correo)
        entrada_pass = _fila("Contraseña de app:", self.var_pass, show="•")
        _fila("Límite diario:", self.var_limite)

        fila_ver = ttk.Frame(cont, style="TFrame")
        fila_ver.pack(fill="x")
        ttk.Button(
            fila_ver, text="Mostrar/ocultar", style="Secondary.TButton",
            command=lambda: entrada_pass.configure(
                show="" if entrada_pass.cget("show") == "•" else "•"
            ),
        ).pack(side="left", pady=(0, 4))

        ttk.Checkbutton(
            cont, text="Recordar esta contraseña en este equipo (se guarda en texto simple)",
            variable=self.var_recordar,
        ).pack(anchor="w", pady=(8, 0))

        ttk.Label(
            cont,
            text=("Gmail normal deja mandar ~500 correos al día por cuenta; Google Workspace "
                  "(correo institucional) suele permitir ~2000. Cuando esta cuenta llegue a su "
                  "límite, el programa pasa solo a la siguiente cuenta que hayas agregado y "
                  "sigue donde se quedó."),
            wraplength=380, justify="left", foreground="#8A8272",
            font=("Liberation Serif", 9, "italic"),
        ).pack(anchor="w", pady=(4, 0))

        ttk.Label(
            cont,
            text=("Si NO la recuerdas, el programa te la pedirá otra vez cada vez que abras "
                  "el programa y quieras enviar correos (pero no en cada tanda dentro de la "
                  "misma sesión). Si SÍ la recuerdas, queda guardada en un archivo de esta "
                  "misma carpeta — solo hazlo en tu propia computadora."),
            wraplength=380, justify="left", foreground="#8A8272",
            font=("Liberation Serif", 9, "italic"),
        ).pack(anchor="w", pady=(6, 0))

        botones = ttk.Frame(cont, style="TFrame")
        botones.pack(fill="x", pady=(14, 0))
        ttk.Button(botones, text="Cancelar", style="Secondary.TButton",
                   command=self.destroy).pack(side="right")
        ttk.Button(botones, text="Guardar cuenta", style="Accent.TButton",
                   command=self._guardar).pack(side="right", padx=8)

    def _guardar(self):
        alias = self.var_alias.get().strip()
        correo = self.var_correo.get().strip()
        contrasena = self.var_pass.get()
        if not alias:
            messagebox.showwarning("Falta el alias", "Ponle un nombre a la cuenta para identificarla.")
            return
        if not correo or "@" not in correo or "." not in correo.split("@")[-1]:
            messagebox.showwarning("Correo inválido", "Escribe una dirección de correo válida.")
            return
        if not contrasena:
            messagebox.showwarning("Falta la contraseña", "Escribe la contraseña de aplicación de esta cuenta.")
            return
        try:
            limite = int(self.var_limite.get().strip())
            if limite <= 0:
                raise ValueError
        except ValueError:
            messagebox.showwarning("Límite inválido", "El límite diario debe ser un número mayor a 0 (ej. 500).")
            return
        self.on_guardar(alias, correo, contrasena, self.var_recordar.get(), limite)
        self.destroy()
