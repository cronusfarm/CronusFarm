# Windows → Pi: UNO R4 WiFi 소프트 리셋만 (upcode 와 달리 compile/upload 없음)
param(
  [string] $PiHost = "",
  [string] $PiHostLan = "",
  [string] $PiHostWan = "ida.mango-larch.ts.net",
  [string] $PiUser = "dooly",
  [string] $RemoteScriptsDir = "/home/dooly/CronusFarm/scripts",
  [string] $Port = "",
  [switch] $AutoPort,
  [switch] $StopNodeRedDuringReset
)

$ErrorActionPreference = "Stop"

function Assert-Command($name) {
  if (-not (Get-Command $name -ErrorAction SilentlyContinue)) {
    throw "필요 명령 없음: $name"
  }
}

Assert-Command "ssh"
Assert-Command "scp"

. (Join-Path $PSScriptRoot "pi-host-resolve.ps1")
$PiHost = Get-CronusPiHost -PiHost $PiHost -PiHostLan $PiHostLan -PiHostWan $PiHostWan -PiUser $PiUser

$SshOpts = @("-o", "ConnectTimeout=30", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=accept-new")
$resetSh = Join-Path $PSScriptRoot "pi-reset-r4.sh"
if (-not (Test-Path $resetSh)) {
  throw "pi-reset-r4.sh 없음: $resetSh"
}

$RemoteScriptsUnix = ($RemoteScriptsDir -replace '\\', '/').TrimEnd('/')

& scp @SshOpts $resetSh "${PiUser}@${PiHost}:$RemoteScriptsUnix/pi-reset-r4.sh"
& ssh @SshOpts "${PiUser}@${PiHost}" "chmod +x '$RemoteScriptsUnix/pi-reset-r4.sh'"

if ($StopNodeRedDuringReset) {
  & ssh @SshOpts "${PiUser}@${PiHost}" "sudo -n systemctl stop nodered.service" 2>$null
  if ($LASTEXITCODE -ne 0) {
    Write-Host "WARN: nodered 중지 실패(계속). 시리얼 점유 시 fuser 로 해제 시도." -ForegroundColor Yellow
  }
}

if ($AutoPort -or [string]::IsNullOrWhiteSpace($Port)) {
  & ssh @SshOpts "${PiUser}@${PiHost}" "bash '$RemoteScriptsUnix/pi-reset-r4.sh'"
} else {
  & ssh @SshOpts "${PiUser}@${PiHost}" "bash '$RemoteScriptsUnix/pi-reset-r4.sh' '$Port'"
}

if ($StopNodeRedDuringReset) {
  & ssh @SshOpts "${PiUser}@${PiHost}" "sudo -n systemctl start nodered.service" 2>$null
}

Write-Host "OK: Pi R4 소프트 리셋만 완료 (업로드 없음). tele MQTT 확인하세요." -ForegroundColor Green
