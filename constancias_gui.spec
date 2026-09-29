# -*- mode: python ; coding: utf-8 -*-
"""
Especificación de PyInstaller para compilar el Generador de Constancias
y QR como aplicación de escritorio (.exe en Windows).

Uso (en la máquina donde quieras compilar, con el entorno activado y
pyinstaller instalado):

    pyinstaller constancias_gui.spec

El resultado queda en dist/GeneradorConstanciasQR/ (modo carpeta, NO
un solo archivo .exe) — así es más rápido de abrir y los archivos que
el programa necesita junto a sí (plantilla.jpeg, preferencias, etc.)
quedan de verdad al lado del .exe, no escondidos en una carpeta
temporal. Reparte esa carpeta completa, no solo el .exe suelto.

Ver LEEME.txt, sección "COMPILAR COMO .EXE PARA WINDOWS", para el
paso a paso completo.
"""

from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

# tkinterdnd2 trae archivos .tcl/.dll que PyInstaller no detecta solo.
datas = collect_data_files("tkinterdnd2")

# Archivos que el programa espera encontrar junto a sí (plantilla de
# ejemplo, datos de ejemplo, instrucciones, número de versión).
datas += [
    ("plantilla.jpeg", "."),
    ("datos_ejemplo.xlsx", "."),
    ("LEEME.txt", "."),
    ("VERSION", "."),
]

a = Analysis(
    ["constancias_gui.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=[
        "openpyxl",
        "pypdf",
        "PIL._tkinter_finder",
        "tkinterdnd2",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="GeneradorConstanciasQR",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,   # sin ventana de consola negra detrás (app de escritorio)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # PyInstaller 6+ por defecto mete todo en una subcarpeta "_internal/".
    # Con "." lo desactivamos, para que plantilla.jpeg, preferencias, etc.
    # queden DIRECTO junto al .exe (que es de donde el programa las busca).
    contents_directory=".",
    # icon="icono.ico",   # descomenta y pon aquí tu .ico si quieres un ícono propio
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="GeneradorConstanciasQR",
)
