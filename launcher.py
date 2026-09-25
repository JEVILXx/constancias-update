#!/usr/bin/env python3
"""
Lanzador — ESTE es el archivo que se convierte en .exe (ver constancias.spec).

Hace tres cosas:
  1. Busca actualizaciones (con una ventanita de "Buscando actualizaciones…").
  2. Carga la versión más nueva del código (o la del .exe si no hay).
  3. Abre la interfaz.

Casi nunca necesitarás cambiarlo, así que el .exe se genera UNA vez; todo lo
demás (core/, gui/, paneles nuevos…) se actualiza solo desde internet o
desde una carpeta compartida.

Para probarlo sin .exe:   python launcher.py
"""

import sys
import traceback

import actualizador

GRANATE = "#7A1F2B"


def _buscar_con_ventanita():
    """Revisa actualizaciones mostrando una ventanita; nunca bloquea el arranque si falla."""
    try:
        import tkinter as tk
        raiz = tk.Tk()
    except Exception:
        actualizador.buscar_e_instalar()
        return

    raiz.overrideredirect(True)
    raiz.configure(bg=GRANATE)
    ancho, alto = 400, 110
    raiz.geometry(f"{ancho}x{alto}+{(raiz.winfo_screenwidth() - ancho) // 2}+{(raiz.winfo_screenheight() - alto) // 2}")
    tk.Label(raiz, text="Generador de Constancias UAdeO", bg=GRANATE, fg="white",
             font=("Times New Roman", 15, "bold")).pack(pady=(22, 6))
    estado = tk.Label(raiz, text="Buscando actualizaciones…", bg=GRANATE, fg="#F3D9DC",
                      font=("Times New Roman", 11))
    estado.pack()
    raiz.update()

    def al_encontrar(version):
        estado.config(text=f"Descargando la versión {version}…")
        raiz.update()

    def progreso(leido, total):
        if total:
            estado.config(text=f"Descargando actualización… {leido * 100 // total}%")
        raiz.update()

    try:
        actualizador.buscar_e_instalar(progreso=progreso, al_encontrar=al_encontrar)
    finally:
        raiz.destroy()


def main():
    actualizador.preparar_entorno()
    cfg = actualizador.leer_config()
    if str(cfg.get("origen", "")).strip() and cfg.get("activo", True) is not False:
        _buscar_con_ventanita()
    app, _version = actualizador.cargar_aplicacion()
    app.mainloop()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        detalle = traceback.format_exc()
        actualizador.registrar("Error fatal al iniciar:\n" + detalle)
        try:
            import tkinter as tk
            from tkinter import messagebox
            r = tk.Tk()
            r.withdraw()
            messagebox.showerror(
                "No se pudo abrir el programa",
                "Ocurrió un error al iniciar.\n\nEl detalle quedó guardado en:\n"
                f"{actualizador.carpeta_datos() / 'actualizaciones.log'}\n\n{detalle[-600:]}",
            )
        except Exception:
            pass
        sys.exit(1)
