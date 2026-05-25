# USB serial primary + /ui devflow → Pi 동기화·적용 (git 없는 Pi 대응)
param(
  [string] $PiHost = "",
  [string] $PiUser = "dooly",
  [switch] $SkipUpload,
  [switch] $SkipNodeRed
)
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "pi-host-resolve.ps1")
$PiHost = Get-CronusPiHost -PiHost $PiHost -PiUser $PiUser
$SshOpts = @("-o", "ConnectTimeout=30", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=accept-new")
$repo = Split-Path $PSScriptRoot -Parent
$remote = "/home/dooly/CronusFarm"
$files = @(
  "scripts/cronusfarm_r4_serial_daemon.py",
  "scripts/cronusfarm_mqtt_wifi_recover.py",
  "scripts/cronusfarm_sqlite_bridge.py",
  "scripts/pi-install-r4-serial-primary.sh",
  "scripts/pi-upload-r4.sh",
  "scripts/pi-recover-r4-usb.sh",
  "scripts/pi-apply-usb-primary-all.sh",
  "scripts/pi-ensure-secrets-http-backup.sh",
  "scripts/pi-mqtt-publish-rtc-to-r4.sh",
  "scripts/_pi_mqtt_diag.sh",
  "deploy/systemd/cronusfarm-r4-serial.service",
  "deploy/env/r4-serial.env.example",
  "arduino/CronusFarm/CronusFarm.ino",
  "arduino/CronusFarm/secrets.h.example",
  "nodered/merged-deploy.json",
  "nodered/flows_cronusfarm_devflow_flow.json"
)
foreach ($rel in $files) {
  $local = Join-Path $repo $rel
  if (-not (Test-Path $local)) { Write-Warning "skip missing $rel"; continue }
  $rdir = "$remote/$(Split-Path $rel -Parent)"
  & ssh @SshOpts "${PiUser}@${PiHost}" "mkdir -p '$rdir'"
  & scp @SshOpts $local "${PiUser}@${PiHost}:$remote/$rel"
}
if (-not $SkipUpload) {
  & ssh @SshOpts "${PiUser}@${PiHost}" "tr -d '\r' < '$remote/scripts/pi-apply-usb-primary-all.sh' > /tmp/cf-apply.lf && mv /tmp/cf-apply.lf '$remote/scripts/pi-apply-usb-primary-all.sh' && chmod +x '$remote/scripts/'*.sh '$remote/scripts/'*.py 2>/dev/null; bash '$remote/scripts/pi-apply-usb-primary-all.sh'"
} else {
  & ssh @SshOpts "${PiUser}@${PiHost}" "bash '$remote/scripts/pi-install-r4-serial-primary.sh'; curl -s -m 5 http://127.0.0.1:18767/health || true"
}
if (-not $SkipNodeRed) {
  & ssh @SshOpts "${PiUser}@${PiHost}" "cp '$remote/nodered/merged-deploy.json' ~/.node-red/flows.json && sudo systemctl restart nodered.service"
}
Write-Host "OK: Pi USB primary sync" -ForegroundColor Green
