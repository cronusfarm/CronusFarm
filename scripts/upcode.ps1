param(

  [string] $PiHost = "",

  [string] $PiHostLan = "192.168.0.222",

  [string] $PiHostWan = "ida.mango-larch.ts.net",

  [string] $PiUser = "dooly",

  # 로컬 스케치 폴더(지정 안 하면 기본: arduino/CronusFarm)
  [string] $LocalSketchDir = "",

  [string] $RemoteSketchDir = "/home/dooly/CronusFarm/arduino/CronusFarm",

  [string] $Port = "/dev/ttyACM0",

  [string] $Fqbn = "arduino:renesas_uno:unor4wifi",

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

  throw "Required command not found: $name (Install Windows OpenSSH client)"

  }

}



Assert-Command "ssh"

Assert-Command "scp"

. (Join-Path $PSScriptRoot "pi-host-resolve.ps1")
$PiHost = Get-CronusPiHost -PiHost $PiHost -PiHostLan $PiHostLan -PiHostWan $PiHostWan -PiUser $PiUser

$SshOpts = @("-o", "ConnectTimeout=30", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=accept-new")

$localSketchDir = $LocalSketchDir
if ([string]::IsNullOrWhiteSpace($localSketchDir)) {
  $localSketchDir = Join-Path $PSScriptRoot "..\\arduino\\CronusFarm"
}

$localSketchDir = (Resolve-Path $localSketchDir).Path



if (-not (Test-Path $localSketchDir)) {

  throw "Local sketch dir not found: $localSketchDir"

}



# Windows에서 Split-Path이 '\'를 섞으면 Pi(리눅스) 경로가 깨지므로 원격은 항상 POSIX로 맞춘다.

$RemoteSketchUnix = ($RemoteSketchDir -replace '\\', '/').TrimEnd('/')

if ($RemoteSketchUnix -notmatch '^(.*)/arduino/[^/]+$') {
  throw "RemoteSketchDir must be .../arduino/<SketchName>: $RemoteSketchDir"
}
# /home/dooly/CronusFarm/arduino/<SketchName> -> /home/dooly/CronusFarm
$RemoteFarmRoot = $Matches[1]

$RemoteScriptsDir = "$RemoteFarmRoot/scripts"



Write-Host "Local sketch dir : $localSketchDir"
Write-Host "Remote sketch dir: $RemoteSketchUnix"
Write-Host "Remote scripts   : $RemoteScriptsDir"



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

    Write-Host "WARN: failed to stop nodered (continue). sudo may be missing." -ForegroundColor Yellow

  }

}



# AutoPort: 두 번째 인자 생략 -> pi 스크립트가 ttyACM 자동 탐지
# CRLF가 남아 있어도 동작하도록 bash로 명시 실행(쉐뱅 exec 경로 회피)

if ($AutoPort) {
  & ssh @SshOpts "${PiUser}@${PiHost}" "bash -lc 'export FQBN=$Fqbn; bash $RemoteScriptsDir/pi-arduino-build.sh $RemoteSketchUnix'"
} else {
  & ssh @SshOpts "${PiUser}@${PiHost}" "bash -lc 'export FQBN=$Fqbn; bash $RemoteScriptsDir/pi-arduino-build.sh $RemoteSketchUnix $Port'"
}



if ($StopNodeRedDuringUpload) {

  & ssh @SshOpts "${PiUser}@${PiHost}" "sudo -n systemctl start nodered.service" 2>$null

}



Write-Host "OK: remote prep(core/lib) + compile + upload"


