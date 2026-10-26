@echo off
rem Arranca el módulo en segundo plano, sin ventana de consola.
cd /d "%~dp0"
start "" ".venv\Scripts\pythonw.exe" -m flux_perf
