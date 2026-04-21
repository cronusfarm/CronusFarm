param(
  [string] $PiHost = "",
  [string] $PiHostLan = "",
  [string] $PiHostWan = "ida.mango-larch.ts.net",
  [string] $PiUser = "dooly",
  [string] $RemoteSketchDir = "/home/dooly/CronusFarm/arduino/CronusFarmPanel",
  [string] $Port = "/dev/ttyACM0",
  [string] $Fqbn = "arduino:avr:uno",
  [switch] $AutoPort,
  [switch] $StopNodeRedDuringUpload
)

$ErrorActionPreference = "Stop"

try {
  if ($PSVersionTable.PSVersion.Major -lt 6) { chcp 65001 | Out-Null }
  $u8 = New-Object System.Text.UTF8Encoding $false
  [Console]::OutputEncoding = $u8
  [Console]::InputEncoding = $u8
  $OutputEncoding = $u8
} catch { }

function Assert-Command($name) {
  if (-not (Get-Command $name -ErrorAction SilentlyContinue)) {
    throw "필수 명령을 찾지 못했습니다: $name (Windows에 OpenSSH 클라이언트가 설치되어 있는지 확인하세요)"
  }
}

Assert-Command "ssh"
Assert-Command "scp"

. (Join-Path $PSScriptRoot "pi-host-resolve.ps1")
$PiHost = Get-CronusPiHost -PiHost $PiHost -PiHostLan $PiHostLan -PiHostWan $PiHostWan -PiUser $PiUser

$SshOpts = @("-o", "ConnectTimeout=30", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=accept-new")

$localSketchDir = Join-Path $PSScriptRoot "..\\arduino\\CronusFarmPanel"
$localSketchDir = (Resolve-Path $localSketchDir).Path

if (-not (Test-Path $localSketchDir)) {
  throw "로컬 스케치 폴더가 없습니다: $localSketchDir"
}

$RemoteSketchUnix = ($RemoteSketchDir -replace '\\', '/').TrimEnd('/')
if ($RemoteSketchUnix -notmatch '/arduino/CronusFarmPanel$') {
  throw "RemoteSketchDir는 .../arduino/CronusFarmPanel 로 끝나야 합니다: $RemoteSketchDir"
}
$RemoteFarmRoot = $RemoteSketchUnix -replace '/arduino/CronusFarmPanel$', ''
$RemoteScriptsDir = "$RemoteFarmRoot/scripts"

Write-Host "로컬 스케치 폴더(R3 패널): $localSketchDir"
Write-Host "원격 스케치 폴더: $RemoteSketchUnix"
Write-Host "원격 스크립트 폴더: $RemoteScriptsDir"

& ssh @SshOpts "${PiUser}@${PiHost}" "mkdir -p '$RemoteSketchUnix' '$RemoteScriptsDir'"

$piBuild = Join-Path $PSScriptRoot "pi-arduino-build.sh"
if (-not (Test-Path $piBuild)) {
  throw "pi-arduino-build.sh 가 없습니다: $piBuild"
}

& scp @SshOpts "$piBuild" "${PiUser}@${PiHost}:$RemoteScriptsDir/pi-arduino-build.sh"
& ssh @SshOpts "${PiUser}@${PiHost}" "chmod +x '$RemoteScriptsDir/pi-arduino-build.sh'"

& scp @SshOpts -r "$localSketchDir/*" "${PiUser}@${PiHost}:$RemoteSketchUnix/"

if ($StopNodeRedDuringUpload) {
  & ssh @SshOpts "${PiUser}@${PiHost}" "sudo -n systemctl stop nodered.service" 2>$null
  if ($LASTEXITCODE -ne 0) {
    Write-Host "경고: nodered 중지 실패(무시하고 계속). sudo 권한이 없을 수 있습니다." -ForegroundColor Yellow
  }
}

if ($AutoPort) {
  & ssh @SshOpts "${PiUser}@${PiHost}" "bash -lc 'export FQBN=$Fqbn; bash $RemoteScriptsDir/pi-arduino-build.sh $RemoteSketchUnix'"
} else {
  & ssh @SshOpts "${PiUser}@${PiHost}" "bash -lc 'export FQBN=$Fqbn; bash $RemoteScriptsDir/pi-arduino-build.sh $RemoteSketchUnix $Port'"
}

if ($StopNodeRedDuringUpload) {
  & ssh @SshOpts "${PiUser}@${PiHost}" "sudo -n systemctl start nodered.service" 2>$null
}

Write-Host "완료: 원격 준비(core) + CronusFarmPanel compile + upload"
