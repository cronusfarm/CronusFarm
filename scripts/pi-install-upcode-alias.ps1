# Pi에 upcode.sh / pi-arduino-build.sh 복사, chmod, ~/.bashrc 에 upcode 별칭 추가
param(
  [string] $PiHost = "",
  [string] $PiHostLan = "192.168.1.22",
  [string] $PiHostWan = "ida.mango-larch.ts.net",
  [string] $PiUser = "dooly"
)
$ErrorActionPreference = "Stop"
$SshOpts = @("-o", "ConnectTimeout=25", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=accept-new")
. (Join-Path $PSScriptRoot "pi-host-resolve.ps1")
$PiHost = Get-CronusPiHost -PiHost $PiHost -PiHostLan $PiHostLan -PiHostWan $PiHostWan -PiUser $PiUser

$up = Join-Path $PSScriptRoot "upcode.sh"
$bd = Join-Path $PSScriptRoot "pi-arduino-build.sh"
if (-not (Test-Path $up)) { throw "없음: $up" }
if (-not (Test-Path $bd)) { throw "없음: $bd" }

& ssh @SshOpts "${PiUser}@${PiHost}" "mkdir -p `$HOME/CronusFarm/scripts"
& scp @SshOpts $up "${PiUser}@${PiHost}:CronusFarm/scripts/upcode.sh"
& scp @SshOpts $bd "${PiUser}@${PiHost}:CronusFarm/scripts/pi-arduino-build.sh"
$boot = Join-Path $PSScriptRoot "pi-bootstrap-upcode.sh"
if (Test-Path $boot) {
  & scp @SshOpts $boot "${PiUser}@${PiHost}:pi-bootstrap-upcode.sh"
}
& ssh @SshOpts "${PiUser}@${PiHost}" "chmod +x `$HOME/CronusFarm/scripts/upcode.sh `$HOME/CronusFarm/scripts/pi-arduino-build.sh"

# Pi에서 pi-repair-upcode.sh 로 복구(문법 검사 + alias 블록)
$repair = Join-Path $PSScriptRoot "pi-repair-upcode.sh"
if (-not (Test-Path $repair)) { throw "없음: $repair" }
& scp @SshOpts $repair "${PiUser}@${PiHost}:CronusFarm/scripts/pi-repair-upcode.sh"
& ssh @SshOpts "${PiUser}@${PiHost}" "chmod +x `$HOME/CronusFarm/scripts/pi-repair-upcode.sh && bash `$HOME/CronusFarm/scripts/pi-repair-upcode.sh"

Write-Host "완료: $PiUser@${PiHost} — 새 셸에서 upcode 또는: bash ~/CronusFarm/scripts/upcode.sh" -ForegroundColor Green
