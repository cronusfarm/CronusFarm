param(
  [string] $PiHost = "",
  [string] $PiHostLan = "",
  [string] $PiHostWan = "ida.mango-larch.ts.net",
  [string] $PiUser = "dooly",
  [string] $RemoteFarmRoot = "/home/dooly/CronusFarm"
)

$ErrorActionPreference = "Stop"

function Assert-Command($name) {
  if (-not (Get-Command $name -ErrorAction SilentlyContinue)) {
    throw "필수 명령을 찾지 못했습니다: $name"
  }
}

Assert-Command "ssh"
Assert-Command "scp"

. (Join-Path $PSScriptRoot "pi-host-resolve.ps1")
$PiHost = Get-CronusPiHost -PiHost $PiHost -PiHostLan $PiHostLan -PiHostWan $PiHostWan -PiUser $PiUser

$SshOpts = @("-o", "ConnectTimeout=30", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=accept-new")

$localMega = Join-Path $PSScriptRoot "..\nodered\dashboard\mega.html"
$localMega = (Resolve-Path $localMega).Path

$remoteMega = "$RemoteFarmRoot/nodered/dashboard/mega.html"

Write-Host "로컬 mega.html: $localMega"

& ssh @SshOpts "${PiUser}@${PiHost}" "mkdir -p '${RemoteFarmRoot}/nodered/dashboard' '${RemoteFarmRoot}/scripts'"

& scp @SshOpts "$localMega" "${PiUser}@${PiHost}:${remoteMega}"

$applyLocal = Join-Path $PSScriptRoot "pi-nodered-dashboard-apply-mega.sh"
if (-not (Test-Path $applyLocal)) {
  throw "스크립트 없음: $applyLocal"
}
& scp @SshOpts "$applyLocal" "${PiUser}@${PiHost}:${RemoteFarmRoot}/scripts/pi-nodered-dashboard-apply-mega.sh"
& ssh @SshOpts "${PiUser}@${PiHost}" "chmod +x '${RemoteFarmRoot}/scripts/pi-nodered-dashboard-apply-mega.sh'"

& ssh @SshOpts "${PiUser}@${PiHost}" "bash -lc '${RemoteFarmRoot}/scripts/pi-nodered-dashboard-apply-mega.sh ${remoteMega}'"

Write-Host "완료: Pi node-red-dashboard dist/mega.html 동기화 (/ui/mega.html)" -ForegroundColor Green
