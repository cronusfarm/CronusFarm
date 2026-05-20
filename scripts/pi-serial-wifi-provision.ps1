# Windows → Pi SSH 로 R4 USB WiFi 프로비저닝 실행
param(
  [string] $PiHost = "14.32.231.191",
  [string] $PiUser = "dooly",
  [string] $PiSerial = "",
  [switch] $Clear,
  [switch] $Status
)

$ErrorActionPreference = "Stop"
$here = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
$repo = Split-Path $here -Parent

$remoteArgs = @()
if ($PiSerial) { $remoteArgs += "--port", $PiSerial }
if ($Clear) { $remoteArgs += "--clear" }
if ($Status) { $remoteArgs += "--status" }

Write-Host "=== Pi R4 WiFi serial provision ($PiUser@${PiHost}) ===" -ForegroundColor Cyan
scp -o ConnectTimeout=30 -o BatchMode=yes `
  "$repo\scripts\pi-serial-wifi-provision.py" `
  "$repo\scripts\pi-serial-wifi-provision.sh" `
  "$repo\arduino\CronusFarm\CronusFarm.ino" `
  "$repo\arduino\CronusFarm\cf_schedule_types.h" `
  "${PiUser}@${PiHost}:/tmp/cf_wifi_prov/"

$argStr = ($remoteArgs | ForEach-Object { "'$_'" }) -join " "
ssh -o ConnectTimeout=30 -o BatchMode=yes "${PiUser}@${PiHost}" @"
set -e
cp -f /tmp/cf_wifi_prov/pi-serial-wifi-provision.py ~/CronusFarm/scripts/
cp -f /tmp/cf_wifi_prov/pi-serial-wifi-provision.sh ~/CronusFarm/scripts/
chmod +x ~/CronusFarm/scripts/pi-serial-wifi-provision.sh
cp -f /tmp/cf_wifi_prov/CronusFarm.ino ~/CronusFarm/arduino/CronusFarm/
cp -f /tmp/cf_wifi_prov/cf_schedule_types.h ~/CronusFarm/arduino/CronusFarm/ 2>/dev/null || true
export FQBN=arduino:renesas_uno:unor4wifi
bash ~/CronusFarm/scripts/pi-arduino-build.sh ~/CronusFarm/arduino/CronusFarm
python3 ~/CronusFarm/scripts/pi-serial-wifi-provision.py $argStr
"@

Write-Host "OK: done" -ForegroundColor Green
