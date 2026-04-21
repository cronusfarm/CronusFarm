@echo off
REM Pi 접속: pi-host-resolve.ps1 (기본 Tailscale, LAN IP 고정 없음). 인자 그대로 upcode.ps1 에 전달.
setlocal
cd /d "%~dp0.."
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0upcode.ps1" %*
exit /b %ERRORLEVEL%
