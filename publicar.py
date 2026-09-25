#!/usr/bin/env python3
"""
Publicar una versión nueva (se ejecuta en TU computadora, la de desarrollo)
==========================================================================
Empaqueta tu código actual (core/, gui/ y cualquier paquete nuevo con
__init__.py) en un .zip y genera el version.json que leen las otras PCs.

Uso:
    python publicar.py --notas "Panel de reportes nuevo"      # 1.0.0 -> 1.0.1
    python publicar.py --minor --notas "..."                  # 1.0.1 -> 1.1.0
    python publicar.py --major                                # 1.1.0 -> 2.0.0
    python publicar.py --version 3.2.1
    python publicar.py --destino "G:\\Mi unidad\\Constancias"  # además copia todo ahí

Resultado en la carpeta  publicar/ :
    version.json
    paquetes/app-<versión>.zip
Sube esas dos cosas (respetando la carpeta paquetes/) al mismo lugar que
pusiste en actualizaciones.json -> "origen".

NUNCA se empaquetan los archivos .json de datos (cuentas de correo, etc.),
el .venv ni la carpeta de salida.
"""

import argparse
import hashlib
import json
import shutil
import sys
import time
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
EXCLUIR_DIRS = {".venv", "venv", "__pycache__", "publicar", "updates", "build", "dist",
                "salida", ".git", ".idea", ".vscode"}
LAUNCHER_API_MINIMA = 1


def paquetes() -> list[Path]:
    return [d for d in sorted(RAIZ.iterdir())
            if d.is_dir() and d.name not in EXCLUIR_DIRS and not d.name.startswith(".")
            and (d / "__init__.py").exists()]


def leer_version() -> str:
    try:
        return json.loads((RAIZ / "version.json").read_text(encoding="utf-8"))["version"]
    except Exception:
        return "1.0.0"


def subir(v: str, nivel: str) -> str:
    a, b, c = (list(map(int, v.split("."))) + [0, 0])[:3]
    if nivel == "major":
        return f"{a + 1}.0.0"
    if nivel == "minor":
        return f"{a}.{b + 1}.0"
    return f"{a}.{b}.{c + 1}"


def archivos_de(paquete: Path):
    for f in sorted(paquete.rglob("*")):
        partes = set(f.relative_to(RAIZ).parts)
        if not f.is_file() or "__pycache__" in partes or f.suffix == ".pyc" or f.name.startswith("."):
            continue
        yield f


def main():
    ap = argparse.ArgumentParser(description="Empaqueta una versión nueva para las actualizaciones remotas.")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--minor", action="store_true", help="sube el número de en medio (1.0.3 -> 1.1.0)")
    g.add_argument("--major", action="store_true", help="sube el primer número (1.4.0 -> 2.0.0)")
    g.add_argument("--version", help="pon una versión exacta, p. ej. 2.0.0")
    ap.add_argument("--notas", default="", help="qué cambió (se le muestra al usuario)")
    ap.add_argument("--destino", help="carpeta a la que copiar version.json y paquetes/ (Drive, red, etc.)")
    ap.add_argument("--min-launcher", type=int, default=LAUNCHER_API_MINIMA,
                    help="mínimo de LAUNCHER_API requerido (súbelo si el cambio exige un .exe nuevo)")
    args = ap.parse_args()

    pkgs = paquetes()
    if not {"core", "gui"} <= {p.name for p in pkgs}:
        sys.exit("No encuentro las carpetas core/ y gui/ junto a publicar.py.")

    anterior = leer_version()
    nueva = args.version or subir(anterior, "major" if args.major else "minor" if args.minor else "patch")
    (RAIZ / "version.json").write_text(json.dumps({"version": nueva}), encoding="utf-8")

    salida = RAIZ / "publicar"
    (salida / "paquetes").mkdir(parents=True, exist_ok=True)
    zip_path = salida / "paquetes" / f"app-{nueva}.zip"
    n = 0
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(RAIZ / "version.json", "version.json")
        for p in pkgs:
            for f in archivos_de(p):
                z.write(f, f.relative_to(RAIZ).as_posix())
                n += 1

    sha = hashlib.sha256(zip_path.read_bytes()).hexdigest()
    manifiesto = {
        "version": nueva,
        "url": f"paquetes/{zip_path.name}",
        "sha256": sha,
        "notas": args.notas,
        "min_launcher": args.min_launcher,
        "fecha": time.strftime("%Y-%m-%d %H:%M"),
    }
    (salida / "version.json").write_text(json.dumps(manifiesto, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Versión {anterior} -> {nueva}")
    print(f"Paquetes incluidos: {', '.join(p.name for p in pkgs)} ({n} archivos)")
    print(f"Listo: {zip_path}  ({zip_path.stat().st_size / 1024:.0f} KB)")

    if args.destino:
        d = Path(args.destino)
        (d / "paquetes").mkdir(parents=True, exist_ok=True)
        shutil.copy2(zip_path, d / "paquetes" / zip_path.name)
        shutil.copy2(salida / "version.json", d / "version.json")  # el manifiesto va al final
        print(f"Copiado a: {d}")
    else:
        print(f"\nSube  {salida / 'version.json'}  y  {salida / 'paquetes'}  a tu origen de actualizaciones.")


if __name__ == "__main__":
    main()
