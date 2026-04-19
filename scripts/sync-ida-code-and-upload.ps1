# 레거시: .ino + secrets.h 만 동기화. 전체 스케치 폴더 + 의존성 준비는 upcode.ps1 권장.
param(
  [string] $PiHost = "",
  [string] $PiHostLan = "192.168.1.22",
  [string] $PiHostWan = "ida.mango-larch.ts.net",
  [string] $PiUser = "dooly",
  [string] $RemoteSketchDir = "/home/dooly/CronusFarm/arduino/CronusFarm",
  [string] $Port = "/dev/ttyACM0",
  [string] $Fqbn = "arduino:renesas_uno:unor4wifi",
  [switch] $StopNodeRedDuringUpload = $false
)

$ErrorActionPreference = "Stop"

function Assert-Command($name) {
  if (-not (Get-Command $name -ErrorAction SilentlyContinue)) {
    throw "필수 명령을 찾지 못했습니다: $name"
  }
}

Assert-Command "ssh"
Assert-Command "scp"

$SshOpts = @("-o", "ConnectTimeout=30", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=accept-new")
. (Join-Path $PSScriptRoot "pi-host-resolve.ps1")
$PiHost = Get-CronusPiHost -PiHost $PiHost -PiHostLan $PiHostLan -PiHostWan $PiHostWan -PiUser $PiUser

$localIno = Join-Path $PSScriptRoot "..\\arduino\\CronusFarm\\CronusFarm.ino"
$localSecrets = Join-Path $PSScriptRoot "..\\arduino\\CronusFarm\\secrets.h"

$localIno = (Resolve-Path $localIno).Path
$localSecrets = (Resolve-Path $localSecrets).Path

if (-not (Test-Path $localIno)) { throw "로컬 .ino 파일이 없습니다: $localIno" }
if (-not (Test-Path $localSecrets)) { throw "로컬 secrets.h 파일이 없습니다: $localSecrets" }

& ssh @SshOpts "${PiUser}@${PiHost}" "mkdir -p '$RemoteSketchDir'"

# 원격에 업로드할 스케치/시크릿 동기화(덮어쓰기) — 폴더명과 동일한 .ino 여야 compile . 가 안정적임
& scp @SshOpts "$localIno" "${PiUser}@${PiHost}:$RemoteSketchDir/CronusFarm.ino"
& scp @SshOpts "$localSecrets" "${PiUser}@${PiHost}:$RemoteSketchDir/secrets.h"

$remoteCmd = "cd '$RemoteSketchDir' && arduino-cli compile -j 4 --fqbn $Fqbn . && arduino-cli upload -p $Port --fqbn $Fqbn ."

# Node-RED 시리얼 점유 때문에 업로드가 막히는 경우가 있어 옵션으로 처리
if ($StopNodeRedDuringUpload) {
  & ssh @SshOpts "${PiUser}@${PiHost}" "sudo -n systemctl stop nodered.service"
}

& ssh @SshOpts "${PiUser}@${PiHost}" "bash -lc '$remoteCmd'"

if ($StopNodeRedDuringUpload) {
  & ssh @SshOpts "${PiUser}@${PiHost}" "sudo -n systemctl start nodered.service"
}

Write-Host "완료: 동기화 + compile + upload"

