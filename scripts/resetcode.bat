@echo off
REM Pi R4 소프트 리셋만 (upcode = 리셋+업로드)
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0resetcode.ps1" %*
