@echo off
REM R3 패널용: upcode-panel.ps1 호출 (기본 FQBN=arduino:avr:uno)
setlocal
cd /d "%~dp0.."
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0upcode-panel.ps1" %*
exit /b %ERRORLEVEL%
