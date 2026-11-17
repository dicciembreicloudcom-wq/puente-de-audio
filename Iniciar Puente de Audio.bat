@echo off
chcp 65001 >nul
title Puente de Audio
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
call _preparar.bat || (pause & exit /b 1)
".venv\Scripts\python.exe" -u servidor.py
pause
