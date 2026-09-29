#!/usr/bin/env python3
"""
Generador de Constancias y QR UAdeO — punto de entrada de la interfaz gráfica
-------------------------------------------------------------------------------
Todo el código está organizado en paquetes para que ningún archivo sea
demasiado largo:

    core/   -> motor de generación (constancias, QR, correo, detección
               automática de posiciones, actualizaciones) — ver core/__init__.py
    gui/    -> interfaz gráfica (ventanas, paneles, diálogos) — ver
               gui/__init__.py

Este archivo solo arranca la aplicación.

Requisitos: pandas, openpyxl, pillow, pypdf, numpy (tkinter viene con
Python). Opcional: tkinterdnd2, para poder arrastrar archivos a la
ventana (pip install tkinterdnd2); sin ella, todo funciona igual, solo
sin esa comodidad.

Ejecutar:
    python3 constancias_gui.py
"""

from gui import ConstanciasGUI

if __name__ == "__main__":
    app = ConstanciasGUI()
    app.mainloop()
