# Pi + Arduino + Node-RED 일괄 적용 (git 없는 Pi)
param(
  [string] $PiHost = "",
  [string] $PiUser = "dooly",
  [switch] $SkipUpload
)
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "pi-host-resolve.ps1")
$PiHost = Get-CronusPiHost -PiHost $PiHost -PiUser $PiUser
$repo = Split-Path $PSScriptRoot -Parent

Write-Host "=== patch devflow + merge ===" -ForegroundColor Cyan
& python (Join-Path $repo "scripts\patch_devflow_hybrid_usb.py")
& python (Join-Path $repo "scripts\merge_nodered_deploy.py") --use-split

& (Join-Path $PSScriptRoot "pi-sync-usb-primary.ps1") -PiHost $PiHost -PiUser $PiUser -SkipUpload:$SkipUpload

Write-Host "OK: Pi + Arduino + /ui 개발현황 4장" -ForegroundColor Green
