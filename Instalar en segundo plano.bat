@echo off
chcp 65001 >nul
title Puente de Audio - Instalar
cd /d "%~dp0"
call _preparar.bat || (pause & exit /b 1)

rem Acceso directo en la carpeta Inicio de Windows: arranca solo, sin ventana, al prender la laptop
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$d = (Get-Location).Path; $s = (New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Startup') + '\Puente de Audio.lnk');" ^
  "$s.TargetPath = \"$env:SystemRoot\System32\conhost.exe\";" ^
  "$s.Arguments = '--headless \"' + $d + '\.venv\Scripts\python.exe\" servidor.py --fondo --sin-navegador';" ^
  "$s.WorkingDirectory = $d; $s.Description = 'Puente de Audio'; $s.WindowStyle = 7; $s.Save()"

start "" "%SystemRoot%\System32\conhost.exe" --headless "%~dp0.venv\Scripts\python.exe" servidor.py --fondo --sin-navegador
echo.
echo  Listo. El Puente de Audio ya esta encendido (icono azul junto al reloj)
echo  y se encendera solo cada vez que prendas la laptop.
echo.
pause
