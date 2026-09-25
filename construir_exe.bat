@echo off
REM Genera el .exe. Ejecutar en WINDOWS (PyInstaller no cruza de Linux a Windows).
REM Solo hace falta volver a correr esto si cambias launcher.py / actualizador.py
REM o agregas una libreria nueva. El resto se actualiza solo con publicar.py.
cd /d "%~dp0"
if not exist .venv-build (
    py -m venv .venv-build || goto :error
)
call .venv-build\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install pyinstaller pandas openpyxl pypdf pillow numpy tkinterdnd2 || goto :error
pyinstaller constancias.spec --noconfirm --clean || goto :error
echo.
echo Listo: dist\GeneradorConstancias\GeneradorConstancias.exe
echo Comprime la carpeta dist\GeneradorConstancias y pasala a la otra PC.
pause
exit /b 0
:error
echo Ocurrio un error. Revisa los mensajes de arriba.
pause
exit /b 1
