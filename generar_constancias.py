#!/usr/bin/env python3
"""
Generador de Constancias UAdeO — versión de consola (solo modo Constancias)
-----------------------------------------------------------------------------
Uso:
    python3 generar_constancias.py datos.xlsx [--plantilla plantilla.jpeg]
                                    [--salida salida] [--hoja 0]

Si no se indica --plantilla, usa "plantilla.jpeg" en esta misma carpeta.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from core import Config, encontrar_columna, procesar_excel

CARPETA = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description="Genera constancias en PDF a partir de un Excel.")
    parser.add_argument("excel", help="Ruta al archivo Excel con los datos")
    parser.add_argument("--plantilla", default=str(CARPETA / "plantilla.jpeg"),
                         help="Imagen de la plantilla (por defecto: plantilla.jpeg)")
    parser.add_argument("--salida", default=str(CARPETA / "salida"),
                         help="Carpeta de salida (por defecto: ./salida)")
    parser.add_argument("--hoja", default=0, help="Nombre o índice de la hoja de Excel (por defecto: 0)")
    parser.add_argument("--col-nombre", default=None, help="Nombre exacto de la columna de nombre")
    parser.add_argument("--col-matricula", default=None, help="Nombre exacto de la columna de matrícula")
    args = parser.parse_args()

    excel_path = Path(args.excel)
    plantilla_path = Path(args.plantilla)
    salida_path = Path(args.salida)

    if not excel_path.exists():
        print(f"No se encontró el Excel: {excel_path}")
        return
    if not plantilla_path.exists():
        print(f"No se encontró la plantilla: {plantilla_path}")
        return

    import pandas as pd
    df_muestra = pd.read_excel(excel_path, sheet_name=args.hoja, nrows=5)

    col_nombre = args.col_nombre or encontrar_columna(
        df_muestra, ["Nombre", "Nombre completo", "Nombre Completo", "Participante", "Alumno"]
    )
    col_matricula = args.col_matricula or encontrar_columna(
        df_muestra, ["Matricula", "Matrícula", "No. Control", "Numero de control", "ID"]
    )

    if not col_nombre:
        print("No se pudo detectar la columna de nombre. Indícala con --col-nombre.")
        return

    print(f"Columna de nombre:    {col_nombre}")
    print(f"Columna de matrícula: {col_matricula or '(no se usará)'}")

    config = Config(plantilla=plantilla_path)

    def on_progreso(i, total, nombre):
        print(f"  [{i}/{total}] {nombre}")

    generados = procesar_excel(
        config,
        excel_path=excel_path,
        carpeta_salida=salida_path,
        col_nombre=col_nombre,
        col_matricula=col_matricula,
        hoja=args.hoja,
        on_progreso=on_progreso,
    )

    n = max(len(generados) - 1, 0)
    print(f"\nListo. {n} constancias generadas en: {salida_path}")
    if generados:
        print(f"PDF combinado: {generados[-1]}")


if __name__ == "__main__":
    main()
