# Pi에 진단 스크립트를 복사(SC P)한 뒤 SSH로 실행 — Pi에 ~/CronusFarm 이 없어도 동작
# 사용: powershell -ExecutionPolicy Bypass -File .\scripts\run-pi-diagnose-ui.ps1
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
. "$here\pi-host-resolve.ps1"
$h = Get-CronusPiHost
$target = "dooly@${h}"

Write-Host "=== SCP → ${target}:/tmp/ (pi-diagnose-ui, ensure-upstream) ===" -ForegroundColor Cyan
& scp -o ConnectTimeout=20 -o BatchMode=yes `
  "$here\pi-diagnose-ui.sh" `
  "$here\pi-nodered-ensure-upstream-for-nginx.sh" `
  "${target}:/tmp/"

Write-Host "=== SSH: bash /tmp/pi-diagnose-ui.sh ===" -ForegroundColor Cyan
ssh -o ConnectTimeout=25 -o BatchMode=yes $target "chmod +x /tmp/pi-diagnose-ui.sh /tmp/pi-nodered-ensure-upstream-for-nginx.sh 2>/dev/null; bash /tmp/pi-diagnose-ui.sh"
$code = $LASTEXITCODE
if ($code -ne 0) {
  Write-Host "원격 실행 실패 (exit $code)." -ForegroundColor Yellow
  exit $code
}
