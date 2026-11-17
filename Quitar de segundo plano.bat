@echo off
chcp 65001 >nul
cd /d "%~dp0"
del "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\Puente de Audio.lnk" >nul 2>&1
powershell -NoProfile -Command "try { Invoke-WebRequest -UseBasicParsing -Method Post http://127.0.0.1:8765/apagar -TimeoutSec 3 | Out-Null } catch {}"
echo.
echo  Listo. El Puente de Audio se apago y ya no se encendera solo.
echo  (Para volver a activarlo usa "Instalar en segundo plano.bat")
echo.
pause
