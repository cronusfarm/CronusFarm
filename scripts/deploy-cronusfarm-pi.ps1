param(
  [string] $PiHost = "",
  [string] $PiHostLan = "",
  [string] $PiHostWan = "ida.mango-larch.ts.net",
  [string] $PiUser = "dooly",
  [string] $RemoteCronusRoot = "/home/dooly/CronusFarm",
  [switch] $SkipArduino,
  [switch] $ApplyNodeRed,
  # Node-RED에서 내보낸 전체 플로우 — 파일이 없을 때만 에러로 강제하고 싶으면 지정
  [switch] $UseNodeRedExport,
  # 분할 JSON(mqtt+dashboard+devflow)만으로 병합 — 편집기 노드 위치는 CronusFarm_NodeRED_flow.json 과 무관
  [switch] $UseSplitFlows,
  [switch] $AutoPort,
  [switch] $StopNodeRedDuringArduinoUpload
)

$ErrorActionPreference = "Stop"

# Windows PowerShell 콘솔에서 한글 로그가 깨지지 않도록 UTF-8 사용
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

# 에이전트/백그라운드 환경에서 SSH 무한 대기 방지 + 비대화형
# 원격 셸: -T(의사 TTY 끔) — Windows PowerShell에서 ssh가 멈추는 경우가 있어 ssh에만 사용
$SshScpOpts = @(
  "-o", "ConnectTimeout=30",
  "-o", "ServerAliveInterval=5",
  "-o", "ServerAliveCountMax=3",
  "-o", "BatchMode=yes",
  "-o", "StrictHostKeyChecking=accept-new"
)
$SshRemoteOpts = @(
  "-T",
  "-o", "ConnectTimeout=30",
  "-o", "ServerAliveInterval=5",
  "-o", "ServerAliveCountMax=3",
  "-o", "BatchMode=yes",
  "-o", "StrictHostKeyChecking=accept-new"
)

. (Join-Path $PSScriptRoot "pi-host-resolve.ps1")
$PiHost = Get-CronusPiHost -PiHost $PiHost -PiHostLan $PiHostLan -PiHostWan $PiHostWan -PiUser $PiUser

$nrDir = Join-Path $PSScriptRoot "..\nodered"
$mqttPath = Join-Path $nrDir "flows_cronusfarm_mqtt.json"
$dashPath = Join-Path $nrDir "flows_cronusfarm_dashboard.json"
$devFlowPath = Join-Path $nrDir "flows_cronusfarm_devflow_flow.json"
if (-not (Test-Path $mqttPath) -or -not (Test-Path $dashPath) -or -not (Test-Path $devFlowPath)) {
  throw "Node-RED 플로우 JSON이 없습니다: $nrDir"
}

if (-not $SkipArduino) {
  Write-Host "=== Arduino: upcode (copy -> Pi compile/upload) ===" -ForegroundColor Cyan
  $up = @{ PiHost = $PiHost; PiUser = $PiUser }
  if ($AutoPort) { $up.AutoPort = $true }
  if ($StopNodeRedDuringArduinoUpload) { $up.StopNodeRedDuringUpload = $true }
  # 1) R4 메인 스케치
  & (Join-Path $PSScriptRoot "upcode.ps1") @up

  # 2) R3 패널 스케치도 함께 업로드(연결되어 있을 때만). 포트는 AutoPort로 탐지.
  Write-Host "=== Arduino: upcode (R3 panel, if connected) ===" -ForegroundColor Cyan
  $upR3 = @{ PiHost = $PiHost; PiUser = $PiUser; Fqbn = "arduino:avr:uno"; LocalSketchDir = (Join-Path $PSScriptRoot "..\\arduino\\CronusFarmPanel"); RemoteSketchDir = "$RemoteCronusRoot/arduino/CronusFarmPanel" }
  if ($AutoPort) { $upR3.AutoPort = $true }
  if ($StopNodeRedDuringArduinoUpload) { $upR3.StopNodeRedDuringUpload = $true }
  try {
    & (Join-Path $PSScriptRoot "upcode.ps1") @upR3
  } catch {
    Write-Host "WARN: R3 panel upload failed (not connected / no port). You can run upcode for R3 only." -ForegroundColor Yellow
  }
} else {
  Write-Host "=== Arduino upload skipped (-SkipArduino) ===" -ForegroundColor Yellow
}

$remoteNodered = "$RemoteCronusRoot/nodered"
$remoteScripts = "$RemoteCronusRoot/scripts"
& ssh @SshRemoteOpts "${PiUser}@${PiHost}" "mkdir -p '$remoteNodered' '$remoteScripts'"

Write-Host "=== Node-RED: sync flow JSON -> $remoteNodered ===" -ForegroundColor Cyan
& scp @SshScpOpts "$mqttPath" "${PiUser}@${PiHost}:$remoteNodered/flows_cronusfarm_mqtt.json"
& scp @SshScpOpts "$dashPath" "${PiUser}@${PiHost}:$remoteNodered/flows_cronusfarm_dashboard.json"
& scp @SshScpOpts "$devFlowPath" "${PiUser}@${PiHost}:$remoteNodered/flows_cronusfarm_devflow_flow.json"
$exportPath = Join-Path $nrDir "CronusFarm_NodeRED_flow.json"
if (Test-Path $exportPath) {
  & scp @SshScpOpts "$exportPath" "${PiUser}@${PiHost}:$remoteNodered/CronusFarm_NodeRED_flow.json"
  Write-Host "Synced: CronusFarm_NodeRED_flow.json (export backup)" -ForegroundColor DarkGray
}

$applySettingsSh = Join-Path $PSScriptRoot "pi-nodered-apply-settings-farm.sh"
if (-not (Test-Path $applySettingsSh)) {
  throw "pi-nodered-apply-settings-farm.sh 없음: $applySettingsSh"
}
& scp @SshScpOpts "$applySettingsSh" "${PiUser}@${PiHost}:$remoteScripts/pi-nodered-apply-settings-farm.sh"
& ssh @SshRemoteOpts "${PiUser}@${PiHost}" "chmod +x '$remoteScripts/pi-nodered-apply-settings-farm.sh'"

$applySh = Join-Path $PSScriptRoot "pi-nodered-apply-merged.sh"
if (-not (Test-Path $applySh)) {
  throw "pi-nodered-apply-merged.sh 없음: $applySh"
}
& scp @SshScpOpts "$applySh" "${PiUser}@${PiHost}:$remoteScripts/pi-nodered-apply-merged.sh"
& ssh @SshRemoteOpts "${PiUser}@${PiHost}" "chmod +x '$remoteScripts/pi-nodered-apply-merged.sh'"

# Windows에서 git/autocrlf 등으로 .sh가 CRLF로 올라가면 Pi에서 "$'\r'" 오류가 납니다.
# 복사 직후 원격에서 LF로 정리합니다(실패해도 계속).
& ssh @SshRemoteOpts "${PiUser}@${PiHost}" "sed -i 's/\r$//' $remoteScripts/*.sh 2>/dev/null || true"

# SQLite 브리지·DDL(systemd §9) — Pi에서 직접 실행할 스크립트가 저장소와 동일하게 올라가도록 함
# 일부 실행 환경에서 $PSScriptRoot 가 null인 케이스를 방어합니다.
$scriptPath = $MyInvocation.MyCommand.Path
$scriptDir = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $scriptPath }
$repoRoot = Split-Path $scriptDir -Parent
$sqlSchema = Join-Path $PSScriptRoot "sql\cronusfarm_record_v1.sql"
$sqliteInit = Join-Path $PSScriptRoot "init_cronusfarm_sqlite.py"
$sqliteBridge = Join-Path $PSScriptRoot "cronusfarm_sqlite_bridge.py"
$systemdBridge = Join-Path $repoRoot "deploy\systemd\cronusfarm-sqlite-bridge.service"
if ((Test-Path $sqliteInit) -or (Test-Path $sqliteBridge) -or (Test-Path $sqlSchema) -or (Test-Path $systemdBridge)) {
  Write-Host "=== SQLite: sync bridge/schema -> $RemoteCronusRoot ===" -ForegroundColor Cyan
  $remoteDeploySystemd = "$RemoteCronusRoot/deploy/systemd"
  & ssh @SshRemoteOpts "${PiUser}@${PiHost}" "mkdir -p '$remoteScripts/sql' '$remoteDeploySystemd'"
  if (Test-Path $sqliteInit) {
    & scp @SshScpOpts "$sqliteInit" "${PiUser}@${PiHost}:$remoteScripts/init_cronusfarm_sqlite.py"
  }
  if (Test-Path $sqliteBridge) {
    & scp @SshScpOpts "$sqliteBridge" "${PiUser}@${PiHost}:$remoteScripts/cronusfarm_sqlite_bridge.py"
  }
  if (Test-Path $sqlSchema) {
    & scp @SshScpOpts "$sqlSchema" "${PiUser}@${PiHost}:$remoteScripts/sql/cronusfarm_record_v1.sql"
  }
  if (Test-Path $systemdBridge) {
    & scp @SshScpOpts "$systemdBridge" "${PiUser}@${PiHost}:$remoteDeploySystemd/cronusfarm-sqlite-bridge.service"
  }
  $piCheckKv = Join-Path $PSScriptRoot "pi-check-sqlite-kv.sh"
  if (Test-Path $piCheckKv) {
    & scp @SshScpOpts "$piCheckKv" "${PiUser}@${PiHost}:$remoteScripts/pi-check-sqlite-kv.sh"
    & ssh @SshRemoteOpts "${PiUser}@${PiHost}" "chmod +x '$remoteScripts/pi-check-sqlite-kv.sh'"
  }
  $piAiSetup = Join-Path $PSScriptRoot "pi-ai-setup.sh"
  if (Test-Path $piAiSetup) {
    & scp @SshScpOpts "$piAiSetup" "${PiUser}@${PiHost}:$remoteScripts/pi-ai-setup.sh"
    & ssh @SshRemoteOpts "${PiUser}@${PiHost}" "chmod +x '$remoteScripts/pi-ai-setup.sh'"
  }
  if ((Test-Path $sqliteBridge) -or (Test-Path $sqliteInit)) {
    # sudo/systemctl이 환경에 따라 멈추는 경우가 있어 timeout으로 보호
    & ssh @SshRemoteOpts "${PiUser}@${PiHost}" "timeout 12s sudo systemctl restart cronusfarm-sqlite-bridge.service 2>/dev/null || true"
  }
}

# 텔레그램 플로우용 systemd EnvironmentFile(비밀값은 Pi의 /etc/cronusfarm/nodered-telegram.env 만)
$tgInstall = Join-Path $PSScriptRoot "pi-install-nodered-telegram-env.sh"
$tgDropIn = Join-Path $repoRoot "deploy\systemd\nodered.service.d\10-cronusfarm-telegram.conf"
$tgEnvEx = Join-Path $repoRoot "deploy\env\nodered-telegram.env.example"
if ((Test-Path $tgInstall) -and (Test-Path $tgDropIn) -and (Test-Path $tgEnvEx)) {
  Write-Host "=== Telegram: systemd drop-in/env example -> $RemoteCronusRoot ===" -ForegroundColor Cyan
  $remoteNrDrop = "$RemoteCronusRoot/deploy/systemd/nodered.service.d"
  $remoteDeployEnv = "$RemoteCronusRoot/deploy/env"
  & ssh @SshRemoteOpts "${PiUser}@${PiHost}" "mkdir -p '$remoteNrDrop' '$remoteDeployEnv'"
  & scp @SshScpOpts "$tgDropIn" "${PiUser}@${PiHost}:$remoteNrDrop/10-cronusfarm-telegram.conf"
  & scp @SshScpOpts "$tgEnvEx" "${PiUser}@${PiHost}:$remoteDeployEnv/nodered-telegram.env.example"
  & scp @SshScpOpts "$tgInstall" "${PiUser}@${PiHost}:$remoteScripts/pi-install-nodered-telegram-env.sh"
  & ssh @SshRemoteOpts "${PiUser}@${PiHost}" "chmod +x '$remoteScripts/pi-install-nodered-telegram-env.sh'"
  # CRLF -> LF (Windows copy) before executing on Pi
  & ssh @SshRemoteOpts "${PiUser}@${PiHost}" "sed -i 's/\r$//' '$remoteScripts/pi-install-nodered-telegram-env.sh' 2>/dev/null || true"
}

$grafanaDashDir = Join-Path $repoRoot "grafana\dashboards"
if (Test-Path $grafanaDashDir) {
  $gfJson = @(Get-ChildItem -Path $grafanaDashDir -Filter "*.json" -File -ErrorAction SilentlyContinue)
  if ($gfJson.Count -gt 0) {
    Write-Host "=== Grafana: dashboards JSON -> /var/lib/grafana/dashboards (sudo) ===" -ForegroundColor Cyan
    foreach ($gf in $gfJson) {
      & scp @SshScpOpts "$($gf.FullName)" "${PiUser}@${PiHost}:/tmp/$($gf.Name)"
    }
    $copyParts = @()
    foreach ($gf in $gfJson) {
      $bn = $gf.Name
      $copyParts += "sudo cp /tmp/$bn /var/lib/grafana/dashboards/$bn"
    }
    $remoteGfCmd = ($copyParts -join " && ") + " && sudo chown grafana:grafana /var/lib/grafana/dashboards/*.json 2>/dev/null; sudo systemctl reload grafana-server 2>/dev/null || sudo systemctl restart grafana-server 2>/dev/null || true"
    & ssh @SshRemoteOpts "${PiUser}@${PiHost}" $remoteGfCmd
    if ($LASTEXITCODE -ne 0) {
      Write-Host "WARN: Grafana copy/reload failed (sudo/path). Manual: sudo cp /tmp/*.json /var/lib/grafana/dashboards/" -ForegroundColor Yellow
    }
  }
}

$gfDropIn = Join-Path $repoRoot "deploy\grafana\systemd\grafana-server.service.d\99-cronusfarm-panels.conf"
if (Test-Path $gfDropIn) {
  Write-Host "=== Grafana: allow Text panel iframe(systemd drop-in) ===" -ForegroundColor Cyan
  & scp @SshScpOpts "$gfDropIn" "${PiUser}@${PiHost}:/tmp/99-cronusfarm-panels.conf"
  $gfSysCmd = "sudo mkdir -p /etc/systemd/system/grafana-server.service.d && sudo cp /tmp/99-cronusfarm-panels.conf /etc/systemd/system/grafana-server.service.d/ && sudo systemctl daemon-reload && (sudo systemctl restart grafana-server 2>/dev/null || sudo systemctl restart grafana 2>/dev/null || true)"
  & ssh @SshRemoteOpts "${PiUser}@${PiHost}" $gfSysCmd
  if ($LASTEXITCODE -ne 0) {
    Write-Host "WARN: Grafana systemd drop-in failed. Check GF_PANELS_DISABLE_SANITIZE_HTML on Pi." -ForegroundColor Yellow
  }
}

if (-not $ApplyNodeRed) {
  Write-Host "OK: saved nodered/*.json and apply scripts on Pi." -ForegroundColor Green
  Write-Host "Auto apply: .\\scripts\\deploy-cronusfarm-pi.ps1 -ApplyNodeRed" -ForegroundColor Green
  exit 0
}

Write-Host "=== Node-RED: merge then POST via Admin API (backup flows.json) ===" -ForegroundColor Cyan
if ($UseSplitFlows) {
  Write-Host "Merge source: split 3 files only (editor layout may differ from CronusFarm_NodeRED_flow.json)" -ForegroundColor Yellow
} elseif (Test-Path $exportPath) {
  Write-Host "Merge source: CronusFarm_NodeRED_flow.json (keep export node layout) — default" -ForegroundColor Cyan
} else {
  Write-Host "Merge source: split 3 files (no export JSON)" -ForegroundColor Yellow
}
Write-Host "NOTE: running Node-RED flow will be fully replaced by repo JSON." -ForegroundColor Yellow
Write-Host "Also: patch settings.js paths(/farm) + restart service(if possible)" -ForegroundColor Yellow

& ssh @SshRemoteOpts "${PiUser}@${PiHost}" "if [[ -x '$remoteScripts/pi-install-nodered-telegram-env.sh' ]]; then sed -i 's/\r$//' '$remoteScripts/pi-install-nodered-telegram-env.sh' 2>/dev/null || true; bash '$remoteScripts/pi-install-nodered-telegram-env.sh'; else echo 'skip: pi-install-nodered-telegram-env.sh missing'; fi"
if ($LASTEXITCODE -ne 0) {
  Write-Host "WARN: telegram env systemd apply failed (sudo/path). On Pi: bash ~/CronusFarm/scripts/pi-install-nodered-telegram-env.sh" -ForegroundColor Yellow
}

& ssh @SshRemoteOpts "${PiUser}@${PiHost}" "bash '$remoteScripts/pi-nodered-apply-settings-farm.sh'"
if ($LASTEXITCODE -ne 0) {
  throw "settings.js 패치 실패(원격 종료 코드: $LASTEXITCODE)"
}
& ssh @SshRemoteOpts "${PiUser}@${PiHost}" "sudo -n systemctl restart nodered.service" 2>$null
if ($LASTEXITCODE -ne 0) {
  Write-Host "WARN: nodered restart failed (continue). On Pi: sudo systemctl restart nodered.service" -ForegroundColor Yellow
}

# 로컬에서 merge_nodered_deploy.py 실행 → 분할 dashboard → 내보내기 동기화 후 merged-deploy.json 생성
# Windows에서는 PATH에 python 이 없고 py 런처만 있는 경우가 있어 둘 다 허용한다.
$mergeScript = Join-Path $PSScriptRoot "merge_nodered_deploy.py"
$mergedLocal = Join-Path $nrDir "merged-deploy.json"
$mergeArgs = @($mergeScript)
if ($UseSplitFlows) {
  $mergeArgs += "--use-split"
} elseif ($UseNodeRedExport -and -not (Test-Path $exportPath)) {
  throw "CronusFarm_NodeRED_flow.json 없음: $exportPath — Node-RED에서 내보내 저장하거나 -UseSplitFlows 로 분할 병합을 사용하세요."
}
if (Get-Command python -ErrorAction SilentlyContinue) {
  & python @mergeArgs
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
  & py -3 @mergeArgs
} else {
  throw "필수: merge 스크립트 실행용 Python 이 필요합니다. PATH 에 python 또는 py(Windows Python Launcher) 가 있어야 합니다."
}
if ($LASTEXITCODE -ne 0) {
  throw "merge_nodered_deploy.py 실패 (종료 코드: $LASTEXITCODE)"
}
if (-not (Test-Path $mergedLocal)) {
  throw "merged-deploy.json 이 생성되지 않았습니다: $mergedLocal"
}
$mergedRemote = "$remoteNodered/merged-deploy.json"
& scp @SshScpOpts "$mergedLocal" "${PiUser}@${PiHost}:$mergedRemote"
& ssh @SshRemoteOpts "${PiUser}@${PiHost}" "bash '$remoteScripts/pi-nodered-apply-merged.sh' '$mergedRemote'"
if ($LASTEXITCODE -ne 0) {
  throw "Node-RED POST /flows 실패 (원격 종료 코드: $LASTEXITCODE). Pi에서 merged JSON·node-red-log 확인."
}

if ($SkipArduino) {
  Write-Host "OK: Node-RED flow deployed (Arduino skipped)" -ForegroundColor Green
} else {
  Write-Host "OK: Arduino(upcode) + Node-RED flow deployed" -ForegroundColor Green
}
