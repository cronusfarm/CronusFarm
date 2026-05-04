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
  Write-Host "=== Arduino: upcode (복사 -> Pi에서 compile/upload) ===" -ForegroundColor Cyan
  $up = @{ PiHost = $PiHost; PiUser = $PiUser }
  if ($AutoPort) { $up.AutoPort = $true }
  if ($StopNodeRedDuringArduinoUpload) { $up.StopNodeRedDuringUpload = $true }
  & (Join-Path $PSScriptRoot "upcode.ps1") @up
} else {
  Write-Host "=== Arduino 업로드 생략 (-SkipArduino) ===" -ForegroundColor Yellow
}

$remoteNodered = "$RemoteCronusRoot/nodered"
$remoteScripts = "$RemoteCronusRoot/scripts"
& ssh @SshRemoteOpts "${PiUser}@${PiHost}" "mkdir -p '$remoteNodered' '$remoteScripts'"

Write-Host "=== Node-RED: 플로우 JSON 동기화 -> $remoteNodered ===" -ForegroundColor Cyan
& scp @SshScpOpts "$mqttPath" "${PiUser}@${PiHost}:$remoteNodered/flows_cronusfarm_mqtt.json"
& scp @SshScpOpts "$dashPath" "${PiUser}@${PiHost}:$remoteNodered/flows_cronusfarm_dashboard.json"
& scp @SshScpOpts "$devFlowPath" "${PiUser}@${PiHost}:$remoteNodered/flows_cronusfarm_devflow_flow.json"
$exportPath = Join-Path $nrDir "CronusFarm_NodeRED_flow.json"
if (Test-Path $exportPath) {
  & scp @SshScpOpts "$exportPath" "${PiUser}@${PiHost}:$remoteNodered/CronusFarm_NodeRED_flow.json"
  Write-Host "동기화: CronusFarm_NodeRED_flow.json (내보내기 백업)" -ForegroundColor DarkGray
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

# SQLite 브리지·DDL(systemd §9) — Pi에서 직접 실행할 스크립트가 저장소와 동일하게 올라가도록 함
$repoRoot = Split-Path $PSScriptRoot -Parent
$sqlSchema = Join-Path $PSScriptRoot "sql\cronusfarm_record_v1.sql"
$sqliteInit = Join-Path $PSScriptRoot "init_cronusfarm_sqlite.py"
$sqliteBridge = Join-Path $PSScriptRoot "cronusfarm_sqlite_bridge.py"
$systemdBridge = Join-Path $repoRoot "deploy\systemd\cronusfarm-sqlite-bridge.service"
if ((Test-Path $sqliteInit) -or (Test-Path $sqliteBridge) -or (Test-Path $sqlSchema) -or (Test-Path $systemdBridge)) {
  Write-Host "=== SQLite 브리지·스키마 동기화 -> $RemoteCronusRoot ===" -ForegroundColor Cyan
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
  if ((Test-Path $sqliteBridge) -or (Test-Path $sqliteInit)) {
    # sudo/systemctl이 환경에 따라 멈추는 경우가 있어 timeout으로 보호
    & ssh @SshRemoteOpts "${PiUser}@${PiHost}" "timeout 12s sudo systemctl restart cronusfarm-sqlite-bridge.service 2>/dev/null || true"
  }
}

$grafanaDashDir = Join-Path $repoRoot "grafana\dashboards"
if (Test-Path $grafanaDashDir) {
  $gfJson = @(Get-ChildItem -Path $grafanaDashDir -Filter "*.json" -File -ErrorAction SilentlyContinue)
  if ($gfJson.Count -gt 0) {
    Write-Host "=== Grafana: 대시보드 JSON -> /var/lib/grafana/dashboards (sudo) ===" -ForegroundColor Cyan
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
      Write-Host "경고: Grafana 대시보드 복사/리로드 실패(sudo·경로 확인). Pi에서 수동: sudo cp /tmp/*.json /var/lib/grafana/dashboards/" -ForegroundColor Yellow
    }
  }
}

$gfDropIn = Join-Path $repoRoot "deploy\grafana\systemd\grafana-server.service.d\99-cronusfarm-panels.conf"
if (Test-Path $gfDropIn) {
  Write-Host "=== Grafana: Text 패널 iframe 허용(systemd drop-in) ===" -ForegroundColor Cyan
  & scp @SshScpOpts "$gfDropIn" "${PiUser}@${PiHost}:/tmp/99-cronusfarm-panels.conf"
  $gfSysCmd = "sudo mkdir -p /etc/systemd/system/grafana-server.service.d && sudo cp /tmp/99-cronusfarm-panels.conf /etc/systemd/system/grafana-server.service.d/ && sudo systemctl daemon-reload && (sudo systemctl restart grafana-server 2>/dev/null || sudo systemctl restart grafana 2>/dev/null || true)"
  & ssh @SshRemoteOpts "${PiUser}@${PiHost}" $gfSysCmd
  if ($LASTEXITCODE -ne 0) {
    Write-Host "경고: Grafana systemd drop-in 적용 실패. Pi에서 수동으로 GF_PANELS_DISABLE_SANITIZE_HTML 설정을 확인하세요." -ForegroundColor Yellow
  }
}

if (-not $ApplyNodeRed) {
  Write-Host "완료: Pi에 nodered/*.json 및 적용 스크립트 저장됨." -ForegroundColor Green
  Write-Host "Node-RED에 자동 반영: .\scripts\deploy-cronusfarm-pi.ps1 -ApplyNodeRed" -ForegroundColor Green
  exit 0
}

Write-Host "=== Node-RED: 플로우 병합 후 API 배포 (기존 flows.json 백업) ===" -ForegroundColor Cyan
if ($UseSplitFlows) {
  Write-Host "병합 소스: 분할 3파일만 (편집기 배치는 CronusFarm_NodeRED_flow.json 과 다를 수 있음)" -ForegroundColor Yellow
} elseif (Test-Path $exportPath) {
  Write-Host "병합 소스: CronusFarm_NodeRED_flow.json (내보내기·노드 위치 유지) — 기본 동작" -ForegroundColor Cyan
} else {
  Write-Host "병합 소스: 분할 3파일 (내보내기 JSON 없음)" -ForegroundColor Yellow
}
Write-Host "주의: 실행 중인 Node-RED **전체 플로우**가 저장소 내용으로 교체됩니다." -ForegroundColor Yellow
Write-Host "추가: Node-RED 경로 루트(/farm) 적용(settings.js 패치) + 서비스 재시작(가능 시)" -ForegroundColor Yellow

& ssh @SshRemoteOpts "${PiUser}@${PiHost}" "bash '$remoteScripts/pi-nodered-apply-settings-farm.sh'"
if ($LASTEXITCODE -ne 0) {
  throw "settings.js 패치 실패(원격 종료 코드: $LASTEXITCODE)"
}
& ssh @SshRemoteOpts "${PiUser}@${PiHost}" "sudo -n systemctl restart nodered.service" 2>$null
if ($LASTEXITCODE -ne 0) {
  Write-Host "경고: nodered 재시작 실패(무시하고 계속). sudo 권한이 없을 수 있습니다. Pi에서 수동 재시작하세요: sudo systemctl restart nodered.service" -ForegroundColor Yellow
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
  Write-Host "완료: Node-RED 플로우 배포 (Arduino 업로드는 생략됨)" -ForegroundColor Green
} else {
  Write-Host "완료: Arduino(upcode) + Node-RED 플로우 배포" -ForegroundColor Green
}
