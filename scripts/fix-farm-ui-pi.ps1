# farm-ui 403 복구: dist 재배포 + nginx 설정 reload
param(
  [string] $PiHostWan = "ida.mango-larch.ts.net",
  [string] $PiUser = "dooly",
  [string] $RemoteCronusRoot = "/home/dooly/CronusFarm"
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "pi-host-resolve.ps1")
$PiHost = Get-CronusPiHost -PiHostWan $PiHostWan -PiUser $PiUser
$SshOpts = @("-o", "ConnectTimeout=30", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=accept-new")

$repoRoot = Split-Path $PSScriptRoot -Parent
$farmUiDist = Join-Path $repoRoot "farm-ui\dist"

Write-Host "[Pi] $PiUser@$PiHost — farm-ui dist 복구" -ForegroundColor Cyan

& (Join-Path $PSScriptRoot "build-farm-ui.ps1")
if (-not (Test-Path (Join-Path $farmUiDist "index.html"))) {
  throw "farm-ui dist/index.html 없음"
}

function Invoke-Checked {
  param([scriptblock] $Block, [string] $Label)
  & $Block
  if ($LASTEXITCODE -ne 0) { throw "$Label failed (exit $LASTEXITCODE)" }
}

$remoteDist = "$RemoteCronusRoot/farm-ui/dist"
Invoke-Checked { ssh @SshOpts "${PiUser}@${PiHost}" "rm -rf '$remoteDist' && mkdir -p '$remoteDist'" } "ssh mkdir"
Invoke-Checked { scp @SshOpts -r "$farmUiDist\*" "${PiUser}@${PiHost}:$remoteDist/" } "scp dist"
& (Join-Path $PSScriptRoot "Invoke-FarmUiPostDeploy.ps1") -PiHost $PiHost -PiUser $PiUser -RemoteDist $remoteDist -FarmUiDistLocal $farmUiDist -ScriptDir $PSScriptRoot -SshOpts $SshOpts
Invoke-Checked { scp @SshOpts (Join-Path $repoRoot "deploy\nginx\cronusfarm-nodered.conf") "${PiUser}@${PiHost}:/tmp/cronusfarm-nodered.conf" } "scp nginx conf"

$remoteNginx = "/etc/nginx/sites-available/cronusfarm-nodered.conf"
Invoke-Checked {
  ssh @SshOpts "${PiUser}@${PiHost}" "set -e; sudo cp /tmp/cronusfarm-nodered.conf '$remoteNginx'; sudo chmod o+rX /home/dooly /home/dooly/CronusFarm /home/dooly/CronusFarm/farm-ui /home/dooly/CronusFarm/farm-ui/dist 2>/dev/null || true; bash /tmp/pi-fix-farm-ui-perms.sh; sudo nginx -t; sudo systemctl reload nginx; ls -la '$remoteDist/assets' | head -3"
} "ssh nginx reload"

Write-Host "[OK] http://${PiHost}/farm/ui/ 확인 (Ctrl+F5)" -ForegroundColor Green
