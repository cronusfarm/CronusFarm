# Pi 에 Mosquitto(0.0.0.0:1883)·SQLite HTTP 브리지(systemd, 0.0.0.0:18766) 적용.
# SSH 키 기반 로그인 필요(BatchMode). 비밀번호만 쓰는 경우: 아래 $SshScpOpts 에서 BatchMode 줄 제거.
#
# 사용 (저장소 루트에서):
#   .\scripts\pi-apply-mosquitto-sqlite-bridge.ps1
#   .\scripts\pi-apply-mosquitto-sqlite-bridge.ps1 -PiHost ida.mango-larch.ts.net -PiUser dooly -RemoteCronusRoot /home/dooly/CronusFarm

param(
  [string] $PiHost = "",
  [string] $PiHostLan = "",
  [string] $PiHostWan = "ida.mango-larch.ts.net",
  [string] $PiUser = "dooly",
  [string] $RemoteCronusRoot = "/home/dooly/CronusFarm",
  # SQLite DB 파일 (Pi Node-RED userDir 기본 가정)
  [string] $SqlitePath = ""
)

$ErrorActionPreference = "Stop"

try {
  if ($PSVersionTable.PSVersion.Major -lt 6) {
    chcp 65001 | Out-Null
  }
  $utf8 = New-Object System.Text.UTF8Encoding $false
  [Console]::OutputEncoding = $utf8
  [Console]::InputEncoding = $utf8
  $OutputEncoding = $utf8
} catch { }

function Assert-Command($name) {
  if (-not (Get-Command $name -ErrorAction SilentlyContinue)) {
    throw "필수 명령을 찾지 못했습니다: $name"
  }
}
Assert-Command "ssh"
Assert-Command "scp"

$scriptDir = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
$repoRoot = Split-Path $scriptDir -Parent

. (Join-Path $scriptDir "pi-host-resolve.ps1")
$PiHost = Get-CronusPiHost -PiHost $PiHost -PiHostLan $PiHostLan -PiHostWan $PiHostWan -PiUser $PiUser

$SshScpOpts = @(
  "-o", "ConnectTimeout=45",
  "-o", "ServerAliveInterval=5",
  "-o", "ServerAliveCountMax=4",
  "-o", "BatchMode=yes",
  "-o", "StrictHostKeyChecking=accept-new"
)
$SshRemoteOpts = @(
  "-T",
  "-o", "ConnectTimeout=45",
  "-o", "ServerAliveInterval=5",
  "-o", "ServerAliveCountMax=4",
  "-o", "BatchMode=yes",
  "-o", "StrictHostKeyChecking=accept-new"
)

if ([string]::IsNullOrWhiteSpace($SqlitePath)) {
  $SqlitePath = "/home/$PiUser/.node-red/cronusfarm.sqlite"
}

$mosquittoDropin = Join-Path $repoRoot "deploy\mosquitto\conf.d\cronusfarm.conf"
if (-not (Test-Path $mosquittoDropin)) {
  throw "파일 없음: $mosquittoDropin"
}

$bridgePy = Join-Path $scriptDir "cronusfarm_sqlite_bridge.py"
if (-not (Test-Path $bridgePy)) {
  throw "파일 없음: $bridgePy"
}

$remoteRunner = Join-Path $scriptDir "pi-apply-mosquitto-sqlite-bridge-remote.sh"
if (-not (Test-Path $remoteRunner)) {
  throw "파일 없음: $remoteRunner"
}

$svcBody = @"
[Unit]
Description=CronusFarm SQLite HTTP Bridge (Node-RED ingest)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
Environment=CRONUSFARM_SQLITE_PATH=$SqlitePath
Environment=CRONUSFARM_BRIDGE_HOST=0.0.0.0
Environment=CRONUSFARM_BRIDGE_PORT=18766
ExecStart=/usr/bin/python3 $RemoteCronusRoot/scripts/cronusfarm_sqlite_bridge.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
"@

$tmpSvc = Join-Path ([System.IO.Path]::GetTempPath()) ("cronusfarm-sqlite-bridge-" + [Guid]::NewGuid().ToString("n") + ".service")
try {
  $svcUtf8NoBom = New-Object System.Text.UTF8Encoding $false
  [System.IO.File]::WriteAllText($tmpSvc, $svcBody.TrimEnd() + "`n", $svcUtf8NoBom)
} catch {
  throw "임시 systemd 유닛 작성 실패: $_"
}

$remoteTarget = "${PiUser}@${PiHost}"
Write-Host "=== Pi 적용: $remoteTarget ===" -ForegroundColor Cyan
Write-Host "RemoteCronusRoot: $RemoteCronusRoot"
Write-Host "SqlitePath: $SqlitePath"
Write-Host ""

Write-Host "--- scp: mosquitto drop-in, systemd 유닛, 브리지 스크립트, 원격 실행 스크립트 ---" -ForegroundColor DarkCyan
& scp @SshScpOpts "$mosquittoDropin" "${remoteTarget}:~/cronusfarm_apply_mosquitto.conf"
if ($LASTEXITCODE -ne 0) { throw "scp mosquitto conf 실패" }

& scp @SshScpOpts "$tmpSvc" "${remoteTarget}:~/cronusfarm_sqlite_bridge.service.new"
if ($LASTEXITCODE -ne 0) { throw "scp systemd 실패" }

& ssh @SshRemoteOpts "${remoteTarget}" "mkdir -p '$RemoteCronusRoot/scripts'"
if ($LASTEXITCODE -ne 0) { throw "ssh mkdir 실패" }

& scp @SshScpOpts "$bridgePy" "${remoteTarget}:$RemoteCronusRoot/scripts/cronusfarm_sqlite_bridge.py"
if ($LASTEXITCODE -ne 0) { throw "scp bridge py 실패" }

& scp @SshScpOpts "$remoteRunner" "${remoteTarget}:~/pi-apply-mosquitto-sqlite-bridge-remote.sh"
if ($LASTEXITCODE -ne 0) { throw "scp remote runner 실패" }

Write-Host "--- ssh: 원격 적용 스크립트 실행 ---" -ForegroundColor DarkCyan
& ssh @SshRemoteOpts "${remoteTarget}" "chmod +x ~/pi-apply-mosquitto-sqlite-bridge-remote.sh; sed -i 's/\r`$//' ~/pi-apply-mosquitto-sqlite-bridge-remote.sh 2>/dev/null || true; sed -i 's/\r`$//' '$RemoteCronusRoot/scripts/cronusfarm_sqlite_bridge.py' 2>/dev/null || true; bash ~/pi-apply-mosquitto-sqlite-bridge-remote.sh"
$sshExit = $LASTEXITCODE
Remove-Item -Force $tmpSvc -ErrorAction SilentlyContinue

if ($sshExit -ne 0) {
  throw "원격 적용 스크립트 종료 코드 $sshExit"
}

Write-Host ""
Write-Host "Pi 적용 완료." -ForegroundColor Green
