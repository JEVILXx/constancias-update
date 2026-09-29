"""
PanelConstanciasMixin: todo lo específico del modo "Constancias" —
construcción del panel, selección de Excel/plantilla, columnas,
posición de la línea del nombre, gestión de cuentas de correo (varias
cuentas con límite diario), el mensaje del correo, y la generación en
sí (hilo aparte que llama a core.procesar_excel).

Se combina con ComunesMixin y PanelQRMixin en gui.app.ConstanciasGUI.
"""

from __future__ import annotations

import json
import threading
import traceback
from datetime import date
from pathlib import Path

import pandas as pd
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image

from core import (
    Config, encontrar_columna, procesar_excel, render_certificado,
    analizar_plantilla, guardar_linea_manual, eliminar_linea_manual,
    CorreoConfig, CuentaEnvio,
)
from .dnd import DND_DISPONIBLE
from .dialogos import MarcadorLineaDialog, DialogoCuenta
from .estilos import VERDE_OSCURO, GRIS_TEXTO, BORDE
from .rutas import CUENTAS_CORREO_PATH


class PanelConstanciasMixin:
    # ---- Sub-panel: modo Constancias ----
    def _construir_panel_constancias(self, card):
        # Excel
        fila1 = ttk.Frame(card, style="Card.TFrame")
        fila1.pack(fill="x", pady=4)
        self.fila_excel = fila1
        ttk.Label(fila1, text="Archivo Excel:", style="Card.TLabel", width=16).pack(side="left")
        self.excel_var = tk.StringVar(value="(sin seleccionar)")
        ttk.Label(fila1, textvariable=self.excel_var, style="Card.TLabel",
                  foreground=VERDE_OSCURO).pack(side="left", fill="x", expand=True)
        ttk.Button(fila1, text="Examinar…", style="Secondary.TButton",
                   command=self._elegir_excel).pack(side="right")

        # Plantilla
        fila2 = ttk.Frame(card, style="Card.TFrame")
        fila2.pack(fill="x", pady=4)
        self.fila_plantilla = fila2
        ttk.Label(fila2, text="Plantilla imagen:", style="Card.TLabel", width=16).pack(side="left")
        self.plantilla_var = tk.StringVar(
            value=str(self.plantilla_path) if self.plantilla_path else "(sin seleccionar)"
        )
        ttk.Label(fila2, textvariable=self.plantilla_var, style="Card.TLabel",
                  foreground=VERDE_OSCURO).pack(side="left", fill="x", expand=True)
        ttk.Button(fila2, text="Examinar…", style="Secondary.TButton",
                   command=self._elegir_plantilla).pack(side="right")

        ttk.Label(
            card,
            text=("Arrastra aquí tu Excel o la imagen de la plantilla desde tu explorador "
                  "de archivos (a cualquier parte de este panel) para cargarlos más rápido."
                  if DND_DISPONIBLE else
                  "Tip: instala \"tkinterdnd2\" (pip install tkinterdnd2) para poder arrastrar "
                  "archivos aquí en vez de usar \"Examinar…\"."),
            style="Card.TLabel", foreground="#8A8272", font=("Liberation Serif", 9, "italic"),
            wraplength=520, justify="left",
        ).pack(anchor="w", pady=(2, 0))

        sep = ttk.Separator(card)
        sep.pack(fill="x", pady=10)

        # Columnas
        fila4 = ttk.Frame(card, style="Card.TFrame")
        fila4.pack(fill="x", pady=4)
        ttk.Label(fila4, text="Columna de nombre:", style="Card.TLabel", width=18).pack(side="left")
        self.combo_nombre = ttk.Combobox(fila4, values=[], state="readonly")
        self.combo_nombre.pack(side="left", fill="x", expand=True)
        self.combo_nombre.bind("<<ComboboxSelected>>", lambda e: self._refrescar_preview_datos())

        fila5 = ttk.Frame(card, style="Card.TFrame")
        fila5.pack(fill="x", pady=4)
        ttk.Label(fila5, text="Columna de matrícula:", style="Card.TLabel", width=18).pack(side="left")
        self.combo_matricula = ttk.Combobox(fila5, values=[], state="readonly")
        self.combo_matricula.pack(side="left", fill="x", expand=True)
        self.combo_matricula.bind("<<ComboboxSelected>>", lambda e: self._refrescar_preview_datos())

        fila5b = ttk.Frame(card, style="Card.TFrame")
        fila5b.pack(fill="x", pady=4)
        ttk.Label(fila5b, text="Columna de correo:", style="Card.TLabel", width=18).pack(side="left")
        self.combo_correo = ttk.Combobox(fila5b, values=[], state="readonly")
        self.combo_correo.pack(side="left", fill="x", expand=True)

        ttk.Label(card, text="Detectamos las columnas automáticamente; cámbialas aquí si hace falta.",
                  style="Card.TLabel", foreground="#8A8272", font=("Liberation Serif", 9, "italic")).pack(
            anchor="w", pady=(6, 0)
        )

        sep2 = ttk.Separator(card)
        sep2.pack(fill="x", pady=10)

        # ---- Posición del nombre sobre la plantilla ----
        fila_pos = ttk.Frame(card, style="Card.TFrame")
        fila_pos.pack(fill="x", pady=4)
        ttk.Label(fila_pos, text="Posición del nombre:", style="Card.TLabel", width=18).pack(side="left")
        self.linea_estado_var = tk.StringVar(value="Sin plantilla cargada")
        ttk.Label(fila_pos, textvariable=self.linea_estado_var, style="Card.TLabel",
                  foreground=VERDE_OSCURO).pack(side="left", fill="x", expand=True)

        fila_pos2 = ttk.Frame(card, style="Card.TFrame")
        fila_pos2.pack(fill="x", pady=(0, 4))
        ttk.Label(fila_pos2, text="", width=18).pack(side="left")
        ttk.Button(
            fila_pos2, text="Marcar línea manualmente", style="Secondary.TButton",
            command=self._abrir_marcador_linea,
        ).pack(side="left")
        ttk.Button(
            fila_pos2, text="Volver a automático", style="Secondary.TButton",
            command=self._quitar_marca_manual,
        ).pack(side="left", padx=8)

        ttk.Label(
            card,
            text=("El nombre se acomoda solo sobre la línea que detectamos en la plantilla. "
                  "Si en la vista previa se ve chueco o encimado, usa \"Marcar línea manualmente\"."),
            style="Card.TLabel", foreground="#8A8272", font=("Liberation Serif", 9, "italic"),
            wraplength=520, justify="left",
        ).pack(anchor="w", pady=(2, 0))

        sep3 = ttk.Separator(card)
        sep3.pack(fill="x", pady=10)

        # ---- Envío por correo (opcional) — varias cuentas ----
        fila_check = ttk.Frame(card, style="Card.TFrame")
        fila_check.pack(fill="x", pady=(0, 4))
        ttk.Checkbutton(
            fila_check, text="Enviar también por correo a cada persona (usa la columna de correo)",
            variable=self.enviar_correo_var, style="Card.TCheckbutton",
            command=self._al_cambiar_enviar_correo,
        ).pack(anchor="w")

        self.frame_correo = ttk.Frame(card, style="Card.TFrame")
        self.frame_correo.pack(fill="x", pady=(4, 0))

        ttk.Label(
            self.frame_correo,
            text="Cuentas guardadas:",
            style="Card.TLabel",
        ).pack(anchor="w")

        fila_lista = ttk.Frame(self.frame_correo, style="Card.TFrame")
        fila_lista.pack(fill="x", pady=(4, 0))
        self.lista_cuentas = tk.Listbox(
            fila_lista, height=4, selectmode="extended", exportselection=False,
            bg="#FBFAF5", fg=GRIS_TEXTO, font=("Liberation Serif", 10),
            highlightthickness=1, highlightbackground=BORDE, relief="flat",
        )
        self.lista_cuentas.pack(side="left", fill="x", expand=True)
        scroll_cuentas = ttk.Scrollbar(fila_lista, command=self.lista_cuentas.yview)
        scroll_cuentas.pack(side="left", fill="y")
        self.lista_cuentas.configure(yscrollcommand=scroll_cuentas.set)

        fila_seleccion = ttk.Frame(self.frame_correo, style="Card.TFrame")
        fila_seleccion.pack(fill="x", pady=(4, 0))
        self.btn_usar_todas_cuentas = ttk.Button(
            fila_seleccion, text="Usar todas", style="Accent.TButton",
            command=self._seleccionar_todas_cuentas,
        )
        self.btn_usar_todas_cuentas.pack(side="left")
        ttk.Label(
            fila_seleccion, text="  o elige tú cuáles con clic (Ctrl+clic para varias):",
            style="Card.TLabel", foreground="#8A8272", font=("Liberation Serif", 9, "italic"),
        ).pack(side="left")

        fila_botones_cuenta = ttk.Frame(self.frame_correo, style="Card.TFrame")
        fila_botones_cuenta.pack(fill="x", pady=(6, 0))
        self.btn_agregar_cuenta = ttk.Button(
            fila_botones_cuenta, text="Agregar cuenta", style="Secondary.TButton",
            command=self._abrir_dialogo_cuenta,
        )
        self.btn_agregar_cuenta.pack(side="left")
        self.btn_cerrar_sesion_cuenta = ttk.Button(
            fila_botones_cuenta, text="Cerrar sesión", style="Secondary.TButton",
            command=self._cerrar_sesion_cuenta_seleccionada,
        )
        self.btn_cerrar_sesion_cuenta.pack(side="left", padx=8)
        self.btn_eliminar_cuenta = ttk.Button(
            fila_botones_cuenta, text="Eliminar", style="Secondary.TButton",
            command=self._eliminar_cuenta_seleccionada,
        )
        self.btn_eliminar_cuenta.pack(side="left")

        ttk.Label(
            self.frame_correo,
            text=("Si usas Gmail, la \"contraseña de app\" NO es tu contraseña normal: activa la "
                  "verificación en dos pasos en tu cuenta de Google y genera una en "
                  "myaccount.google.com/apppasswords. Cada cuenta de Gmail normal puede mandar "
                  "hasta ~500 correos al día; si tienes más personas que eso, agrega varias "
                  "cuentas y selecciónalas todas para repartir el envío."),
            style="Card.TLabel", foreground="#8A8272", font=("Liberation Serif", 9, "italic"),
            wraplength=520, justify="left",
        ).pack(anchor="w", pady=(6, 0))

        sep_msg = ttk.Separator(self.frame_correo)
        sep_msg.pack(fill="x", pady=10)

        ttk.Label(self.frame_correo, text="Mensaje del correo:", style="Card.TLabel").pack(anchor="w")

        fila_modo_msg = ttk.Frame(self.frame_correo, style="Card.TFrame")
        fila_modo_msg.pack(fill="x", pady=(4, 6))
        self.radio_msg_auto = ttk.Radiobutton(
            fila_modo_msg, text="Mensaje automático", variable=self.modo_mensaje_var,
            value="automatico", command=self._cambiar_modo_mensaje,
        )
        self.radio_msg_auto.pack(side="left", padx=(0, 12))
        self.radio_msg_personalizado = ttk.Radiobutton(
            fila_modo_msg, text="Redactar el mío", variable=self.modo_mensaje_var,
            value="personalizado", command=self._cambiar_modo_mensaje,
        )
        self.radio_msg_personalizado.pack(side="left")

        self.frame_mensaje_auto = ttk.Frame(self.frame_correo, style="Card.TFrame")
        ttk.Label(
            self.frame_mensaje_auto,
            text=(f"Título: \"{CorreoConfig.asunto}\"\n\nMensaje:\n{CorreoConfig.cuerpo}"),
            style="Card.TLabel", foreground="#8A8272", font=("Liberation Serif", 9, "italic"),
            wraplength=500, justify="left",
        ).pack(anchor="w")

        self.frame_mensaje_personalizado = ttk.Frame(self.frame_correo, style="Card.TFrame")
        fila_titulo = ttk.Frame(self.frame_mensaje_personalizado, style="Card.TFrame")
        fila_titulo.pack(fill="x", pady=3)
        ttk.Label(fila_titulo, text="Título:", style="Card.TLabel", width=10).pack(side="left")
        self.entry_asunto_personalizado = ttk.Entry(fila_titulo, textvariable=self.asunto_personalizado_var)
        self.entry_asunto_personalizado.pack(side="left", fill="x", expand=True)

        ttk.Label(self.frame_mensaje_personalizado, text="Mensaje:", style="Card.TLabel").pack(
            anchor="w", pady=(4, 2)
        )

        # El saludo con el nombre se agrega SOLO, automático — el usuario nada
        # más redacta el resto, así nunca sale mal (repetido, sin nombre, etc.).
        ttk.Label(
            self.frame_mensaje_personalizado, text="Hola {nombre},",
            style="Card.TLabel", foreground="#8A8272", font=("Liberation Serif", 10, "italic"),
        ).pack(anchor="w")

        self.texto_cuerpo_personalizado = tk.Text(
            self.frame_mensaje_personalizado, height=6, wrap="word",
            bg="#FBFAF5", fg=GRIS_TEXTO, font=("Liberation Serif", 10),
            highlightthickness=1, highlightbackground=BORDE, relief="flat",
        )
        self.texto_cuerpo_personalizado.pack(fill="x")
        if self._cuerpo_personalizado_inicial:
            self.texto_cuerpo_personalizado.insert("1.0", self._cuerpo_personalizado_inicial)

        ttk.Label(
            self.frame_mensaje_personalizado,
            text=("El saludo \"Hola [nombre de la persona],\" se agrega solo al principio del "
                  "correo de cada quien — tú nada más escribe lo que sigue después. Si quieres, "
                  "también puedes escribir {nombre} en el título o en cualquier otra parte del "
                  "mensaje y se reemplaza igual por el nombre de cada persona."),
            style="Card.TLabel", foreground="#8A8272", font=("Liberation Serif", 9, "italic"),
            wraplength=500, justify="left",
        ).pack(anchor="w", pady=(4, 0))

        self._cambiar_modo_mensaje()

        self._refrescar_lista_cuentas()
        self._al_cambiar_enviar_correo()

    def _cambiar_modo_mensaje(self):
        if self.modo_mensaje_var.get() == "personalizado":
            self.frame_mensaje_auto.pack_forget()
            self.frame_mensaje_personalizado.pack(fill="x", pady=(2, 0))
        else:
            self.frame_mensaje_personalizado.pack_forget()
            self.frame_mensaje_auto.pack(fill="x", pady=(2, 0))

    def _al_cambiar_enviar_correo(self):
        """Prende/apaga los controles de cuentas y de mensaje según el checkbox."""
        estado = "normal" if self.enviar_correo_var.get() else "disabled"
        for widget in (self.lista_cuentas, self.btn_usar_todas_cuentas, self.btn_agregar_cuenta,
                       self.btn_cerrar_sesion_cuenta, self.btn_eliminar_cuenta,
                       self.radio_msg_auto, self.radio_msg_personalizado,
                       self.entry_asunto_personalizado, self.texto_cuerpo_personalizado):
            try:
                widget.configure(state=estado)
            except tk.TclError:
                pass

    def _seleccionar_todas_cuentas(self):
        estado_previo = self.lista_cuentas.cget("state")
        self.lista_cuentas.configure(state="normal")
        self.lista_cuentas.selection_set(0, "end")
        self.lista_cuentas.configure(state=estado_previo)

    # ------------------------------------------------------------------
    # Gestión de cuentas de correo (varias cuentas para repartir el envío)
    # ------------------------------------------------------------------
    def _refrescar_lista_cuentas(self):
        hoy = date.today().isoformat()
        # Recordamos qué cuentas estaban seleccionadas (por alias, no por
        # índice, para que no se pierda si el orden cambia) para volver a
        # seleccionarlas después de reconstruir la lista — así no se
        # desmarca solo por refrescar el conteo mientras se está enviando.
        aliases_seleccionados = {
            self.cuentas_correo[i]["alias"] for i in self.lista_cuentas.curselection()
            if i < len(self.cuentas_correo)
        }
        # OJO: un Listbox en estado "disabled" ignora silenciosamente
        # insert()/delete() (no lanza error, simplemente no hace nada), así
        # que lo habilitamos un instante para poder actualizarlo aunque el
        # checkbox de "enviar por correo" esté apagado en este momento.
        estado_previo = self.lista_cuentas.cget("state")
        self.lista_cuentas.configure(state="normal")
        self.lista_cuentas.delete(0, "end")
        for idx, cuenta in enumerate(self.cuentas_correo):
            marca = "[guardada]" if cuenta.get("recordar") else "[no guardada]"
            enviados_hoy = cuenta.get("enviados_hoy", 0) if cuenta.get("fecha_conteo") == hoy else 0
            limite = cuenta.get("limite_diario", 500)
            self.lista_cuentas.insert(
                "end", f"{marca} {cuenta['alias']} — {cuenta['remitente']} ({enviados_hoy}/{limite} hoy)"
            )
            if cuenta["alias"] in aliases_seleccionados:
                self.lista_cuentas.selection_set(idx)
        self.lista_cuentas.configure(state=estado_previo)

    def _abrir_dialogo_cuenta(self):
        DialogoCuenta(self, on_guardar=self._agregar_cuenta)

    def _agregar_cuenta(self, alias: str, remitente: str, contrasena: str, recordar: bool, limite_diario: int = 500):
        self.cuentas_correo.append({
            "alias": alias, "remitente": remitente,
            "recordar": recordar, "contrasena": contrasena if recordar else "",
            "limite_diario": limite_diario, "enviados_hoy": 0, "fecha_conteo": "",
        })
        # La contraseña de la sesión se recuerda mientras el programa esté
        # abierto, se haya pedido "recordar en disco" o no.
        self._contrasenas_sesion[alias] = contrasena
        self._guardar_cuentas()
        self._refrescar_lista_cuentas()

    def _cerrar_sesion_cuenta_seleccionada(self):
        """'Cierra sesión': olvida la contraseña guardada/en memoria de la
        cuenta seleccionada, sin borrar el alias ni el correo. La próxima
        vez que se use, el programa la volverá a pedir."""
        seleccion = list(self.lista_cuentas.curselection())
        if not seleccion:
            messagebox.showinfo("Nada seleccionado", "Selecciona primero la cuenta de la que quieres salir.")
            return
        for indice in seleccion:
            cuenta = self.cuentas_correo[indice]
            cuenta["recordar"] = False
            cuenta["contrasena"] = ""
            self._contrasenas_sesion.pop(cuenta["alias"], None)
        self._guardar_cuentas()
        self._refrescar_lista_cuentas()

    def _eliminar_cuenta_seleccionada(self):
        seleccion = list(self.lista_cuentas.curselection())
        if not seleccion:
            return
        alias_lista = ", ".join(self.cuentas_correo[i]["alias"] for i in seleccion)
        if not messagebox.askyesno(
            "Eliminar cuenta",
            f"¿Seguro que quieres eliminar por completo: {alias_lista}? Esto no se puede deshacer.",
        ):
            return
        for indice in sorted(seleccion, reverse=True):
            alias = self.cuentas_correo[indice]["alias"]
            self._contrasenas_sesion.pop(alias, None)
            del self.cuentas_correo[indice]
        self._guardar_cuentas()
        self._refrescar_lista_cuentas()

    def _actualizar_conteo_cuenta(self, remitente: str, nuevo_total: int):
        """Se llama en cuanto se manda un correo exitosamente, para guardar
        el avance del día de inmediato (por si el proceso se interrumpe)."""
        hoy = date.today().isoformat()
        for cuenta in self.cuentas_correo:
            if cuenta["remitente"] == remitente:
                cuenta["enviados_hoy"] = nuevo_total
                cuenta["fecha_conteo"] = hoy
                break
        self._guardar_cuentas()
        self._refrescar_lista_cuentas()

    def _cargar_cuentas(self):
        if not CUENTAS_CORREO_PATH.exists():
            return
        try:
            datos = json.loads(CUENTAS_CORREO_PATH.read_text(encoding="utf-8"))
            if isinstance(datos, list):
                self.cuentas_correo = datos
        except Exception:
            self.cuentas_correo = []

    def _guardar_cuentas(self):
        try:
            CUENTAS_CORREO_PATH.write_text(
                json.dumps(self.cuentas_correo, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except Exception:
            pass  # guardar la lista de cuentas es un extra, no debe interrumpir el uso normal

    def _pedir_contrasena_ahora(self, alias: str, remitente: str) -> str | None:
        """Pide la contraseña de una cuenta que no se guardó en disco.
        Devuelve la contraseña, o None si el usuario cancela."""
        from .estilos import CREMA

        resultado: dict = {}

        dialogo = tk.Toplevel(self)
        dialogo.title("Contraseña de la cuenta")
        dialogo.configure(bg=CREMA)
        dialogo.transient(self)
        dialogo.grab_set()
        dialogo.resizable(False, False)

        ttk.Label(
            dialogo, text=f"Escribe la contraseña de app para:\n{alias} ({remitente})",
            style="Card.TLabel", background=CREMA, justify="left",
        ).pack(padx=16, pady=(16, 8))

        var_pass = tk.StringVar(value="")
        entrada = ttk.Entry(dialogo, textvariable=var_pass, show="•", width=32)
        entrada.pack(padx=16, pady=4)
        entrada.focus_set()

        def _confirmar(event=None):
            resultado["valor"] = var_pass.get()
            dialogo.destroy()

        def _cancelar():
            dialogo.destroy()

        entrada.bind("<Return>", _confirmar)

        botones = ttk.Frame(dialogo, style="TFrame")
        botones.pack(pady=12)
        ttk.Button(botones, text="Cancelar", style="Secondary.TButton", command=_cancelar).pack(side="left", padx=6)
        ttk.Button(botones, text="Continuar", style="Accent.TButton", command=_confirmar).pack(side="left", padx=6)

        self.wait_window(dialogo)
        return resultado.get("valor")

    # ------------------------------------------------------------------
    # Arrastrar y soltar (Excel / plantilla)
    # ------------------------------------------------------------------
    def _al_soltar_excel(self, ruta: str):
        p = Path(ruta)
        if p.suffix.lower() not in (".xlsx", ".xls"):
            messagebox.showwarning("Archivo no válido", f"Eso no es un Excel (.xlsx/.xls):\n{p.name}")
            return
        self.excel_path = p
        self.excel_var.set(p.name)
        self._ultimo_dir_datos = str(p.parent)
        self._guardar_preferencias()
        self._cargar_columnas()

    def _al_soltar_plantilla(self, ruta: str):
        p = Path(ruta)
        if p.suffix.lower() not in (".jpg", ".jpeg", ".png"):
            messagebox.showwarning("Archivo no válido", f"Eso no es una imagen (.jpg/.png):\n{p.name}")
            return
        self.plantilla_path = p
        self.plantilla_var.set(p.name)
        self._ultimo_dir_plantilla = str(p.parent)
        self._guardar_preferencias()
        self._refrescar_preview_plantilla()
        self._refrescar_preview_datos()

    # ------------------------------------------------------------------
    # Selección manual de archivos
    # ------------------------------------------------------------------
    def _elegir_excel(self):
        self._traer_al_frente()
        ruta = filedialog.askopenfilename(
            parent=self,
            title="Selecciona el Excel con los datos",
            initialdir=self._ultimo_dir_datos,
            filetypes=[("Excel", "*.xlsx *.xls"), ("Todos los archivos", "*.*")],
        )
        if not ruta:
            return
        self.excel_path = Path(ruta)
        self.excel_var.set(self.excel_path.name)
        self._ultimo_dir_datos = str(self.excel_path.parent)
        self._guardar_preferencias()
        self._cargar_columnas()

    def _elegir_plantilla(self):
        self._traer_al_frente()
        ruta = filedialog.askopenfilename(
            parent=self,
            title="Selecciona la imagen de la plantilla",
            initialdir=self._ultimo_dir_plantilla,
            filetypes=[("Imágenes", "*.jpg *.jpeg *.png"), ("Todos los archivos", "*.*")],
        )
        if not ruta:
            return
        self.plantilla_path = Path(ruta)
        self.plantilla_var.set(self.plantilla_path.name)
        self._ultimo_dir_plantilla = str(self.plantilla_path.parent)
        self._guardar_preferencias()
        self._refrescar_preview_plantilla()
        self._refrescar_preview_datos()

    def _cargar_columnas(self):
        try:
            df = pd.read_excel(self.excel_path, sheet_name=0, nrows=5)
        except Exception as e:
            messagebox.showerror("Error al leer el Excel", str(e))
            return

        columnas = list(df.columns)
        self.combo_nombre["values"] = columnas
        self.combo_matricula["values"] = ["(ninguna)"] + columnas
        self.combo_correo["values"] = ["(ninguna)"] + columnas

        col_nombre = encontrar_columna(df, ["Nombre", "Nombre completo", "Nombre Completo", "Participante", "Alumno"])
        col_matricula = encontrar_columna(df, ["Matricula", "Matrícula", "No. Control", "Numero de control", "ID"])
        col_correo = encontrar_columna(df, ["Correo", "Correo electrónico", "Correo Electronico",
                                             "Email", "E-mail", "Correo institucional"])

        self.combo_nombre.set(col_nombre or (columnas[0] if columnas else ""))
        self.combo_matricula.set(col_matricula or "(ninguna)")
        self.combo_correo.set(col_correo or "(ninguna)")

        self._log(f"Excel cargado: {self.excel_path.name} — columnas: {', '.join(map(str, columnas))}")
        self._refrescar_preview_datos()

    # ------------------------------------------------------------------
    # Vista previa — modo Constancias
    # ------------------------------------------------------------------
    def _refrescar_preview_plantilla(self):
        if self.modo_var.get() != "constancias":
            return
        if self.plantilla_path and Path(self.plantilla_path).exists():
            self._mostrar_preview_imagen(Image.open(self.plantilla_path).convert("RGB"))
        else:
            self.preview_label.configure(image="", text="(sin plantilla)")
        self._actualizar_estado_linea()

    def _actualizar_estado_linea(self):
        """Analiza la plantilla actual y actualiza el letrero de estado
        (automático / manual / respaldo)."""
        if not self.plantilla_path or not Path(self.plantilla_path).exists():
            self.linea_estado_var.set("Sin plantilla cargada")
            self._info_linea = None
            return
        try:
            info = analizar_plantilla(Path(self.plantilla_path))
        except Exception as e:
            self.linea_estado_var.set(f"No se pudo analizar la plantilla ({e})")
            self._info_linea = None
            return

        self._info_linea = info
        origen = info["origen"]
        if origen == "manual":
            self.linea_estado_var.set("Marcada manualmente por ti")
        elif origen == "auto":
            self.linea_estado_var.set("Detectada automáticamente")
        else:
            self.linea_estado_var.set("Aviso: no se detectó la línea — usando posición aproximada")

    def _quitar_marca_manual(self):
        if not self.plantilla_path or not Path(self.plantilla_path).exists():
            return
        eliminar_linea_manual(Path(self.plantilla_path))
        self._log("Se quitó la marca manual; ahora se usará la detección automática.")
        self._actualizar_estado_linea()
        self._refrescar_preview_datos()

    def _abrir_marcador_linea(self):
        if not self.plantilla_path or not Path(self.plantilla_path).exists():
            messagebox.showwarning("Falta la plantilla", "Primero selecciona la imagen de la plantilla.")
            return
        MarcadorLineaDialog(self, Path(self.plantilla_path), self._info_linea,
                             on_guardado=self._al_guardar_marca_manual)

    def _al_guardar_marca_manual(self):
        self._log("Línea marcada manualmente y guardada para esta plantilla.")
        self._actualizar_estado_linea()
        self._refrescar_preview_datos()

    def _refrescar_preview_datos(self):
        if self.modo_var.get() != "constancias":
            return
        if not self.excel_path or not self.plantilla_path:
            return
        col_nombre = self.combo_nombre.get()
        col_matricula = self.combo_matricula.get()
        if not col_nombre:
            return
        try:
            df = pd.read_excel(self.excel_path, sheet_name=0)
            df = df.dropna(how="all")
            if df.empty:
                return
            primera = df.iloc[0]
            nombre = str(primera.get(col_nombre, "")).strip()
            if not nombre or nombre.lower() == "nan":
                return
            matricula = None
            if col_matricula and col_matricula != "(ninguna)":
                val = primera.get(col_matricula)
                if pd.notna(val):
                    matricula = str(val).strip()
                    if matricula.endswith(".0"):
                        matricula = matricula[:-2]

            config = Config(plantilla=Path(self.plantilla_path))
            im = render_certificado(config, nombre, matricula)
            self._mostrar_preview_imagen(im)
        except Exception:
            pass  # la vista previa es solo cosmética, no debe interrumpir al usuario

    # ------------------------------------------------------------------
    # Generación
    # ------------------------------------------------------------------
    def _iniciar_generacion_constancias(self):
        if not self.excel_path:
            messagebox.showwarning("Falta el Excel", "Primero selecciona tu archivo Excel.")
            return
        if not self.plantilla_path or not Path(self.plantilla_path).exists():
            messagebox.showwarning("Falta la plantilla", "Selecciona la imagen de la plantilla.")
            return
        col_nombre = self.combo_nombre.get()
        if not col_nombre:
            messagebox.showwarning("Falta la columna", "Indica cuál columna tiene el nombre.")
            return
        col_matricula = self.combo_matricula.get()
        col_matricula = None if col_matricula in ("", "(ninguna)") else col_matricula

        col_correo = None
        cuentas_envio = None
        if self.enviar_correo_var.get():
            col_correo = self.combo_correo.get()
            col_correo = None if col_correo in ("", "(ninguna)") else col_correo
            if not col_correo:
                messagebox.showwarning(
                    "Falta la columna de correo",
                    "Marcaste enviar por correo, pero no elegiste la columna que tiene los correos.",
                )
                return

            # Mensaje: automático (valores por defecto de CorreoConfig) o redactado por el usuario
            asunto_msg = None
            cuerpo_msg = None
            if self.modo_mensaje_var.get() == "personalizado":
                asunto_msg = self.asunto_personalizado_var.get().strip()
                texto_usuario = self.texto_cuerpo_personalizado.get("1.0", "end").strip()
                if not asunto_msg or not texto_usuario:
                    messagebox.showwarning(
                        "Falta el mensaje",
                        "Elegiste redactar tu propio mensaje: escribe el título y el texto del correo "
                        "(o cambia a \"Mensaje automático\").",
                    )
                    return
                # El saludo con el nombre se agrega solo; si el usuario ya
                # escribió su propio "Hola..." no lo duplicamos.
                if texto_usuario.lower().startswith("hola"):
                    cuerpo_msg = texto_usuario
                else:
                    cuerpo_msg = f"Hola {{nombre}},\n\n{texto_usuario}"
                self._guardar_preferencias()  # recuerda el mensaje redactado para la próxima vez

            indices = sorted(self.lista_cuentas.curselection())
            if not indices:
                messagebox.showwarning(
                    "Falta la cuenta",
                    "Marcaste enviar por correo, pero no seleccionaste ninguna cuenta de la lista "
                    "(agrega una con \"Agregar cuenta\" si aún no tienes ninguna).",
                )
                return

            hoy = date.today().isoformat()
            cuentas_envio = []
            for indice in indices:
                cuenta = self.cuentas_correo[indice]
                contrasena = self._contrasenas_sesion.get(cuenta["alias"]) or cuenta.get("contrasena") or ""
                if not contrasena:
                    contrasena = self._pedir_contrasena_ahora(cuenta["alias"], cuenta["remitente"])
                    if contrasena is None:
                        return  # el usuario canceló
                    self._contrasenas_sesion[cuenta["alias"]] = contrasena

                kwargs_correo = {"remitente": cuenta["remitente"], "contrasena_app": contrasena}
                if asunto_msg is not None:
                    kwargs_correo["asunto"] = asunto_msg
                    kwargs_correo["cuerpo"] = cuerpo_msg

                # Si ya es otro día, el conteo de "enviados hoy" se reinicia solo.
                enviados_hoy = cuenta.get("enviados_hoy", 0) if cuenta.get("fecha_conteo") == hoy else 0
                cuentas_envio.append(CuentaEnvio(
                    config=CorreoConfig(**kwargs_correo),
                    limite_diario=cuenta.get("limite_diario", 500),
                    ya_enviados_hoy=enviados_hoy,
                ))

        self._preparar_ui_generando("Generando constancias…")
        hilo = threading.Thread(
            target=self._trabajo_generacion_constancias,
            args=(col_nombre, col_matricula, col_correo, cuentas_envio),
            daemon=True,
        )
        hilo.start()

    def _trabajo_generacion_constancias(self, col_nombre, col_matricula, col_correo=None, cuentas_envio=None):
        try:
            config = Config(plantilla=Path(self.plantilla_path))

            def on_progreso(i, total, nombre):
                self._cola.put(("progreso", i, total, nombre))

            def on_conteo_actualizado(remitente, nuevo_total):
                self._cola.put(("conteo_correo", remitente, nuevo_total))

            generados = procesar_excel(
                config,
                excel_path=Path(self.excel_path),
                carpeta_salida=Path(self.salida_path),
                col_nombre=col_nombre,
                col_matricula=col_matricula,
                col_correo=col_correo,
                cuentas_envio=cuentas_envio,
                on_progreso=on_progreso,
                on_conteo_actualizado=on_conteo_actualizado,
            )
            self._cola.put(("listo", generados, "constancias", True))
        except Exception as e:
            self._cola.put(("error", str(e), traceback.format_exc()))
