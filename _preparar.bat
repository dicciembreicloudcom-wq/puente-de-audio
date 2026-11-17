@echo off
rem Revisa que el entorno exista y funcione; si no, lo instala (solo la primera vez)
".venv\Scripts\python.exe" -c "import aiohttp, pyaudiowpatch, pycaw, qrcode, zeroconf, av, winrt.windows.media.control, pystray, PIL" >nul 2>&1
if not errorlevel 1 exit /b 0
echo Preparando el programa, espera un momento...
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -m pip install -q -r requirements.txt >nul 2>&1
    ".venv\Scripts\python.exe" -c "import aiohttp, pyaudiowpatch, pycaw, qrcode, zeroconf, av, winrt.windows.media.control, pystray, PIL" >nul 2>&1
    if not errorlevel 1 exit /b 0
    rmdir /s /q .venv
)
python -m venv .venv || (echo No encontre Python. Instala Python desde python.org & exit /b 1)
".venv\Scripts\python.exe" -m pip install -q -r requirements.txt || (echo Fallo la instalacion. & exit /b 1)
exit /b 0
