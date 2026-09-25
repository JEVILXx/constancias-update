# -*- mode: python ; coding: utf-8 -*-
# Construir:  pyinstaller constancias.spec --noconfirm     (o ejecuta construir_exe.bat)
#
# IMPORTANTE: core/ y gui/ NO se compilan dentro del .exe: se copian como
# archivos .py normales a "app_base". Así el lanzador puede sustituirlos por
# versiones descargadas. Por eso TODAS las librerías que usen esas carpetas
# se declaran aquí en hiddenimports (el análisis no las ve, porque el
# lanzador carga gui/ dinámicamente).
#
# Si algún día agregas una librería nueva (pip install ...), añádela a
# hiddenimports y vuelve a generar el .exe (las librerías no se actualizan
# por internet, solo tu código).
import os
from PyInstaller.utils.hooks import collect_all

ONEFILE = False  # False = carpeta (arranca más rápido); True = un solo .exe (más lento al abrir)

datas = [
    ("core", "app_base/core"),
    ("gui", "app_base/gui"),
    ("version.json", "app_base"),
    ("actualizaciones.json", "app_base"),
]
if os.path.exists("plantilla.jpeg"):
    datas.append(("plantilla.jpeg", "app_base"))
binaries = []
hiddenimports = [
    "pandas", "numpy", "openpyxl", "pypdf",
    "PIL", "PIL.Image", "PIL.ImageDraw", "PIL.ImageFont", "PIL.ImageTk", "PIL._tkinter_finder",
    "tkinter", "tkinter.ttk", "tkinter.filedialog", "tkinter.messagebox",
    "smtplib", "ssl", "email.message", "unicodedata", "queue", "threading",
    "subprocess", "dataclasses", "hashlib", "datetime", "traceback", "argparse",
]

for paquete in ("tkinterdnd2", "openpyxl", "pandas"):
    try:
        d, b, h = collect_all(paquete)
        datas += d; binaries += b; hiddenimports += h
    except Exception:
        pass  # tkinterdnd2 es opcional

a = Analysis(
    ["launcher.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["matplotlib", "scipy", "IPython", "pytest"],
)
pyz = PYZ(a.pure)

if ONEFILE:
    exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name="GeneradorConstancias",
              console=False, upx=False)
else:
    exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="GeneradorConstancias",
              console=False, upx=False)
    coll = COLLECT(exe, a.binaries, a.datas, name="GeneradorConstancias", upx=False)
