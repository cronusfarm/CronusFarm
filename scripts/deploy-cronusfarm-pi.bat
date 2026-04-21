@echo off
REM Arduino + Node-RED 배포. LAN 고정 없음 — 기본은 Tailscale 호스트.
setlocal
cd /d "%~dp0.."
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0deploy-cronusfarm-pi.ps1" %*
exit /b %ERRORLEVEL%
