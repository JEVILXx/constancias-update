"""
Sistema de actualizaciones remotas
==================================
Este archivo forma parte del LANZADOR (el .exe). No se actualiza solo: lo
que se actualiza remotamente son los paquetes de código (core/, gui/ y
cualquier paquete nuevo que agregues).

Cómo funciona
-------------
1. Tú publicas una versión con  publicar.py  (genera un .zip + version.json).
2. Subes esos dos archivos a un lugar accesible desde la otra PC (GitHub,
   un servidor web, o una carpeta compartida / Google Drive / OneDrive).
3. Al abrir el programa (y cada 30 min si se queda abierto), el lanzador lee
   version.json. Si hay una versión más nueva: la descarga, verifica su
   SHA-256, la descomprime en  <datos>/updates/v<versión>/  y la usa en el
   siguiente arranque.
4. Si la versión nueva truena al arrancar, se marca como "mala" y se vuelve
   automáticamente a la versión que viene dentro del .exe.

Dónde se dice de dónde bajar las actualizaciones: actualizaciones.json
  {"origen": "https://.../version.json"}     (URL)
  {"origen": "G:\\Mi unidad\\Constancias"}   (carpeta o archivo version.json)
"""

from __future__ import annotations

import hashlib
import importlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import time
import traceback
import zipfile
from pathlib import Path
from urllib.parse import urljoin
from urllib.request import Request, urlopen

# Versión de "contrato" entre el lanzador y los paquetes. Sube este número
# solo si un cambio EXIGE reinstalar el .exe (p. ej. una librería nueva).
# Un paquete puede pedir un mínimo con  "min_launcher"  en version.json.
LAUNCHER_API = 1

NOMBRE_APP = "GeneradorConstancias"
CONFIG_NOMBRE = "actualizaciones.json"


# ----------------------------------------------------------------------
# Rutas
# ----------------------------------------------------------------------
def empaquetado() -> bool:
    return bool(getattr(sys, "frozen", False))


def dir_base() -> Path:
    """Código que viene DENTRO del .exe (o el proyecto, si corre desde fuente)."""
    if empaquetado():
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)) / "app_base"
    return Path(__file__).resolve().parent


def carpeta_datos() -> Path:
    """Datos del usuario + actualizaciones descargadas (sobreviven a las actualizaciones)."""
    forzada = os.environ.get("CONSTANCIAS_DATOS")
    if forzada:
        ruta = Path(forzada)
    elif empaquetado():
        if os.name == "nt":
            raiz = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local"))
        else:
            raiz = Path(os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local" / "share"))
        ruta = raiz / NOMBRE_APP
    else:
        ruta = Path(__file__).resolve().parent
    ruta.mkdir(parents=True, exist_ok=True)
    return ruta


def dir_updates() -> Path:
    d = carpeta_datos() / "updates"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _dir_version(version: str) -> Path:
    return dir_updates() / f"v{version}"


def registrar(mensaje: str) -> None:
    """Bitácora simple en <datos>/actualizaciones.log (útil cuando el .exe no tiene consola)."""
    try:
        with open(carpeta_datos() / "actualizaciones.log", "a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {mensaje}\n")
    except OSError:
        pass


# ----------------------------------------------------------------------
# Versiones y estado
# ----------------------------------------------------------------------
def version_tupla(v: str) -> tuple:
    partes = [int(x) for x in re.findall(r"\d+", str(v))] or [0]
    while len(partes) < 3:
        partes.append(0)
    return tuple(partes)


def leer_version(carpeta: Path) -> str:
    try:
        return str(json.loads((carpeta / "version.json").read_text(encoding="utf-8"))["version"])
    except Exception:
        return "0.0.0"


def _estado_path() -> Path:
    return dir_updates() / "estado.json"


def leer_estado() -> dict:
    try:
        est = json.loads(_estado_path().read_text(encoding="utf-8"))
        if isinstance(est, dict):
            est.setdefault("malas", [])
            return est
    except Exception:
        pass
    return {"activa": None, "malas": []}


def _guardar_estado(est: dict) -> None:
    tmp = _estado_path().with_suffix(".tmp")
    tmp.write_text(json.dumps(est, indent=2), encoding="utf-8")
    os.replace(tmp, _estado_path())


def marcar_mala(version: str) -> None:
    est = leer_estado()
    if version not in est["malas"]:
        est["malas"].append(version)
    if est.get("activa") == version:
        est["activa"] = None
    _guardar_estado(est)
    registrar(f"Versión {version} marcada como mala; se usará la del instalador.")


def _paquete_valido(carpeta: Path) -> bool:
    return (carpeta / "gui" / "__init__.py").exists() and (carpeta / "core" / "__init__.py").exists()


def resolver_codigo() -> tuple[Path, str]:
    """Elige qué código ejecutar: la versión descargada si es más nueva que la
    del .exe (y no está marcada como mala); si no, la del .exe."""
    base = dir_base()
    v_base = leer_version(base)
    est = leer_estado()
    activa = est.get("activa")
    if activa and activa not in est["malas"]:
        d = _dir_version(activa)
        if _paquete_valido(d) and version_tupla(activa) > version_tupla(v_base):
            return d, activa
    return base, v_base


def version_actual() -> str:
    """Versión que está EN EJECUCIÓN ahora mismo."""
    return os.environ.get("CONSTANCIAS_VERSION") or resolver_codigo()[1]


# ----------------------------------------------------------------------
# Configuración y lectura de manifiesto / paquete
# ----------------------------------------------------------------------
def leer_config() -> dict:
    for carpeta in (carpeta_datos(), dir_base()):
        ruta = carpeta / CONFIG_NOMBRE
        if ruta.exists():
            try:
                cfg = json.loads(ruta.read_text(encoding="utf-8"))
                return {k: v for k, v in cfg.items() if not str(k).startswith("_")}
            except Exception:
                registrar(f"{ruta} está mal escrito (JSON inválido).")
    return {}


def _es_url(texto: str) -> bool:
    return texto.lower().startswith(("http://", "https://"))


def _leer_bytes(origen: str, timeout: float, progreso=None) -> bytes:
    if _es_url(origen):
        req = Request(origen, headers={"User-Agent": f"{NOMBRE_APP}-Updater", "Cache-Control": "no-cache"})
        with urlopen(req, timeout=timeout) as r:
            total = int(r.headers.get("Content-Length") or 0)
            partes, leido = [], 0
            while True:
                trozo = r.read(65536)
                if not trozo:
                    break
                partes.append(trozo)
                leido += len(trozo)
                if progreso:
                    progreso(leido, total)
            return b"".join(partes)
    datos = Path(origen).read_bytes()
    if progreso:
        progreso(len(datos), len(datos))
    return datos


def _ruta_manifiesto(origen: str) -> str:
    if _es_url(origen):
        return origen if not origen.endswith("/") else origen + "version.json"
    p = Path(origen)
    return str(p / "version.json") if p.is_dir() else str(p)


def _resolver_relativa(ruta_manifiesto: str, url: str) -> str:
    if _es_url(url):
        return url
    if _es_url(ruta_manifiesto):
        return urljoin(ruta_manifiesto, url)
    return str(Path(ruta_manifiesto).parent / url)


def _extraer_seguro(datos: bytes, destino: Path) -> None:
    raiz = destino.resolve()
    with zipfile.ZipFile(io.BytesIO(datos)) as z:
        for m in z.infolist():
            objetivo = (destino / m.filename).resolve()
            if objetivo != raiz and raiz not in objetivo.parents:
                raise ValueError(f"Ruta sospechosa dentro del paquete: {m.filename}")
        z.extractall(destino)


def _limpiar_versiones_viejas(conservar: set[str]) -> None:
    try:
        for d in dir_updates().iterdir():
            if d.is_dir() and d.name.startswith("v") and d.name not in conservar:
                shutil.rmtree(d, ignore_errors=True)
            elif d.is_dir() and d.name.startswith("_tmp_"):
                shutil.rmtree(d, ignore_errors=True)
    except OSError:
        pass


# ----------------------------------------------------------------------
# Buscar e instalar
# ----------------------------------------------------------------------
def buscar_e_instalar(progreso=None, al_encontrar=None) -> dict:
    """
    Revisa si hay una versión más nueva y, si la hay, la descarga e instala
    (se usará en el próximo arranque). Nunca lanza excepciones.

    Devuelve {"estado": ..., "version": ..., "notas": ..., "mensaje": ...}
    con estado en: sin_config | al_dia | instalada | incompatible | error
    """
    try:
        cfg = leer_config()
        origen = str(cfg.get("origen", "")).strip()
        if not origen or cfg.get("activo", True) is False:
            return {"estado": "sin_config", "mensaje": "No hay un origen de actualizaciones configurado."}
        timeout = float(cfg.get("timeout_segundos", 6))

        ruta_man = _ruta_manifiesto(origen)
        man = json.loads(_leer_bytes(ruta_man, timeout).decode("utf-8-sig"))
        nueva = str(man["version"])

        if int(man.get("min_launcher", 1)) > LAUNCHER_API:
            return {"estado": "incompatible", "version": nueva,
                    "mensaje": f"La versión {nueva} necesita un instalador (.exe) más nuevo."}

        est = leer_estado()
        base_v = leer_version(dir_base())
        actual = max([base_v, est.get("activa") or "0.0.0"], key=version_tupla)
        if version_tupla(nueva) <= version_tupla(actual) or nueva in est["malas"]:
            return {"estado": "al_dia", "version": actual,
                    "mensaje": f"Ya tienes la última versión ({actual})."}

        sha_esperado = str(man.get("sha256", "")).lower().strip()
        if not sha_esperado:
            return {"estado": "error", "version": nueva,
                    "mensaje": "El version.json no trae sha256; se rechaza por seguridad."}

        if al_encontrar:
            al_encontrar(nueva)
        ruta_zip = _resolver_relativa(ruta_man, str(man["url"]))
        datos = _leer_bytes(ruta_zip, max(timeout, 60), progreso)
        if hashlib.sha256(datos).hexdigest() != sha_esperado:
            return {"estado": "error", "version": nueva,
                    "mensaje": "El paquete descargado está dañado (no coincide el SHA-256)."}

        tmp = dir_updates() / f"_tmp_{nueva}"
        shutil.rmtree(tmp, ignore_errors=True)
        tmp.mkdir(parents=True)
        _extraer_seguro(datos, tmp)
        if not _paquete_valido(tmp):
            shutil.rmtree(tmp, ignore_errors=True)
            return {"estado": "error", "version": nueva,
                    "mensaje": "El paquete no trae las carpetas core/ y gui/."}

        final = _dir_version(nueva)
        shutil.rmtree(final, ignore_errors=True)
        os.replace(tmp, final)

        est["activa"] = nueva
        _guardar_estado(est)
        en_uso = os.environ.get("CONSTANCIAS_VERSION", "")
        _limpiar_versiones_viejas({f"v{nueva}", f"v{en_uso}"})
        registrar(f"Actualización {actual} -> {nueva} instalada.")
        return {"estado": "instalada", "version": nueva, "notas": man.get("notas", ""),
                "mensaje": f"Versión {nueva} descargada e instalada."}
    except Exception as e:
        registrar(f"Error al buscar actualizaciones: {e!r}")
        return {"estado": "error", "mensaje": f"No se pudo consultar/instalar la actualización: {e}"}


# ----------------------------------------------------------------------
# Arranque de la aplicación (con vuelta atrás si la versión nueva truena)
# ----------------------------------------------------------------------
def _purgar_modulos(carpeta: Path) -> None:
    raiz = str(carpeta)
    for nombre, mod in list(sys.modules.items()):
        ruta = getattr(mod, "__file__", None)
        if ruta and str(ruta).startswith(raiz):
            del sys.modules[nombre]
    importlib.invalidate_caches()


def _cerrar_ventana_huerfana() -> None:
    try:
        import tkinter
        raiz = getattr(tkinter, "_default_root", None)
        if raiz is not None:
            raiz.destroy()
    except Exception:
        pass


def _instanciar(carpeta: Path, version: str):
    ruta = str(carpeta)
    sys.path.insert(0, ruta)
    os.environ["CONSTANCIAS_CODIGO_DIR"] = ruta
    os.environ["CONSTANCIAS_VERSION"] = version
    try:
        importlib.invalidate_caches()
        gui = importlib.import_module("gui")
        return gui.ConstanciasGUI()
    except BaseException:
        if ruta in sys.path:
            sys.path.remove(ruta)
        raise


def cargar_aplicacion():
    """Crea la ventana principal con la mejor versión disponible. Devuelve (app, versión)."""
    codigo, version = resolver_codigo()
    base = dir_base()
    try:
        return _instanciar(codigo, version), version
    except Exception:
        if codigo == base:
            raise
        registrar(f"La versión {version} falló al arrancar:\n{traceback.format_exc()}")
        marcar_mala(version)
        _cerrar_ventana_huerfana()
        _purgar_modulos(codigo)
        return _instanciar(base, leer_version(base)), leer_version(base)


def preparar_entorno() -> None:
    """Crea la carpeta de datos y copia la plantilla de ejemplo la primera vez."""
    datos = carpeta_datos()
    os.environ["CONSTANCIAS_DATOS"] = str(datos)
    plantilla_base = dir_base() / "plantilla.jpeg"
    if plantilla_base.exists() and not (datos / "plantilla.jpeg").exists():
        try:
            shutil.copy2(plantilla_base, datos / "plantilla.jpeg")
        except OSError:
            pass


def reiniciar() -> None:
    """Abre otra instancia del programa (que ya cargará la versión nueva)."""
    env = dict(os.environ)
    env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"  # PyInstaller >= 6.9: relanzar un .exe desde sí mismo
    for k in ("_MEIPASS2", "CONSTANCIAS_VERSION", "CONSTANCIAS_CODIGO_DIR"):
        env.pop(k, None)
    if empaquetado():
        cmd = [sys.executable]
    else:
        cmd = [sys.executable, str(Path(__file__).resolve().parent / "launcher.py")]
    subprocess.Popen(cmd, env=env, close_fds=True)
