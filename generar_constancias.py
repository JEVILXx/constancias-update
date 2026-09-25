#!/usr/bin/env python3
"""
Generador de Constancias UAdeO — versión de consola
------------------------------------------------------
USO:
    python3 generar_constancias.py datos.xlsx
    python3 generar_constancias.py datos.xlsx --col-nombre "Nombre completo" --col-matricula "No. Control"

Para la versión con ventana/interfaz gráfica usa: constancias_gui.py
"""

import argparse
import sys
from pathlib import Path

from core import Config, encontrar_columna, procesar_excel
import pandas as pd

CARPETA = Path(__file__).parent
PLANTILLA = CARPETA / "plantilla.jpeg"
SALIDA = CARPETA / "salida"


def main():
    parser = argparse.ArgumentParser(description="Genera constancias en PDF a partir de un Excel.")
    parser.add_argument("excel", help="Ruta al archivo Excel (.xlsx) con los datos de los participantes")
    parser.add_argument("--hoja", default=0, help="Nombre o índice de la hoja de Excel (default: la primera)")
    parser.add_argument("--col-nombre", default=None, help="Nombre exacto de la columna con el nombre completo")
    parser.add_argument("--col-matricula", default=None, help="Nombre exacto de la columna con la matrícula")
    parser.add_argument("--plantilla", default=str(PLANTILLA), help="Ruta a la imagen de la plantilla")
    parser.add_argument("--salida", default=str(SALIDA), help="Carpeta donde se guardan los PDFs")
    args = parser.parse_args()

    plantilla = Path(args.plantilla)
    if not plantilla.exists():
        sys.exit(f"ERROR: no se encontró la plantilla en {plantilla}")

    df_preview = pd.read_excel(args.excel, sheet_name=args.hoja)
    col_nombre = args.col_nombre or encontrar_columna(
        df_preview, ["Nombre", "Nombre completo", "Nombre Completo", "Participante", "Alumno"]
    )
    col_matricula = args.col_matricula or encontrar_columna(
        df_preview, ["Matricula", "Matrícula", "No. Control", "Numero de control", "ID"]
    )

    if col_nombre is None:
        sys.exit(
            "ERROR: no encontré una columna de nombre. Columnas disponibles: "
            + ", ".join(map(str, df_preview.columns))
            + "\nUsa --col-nombre 'NombreDeTuColumna' para indicarla."
        )

    print(f"Columna de nombre:    {col_nombre}")
    print(f"Columna de matrícula: {col_matricula or '(no encontrada / no se usará)'}")

    config = Config(plantilla=plantilla)

    def reportar(i, total, nombre):
        print(f"  [{i}/{total}] {nombre}")

    generados = procesar_excel(
        config,
        excel_path=Path(args.excel),
        carpeta_salida=Path(args.salida),
        col_nombre=col_nombre,
        col_matricula=col_matricula,
        hoja=args.hoja,
        on_progreso=reportar,
    )

    if not generados:
        sys.exit("No se generó ninguna constancia: revisa que el Excel tenga datos.")

    print(f"\nListo. {len(generados) - 1} constancias generadas en: {args.salida}")
    print(f"PDF combinado: {generados[-1]}")


if __name__ == "__main__":
    main()
