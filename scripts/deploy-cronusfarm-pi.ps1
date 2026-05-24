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
  [switch] $StopNodeRedDuringArduinoUpload,
  [switch] $SkipGrafana,
  # nginx 사이트 설정 동기화·reload(비밀번호 sudo면 WARN만)
  [switch] $SkipNginxDeploy,
  # cronusfarm-camera-ai 복사·systemctl 재시작 생략(장시간 대기 회피)
  [switch] $SkipAiCamera,
  # Node-RED 플로우만 자주 바꿀 때: SQLite/Hailo/Grafana/nginx/텔레그램 drop-in/Dashboard2 설치·upstream 점검 등 생략 (-ApplyNodeRed와 함께 사용)
  [switch] $NodeRedFlowsOnly,
  # 초경량: 로컬에서 merged-deploy.json만 생성 후 그 파일만 Pi에 반영(분할 JSON·dashboard HTML·vendor 미복사). iframe/HTML 수정 시에는 쓰지 말 것.
  [switch] $NodeRedMergedOnly,
  # settings.js 경로 패치(pi-nodered-apply-settings-farm.sh) 생략 — SSH 불안정 시 플로우만 배포
  [switch] $SkipSettingsPatch,
  # farm-ui SPA 빌드·dist 동기화 생략
  [switch] $SkipFarmUi
)
# -SkipGrafana: Pi sudo(그래파나) 대기로 멈출 때 Node·아두이노만 빠르게 배포
# -SkipAiCamera: AI 카메라 유닛 배포 스킵(원하면 NR 적용 후에도 동일 스위치로 생략)
# -NodeRedFlowsOnly: 무거운 페이로드 생략 + 분할 JSON·dashboard 정적 파일까지 Pi 동기화
# -NodeRedMergedOnly: 위 생략 + 분할 JSON/dashboard 미복사(merged-deploy만). 실행 속도 우선.

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

if ($NodeRedMergedOnly -and -not $ApplyNodeRed) {
  throw "-NodeRedMergedOnly requires -ApplyNodeRed"
}

$CfNrDeployLight = $NodeRedFlowsOnly -or $NodeRedMergedOnly
if ($CfNrDeployLight) {
  $SkipArduino = $true
  $SkipNginxDeploy = $true
  $SkipGrafana = $true
  $SkipAiCamera = $true
  $SkipFarmUi = $true
  Write-Host "=== NR deploy (light): skip SQLite/Hailo/grafana/nginx/telegram extras ===" -ForegroundColor Yellow
}

# PSScriptRoot 이 비면 Join-Path / dot-source 가 실패하거나 $null 경로가 생김
$scriptPathDeploy = $MyInvocation.MyCommand.Path
$scriptDirDeploy = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $scriptPathDeploy }
if (-not $scriptDirDeploy) {
  throw "Cannot resolve script directory (PSScriptRoot empty and MyCommand.Path missing)."
}
# ScriptRoot 같은 일반 이름은 호스트별로 충돌할 수 있어 CronusDeployScriptDir 고정
$CronusDeployScriptDir = $scriptDirDeploy
$repoRoot = Split-Path $CronusDeployScriptDir -Parent

. (Join-Path $CronusDeployScriptDir "pi-host-resolve.ps1")
$PiHost = Get-CronusPiHost -PiHost $PiHost -PiHostLan $PiHostLan -PiHostWan $PiHostWan -PiUser $PiUser
if ([string]::IsNullOrWhiteSpace($PiHost)) {
  throw "PiHost 가 비어 있습니다. Tailscale/LAN 확인 후 -PiHostWan ida.mango-larch.ts.net 또는 -PiHostLan 192.168.60.222 를 지정하세요."
}
Write-Host "[Pi] deploy target: ${PiUser}@${PiHost}" -ForegroundColor Cyan
if (-not (Test-CronusSshPort -ComputerName $PiHost -TimeoutMs 5000)) {
  throw "Pi SSH(22) 연결 불가: ${PiUser}@${PiHost}. Tailscale·LAN(192.168.60.222) 확인 후 -PiHostLan 또는 -PiHostWan 지정."
}
# 에이전트/백그라운드 환경에서 SSH 무한 대기 방지 + 비대화형
# 원격 셸: -T(의사 TTY 끔) — Windows PowerShell에서 ssh가 멈추는 경우가 있어 ssh에만 사용
$SshScpOpts = @(
  "-o", "Port=22",
  "-o", "ConnectTimeout=30",
  "-o", "ServerAliveInterval=5",
  "-o", "ServerAliveCountMax=3",
  "-o", "BatchMode=yes",
  "-o", "StrictHostKeyChecking=accept-new"
)
$SshRemoteOpts = @(
  "-T",
  "-o", "Port=22",
  "-o", "ConnectTimeout=30",
  "-o", "ServerAliveInterval=5",
  "-o", "ServerAliveCountMax=3",
  "-o", "BatchMode=yes",
  "-o", "StrictHostKeyChecking=accept-new"
)

function Invoke-CronusPiSettingsPatch {
  if ($SkipSettingsPatch) {
    Write-Host "Skip: settings.js patch (-SkipSettingsPatch)" -ForegroundColor DarkGray
    return
  }
  if (-not (Test-CronusSshPort -ComputerName $PiHost -TimeoutMs 5000)) {
    Write-Host "WARN: Pi SSH(22) 응답 없음 — settings.js 패치 생략. Tailscale/LAN 확인 후 재시도하거나 Pi에서: bash ~/CronusFarm/scripts/pi-nodered-apply-settings-farm.sh" -ForegroundColor Yellow
    return
  }
  Write-Host "=== Node-RED: settings.js (/ui /admin) patch ===" -ForegroundColor Cyan
  & ssh @SshRemoteOpts "${PiUser}@${PiHost}" "bash '$remoteScripts/pi-nodered-apply-settings-farm.sh'"
  if ($LASTEXITCODE -ne 0) {
    Write-Host "WARN: settings.js 패치 실패(종료 $LASTEXITCODE). 플로우 배포는 계속됩니다. Pi에서: bash ~/CronusFarm/scripts/pi-nodered-apply-settings-farm.sh" -ForegroundColor Yellow
    return
  }
  & ssh @SshRemoteOpts "${PiUser}@${PiHost}" "sudo -n systemctl restart nodered.service" 2>$null
  if ($LASTEXITCODE -ne 0) {
    Write-Host "WARN: nodered restart after settings patch failed (continue)" -ForegroundColor Yellow
  }
}

$nrDir = Join-Path $CronusDeployScriptDir "..\nodered"
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
  & (Join-Path $CronusDeployScriptDir "upcode.ps1") @up
  Write-Host "=== Arduino: R4 메인 upcode 완료 ===" -ForegroundColor Green

  # 2) R3 패널 스케치도 함께 업로드(연결되어 있을 때만). 포트는 AutoPort로 탐지.
  Write-Host "=== Arduino: upcode (R3 panel, if connected) ===" -ForegroundColor Cyan
  $upR3 = @{ PiHost = $PiHost; PiUser = $PiUser; Fqbn = "arduino:avr:uno"; LocalSketchDir = (Join-Path $CronusDeployScriptDir "..\\arduino\\CronusFarmPanel"); RemoteSketchDir = "$RemoteCronusRoot/arduino/CronusFarmPanel" }
  if ($AutoPort) { $upR3.AutoPort = $true }
  if ($StopNodeRedDuringArduinoUpload) { $upR3.StopNodeRedDuringUpload = $true }
  try {
    & (Join-Path $CronusDeployScriptDir "upcode.ps1") @upR3
  } catch {
    Write-Host "WARN: R3 panel upload failed (not connected / no port). You can run upcode for R3 only." -ForegroundColor Yellow
  }
  # upcode 중단·R4+R3 연속 업로드 시에도 /ui(1882) 복구 — StopNodeRed 여부와 무관하게 1회 재기동
  Write-Host "=== Node-RED: Arduino 업로드 후 UI 복구 (restart + 1882 대기) ===" -ForegroundColor Cyan
  & ssh @SshRemoteOpts "${PiUser}@${PiHost}" "sudo -n systemctl restart nodered.service 2>/dev/null || true; bash '$RemoteCronusRoot/scripts/pi-nodered-wait-ready.sh' 90 2>/dev/null || true"
  if ($StopNodeRedDuringArduinoUpload) {
    Write-Host "NOTE: 업로드 직후 1~2분은 /ui 가 502일 수 있음 — 재기동 메시지 후 브라우저 Ctrl+F5" -ForegroundColor Yellow
  }
} else {
  Write-Host "=== Arduino upload skipped (-SkipArduino) ===" -ForegroundColor Yellow
}

$remoteNodered = "$RemoteCronusRoot/nodered"
$remoteScripts = "$RemoteCronusRoot/scripts"
& ssh @SshRemoteOpts "${PiUser}@${PiHost}" "mkdir -p '$remoteNodered' '$remoteScripts'"

if (-not $NodeRedMergedOnly) {
  $spaPatchPy = Join-Path $CronusDeployScriptDir "patch_settings_spa.py"
  if (Test-Path $spaPatchPy) {
    Write-Host "=== Dashboard: settings tab → SPA links (patch_settings_spa.py) ===" -ForegroundColor Cyan
    if (Get-Command python -ErrorAction SilentlyContinue) {
      & python $spaPatchPy
    } elseif (Get-Command py -ErrorAction SilentlyContinue) {
      & py -3 $spaPatchPy
    } else {
      Write-Host "WARN: Python 없음 — patch_settings_spa.py 생략" -ForegroundColor Yellow
    }
  }
  Write-Host "=== Node-RED: sync flow JSON -> $remoteNodered ===" -ForegroundColor Cyan
  & scp @SshScpOpts "$mqttPath" "${PiUser}@${PiHost}:$remoteNodered/flows_cronusfarm_mqtt.json"
  & scp @SshScpOpts "$dashPath" "${PiUser}@${PiHost}:$remoteNodered/flows_cronusfarm_dashboard.json"
  & scp @SshScpOpts "$devFlowPath" "${PiUser}@${PiHost}:$remoteNodered/flows_cronusfarm_devflow_flow.json"
  $dashHtmlDir = Join-Path $nrDir "dashboard"
  if (Test-Path $dashHtmlDir) {
    Write-Host "=== Node-RED: dashboard/*.html -> $remoteNodered/dashboard ===" -ForegroundColor Cyan
    & ssh @SshRemoteOpts "${PiUser}@${PiHost}" "mkdir -p '$remoteNodered/dashboard'"
    Get-ChildItem -Path $dashHtmlDir -Filter "*.html" -File -ErrorAction SilentlyContinue | ForEach-Object {
      & scp @SshScpOpts "$($_.FullName)" "${PiUser}@${PiHost}:$remoteNodered/dashboard/$($_.Name)"
    }
    $dashVendor = Join-Path $dashHtmlDir "vendor"
    if (Test-Path $dashVendor) {
      Write-Host "=== Node-RED: dashboard/vendor/*.js -> $remoteNodered/dashboard/vendor ===" -ForegroundColor Cyan
      & ssh @SshRemoteOpts "${PiUser}@${PiHost}" "mkdir -p '$remoteNodered/dashboard/vendor'"
      Get-ChildItem -Path $dashVendor -Filter "*.js" -File -ErrorAction SilentlyContinue | ForEach-Object {
        & scp @SshScpOpts "$($_.FullName)" "${PiUser}@${PiHost}:$remoteNodered/dashboard/vendor/$($_.Name)"
      }
    }
  }
  if (-not $SkipFarmUi) {
    $buildFarmUi = Join-Path $CronusDeployScriptDir "build-farm-ui.ps1"
    $farmUiDist = Join-Path $repoRoot "farm-ui\dist"
    if (Test-Path $buildFarmUi) {
      Write-Host "=== farm-ui: Vite build ===" -ForegroundColor Cyan
      & $buildFarmUi
      if ($LASTEXITCODE -ne 0) {
        Write-Host "WARN: farm-ui 빌드 실패 — dist 동기화 생략" -ForegroundColor Yellow
      } elseif (Test-Path $farmUiDist) {
        $remoteFarmUiDist = "$RemoteCronusRoot/farm-ui/dist"
        Write-Host "=== farm-ui: dist -> $remoteFarmUiDist ===" -ForegroundColor Cyan
        & ssh @SshRemoteOpts "${PiUser}@${PiHost}" "mkdir -p '$remoteFarmUiDist'"
        Get-ChildItem -Path $farmUiDist -Recurse -File | ForEach-Object {
          $rel = $_.FullName.Substring($farmUiDist.Length).TrimStart('\', '/').Replace('\', '/')
          $remoteDir = "$remoteFarmUiDist/$(Split-Path $rel -Parent)"
          if ($rel -match '/') {
            & ssh @SshRemoteOpts "${PiUser}@${PiHost}" "mkdir -p '$remoteDir'"
          }
          & scp @SshScpOpts $_.FullName "${PiUser}@${PiHost}:$remoteFarmUiDist/$rel"
        }
        & (Join-Path $CronusDeployScriptDir "Invoke-FarmUiPostDeploy.ps1") `
          -PiHost $PiHost -PiUser $PiUser -RemoteDist $remoteFarmUiDist `
          -FarmUiDistLocal $farmUiDist -ScriptDir $CronusDeployScriptDir -SshOpts $SshRemoteOpts
      }
    }
  } else {
    Write-Host "Skip: farm-ui build/deploy (-SkipFarmUi)" -ForegroundColor DarkGray
  }
} else {
  Write-Host "Skip: split JSON + dashboard static (-NodeRedMergedOnly; merged-deploy only to Pi)" -ForegroundColor DarkGray
}
$exportPath = Join-Path $nrDir "CronusFarm_NodeRED_flow.json"
if ((Test-Path $exportPath) -and (-not $CfNrDeployLight)) {
  & scp @SshScpOpts "$exportPath" "${PiUser}@${PiHost}:$remoteNodered/CronusFarm_NodeRED_flow.json"
  Write-Host "Synced: CronusFarm_NodeRED_flow.json (export backup)" -ForegroundColor DarkGray
} elseif ((Test-Path $exportPath) -and $CfNrDeployLight) {
  Write-Host "Skip: CronusFarm_NodeRED_flow.json (light deploy)" -ForegroundColor DarkGray
}

$applySettingsSh = Join-Path $CronusDeployScriptDir "pi-nodered-apply-settings-farm.sh"
if (-not (Test-Path $applySettingsSh)) {
  throw "pi-nodered-apply-settings-farm.sh 없음: $applySettingsSh"
}
& scp @SshScpOpts "$applySettingsSh" "${PiUser}@${PiHost}:$remoteScripts/pi-nodered-apply-settings-farm.sh"
& ssh @SshRemoteOpts "${PiUser}@${PiHost}" "chmod +x '$remoteScripts/pi-nodered-apply-settings-farm.sh'"

# Dashboard 2 설치 스크립트는 Pi에 항상 복사(git pull 없이 수동 실행 가능). npm 실행은 -ApplyNodeRed 구간에서만.
$dash2Sh = Join-Path $CronusDeployScriptDir "pi-nodered-install-dashboard2.sh"
if ((-not $CfNrDeployLight) -and (Test-Path $dash2Sh)) {
  & scp @SshScpOpts "$dash2Sh" "${PiUser}@${PiHost}:$remoteScripts/pi-nodered-install-dashboard2.sh"
  & ssh @SshRemoteOpts "${PiUser}@${PiHost}" "chmod +x '$remoteScripts/pi-nodered-install-dashboard2.sh'; sed -i 's/\r$//' '$remoteScripts/pi-nodered-install-dashboard2.sh' 2>/dev/null || true"
}

$applySh = Join-Path $CronusDeployScriptDir "pi-nodered-apply-merged.sh"
if (-not (Test-Path $applySh)) {
  throw "pi-nodered-apply-merged.sh 없음: $applySh"
}
& scp @SshScpOpts "$applySh" "${PiUser}@${PiHost}:$remoteScripts/pi-nodered-apply-merged.sh"
& ssh @SshRemoteOpts "${PiUser}@${PiHost}" "chmod +x '$remoteScripts/pi-nodered-apply-merged.sh'"

$ensureUpstreamSh = Join-Path $CronusDeployScriptDir "pi-nodered-ensure-upstream-for-nginx.sh"
if ((-not $CfNrDeployLight) -and (Test-Path $ensureUpstreamSh)) {
  & scp @SshScpOpts "$ensureUpstreamSh" "${PiUser}@${PiHost}:$remoteScripts/pi-nodered-ensure-upstream-for-nginx.sh"
  & ssh @SshRemoteOpts "${PiUser}@${PiHost}" "chmod +x '$remoteScripts/pi-nodered-ensure-upstream-for-nginx.sh'"
}

# Windows에서 git/autocrlf 등으로 .sh가 CRLF로 올라가면 Pi에서 "$'\r'" 오류가 납니다.
# 복사 직후 원격에서 LF로 정리합니다(실패해도 계속).
& ssh @SshRemoteOpts "${PiUser}@${PiHost}" "sed -i 's/\r$//' $remoteScripts/*.sh 2>/dev/null || true"

$nginxConfSrc = Join-Path $repoRoot "deploy\nginx\cronusfarm-nodered.conf"
$nginxApplySh = Join-Path $CronusDeployScriptDir "pi-nginx-apply-cronusfarm.sh"
if (-not $SkipNginxDeploy -and (Test-Path $nginxConfSrc)) {
  Write-Host "=== nginx: cronusfarm-nodered.conf -> Pi (reload if sudo -n ok) ===" -ForegroundColor Cyan
  $remoteDeployNginx = "$RemoteCronusRoot/deploy/nginx"
  & ssh @SshRemoteOpts "${PiUser}@${PiHost}" "mkdir -p '$remoteDeployNginx'"
  & scp @SshScpOpts "$nginxConfSrc" "${PiUser}@${PiHost}:$remoteDeployNginx/cronusfarm-nodered.conf"
  if (Test-Path $nginxApplySh) {
    & scp @SshScpOpts "$nginxApplySh" "${PiUser}@${PiHost}:$remoteScripts/pi-nginx-apply-cronusfarm.sh"
    & ssh @SshRemoteOpts "${PiUser}@${PiHost}" "chmod +x '$remoteScripts/pi-nginx-apply-cronusfarm.sh'; sed -i 's/\r$//' '$remoteScripts/pi-nginx-apply-cronusfarm.sh' 2>/dev/null || true; bash '$remoteScripts/pi-nginx-apply-cronusfarm.sh' '$remoteDeployNginx/cronusfarm-nodered.conf'"
  }
} elseif (-not $SkipNginxDeploy) {
  Write-Host "WARN: deploy/nginx/cronusfarm-nodered.conf 없음 — nginx 동기화 생략" -ForegroundColor Yellow
}

# SQLite 브리지·DDL(systemd §9) — Pi에서 직접 실행할 스크립트가 저장소와 동일하게 올라가도록 함
$sqlSchema = Join-Path $CronusDeployScriptDir "sql\cronusfarm_record_v1.sql"
$sqliteInit = Join-Path $CronusDeployScriptDir "init_cronusfarm_sqlite.py"
$sqliteBridge = Join-Path $CronusDeployScriptDir "cronusfarm_sqlite_bridge.py"
$sqliteAdminApi = Join-Path $CronusDeployScriptDir "cronusfarm_admin_api.py"
$sqlAdminV2 = Join-Path $CronusDeployScriptDir "sql\cronusfarm_admin_v2.sql"
$systemdBridge = Join-Path $repoRoot "deploy\systemd\cronusfarm-sqlite-bridge.service"
$haveSqlitePayload = ($null -ne $sqliteInit -and (Test-Path -LiteralPath $sqliteInit)) -or ($null -ne $sqliteBridge -and (Test-Path -LiteralPath $sqliteBridge)) -or ($null -ne $sqlSchema -and (Test-Path -LiteralPath $sqlSchema)) -or ($null -ne $systemdBridge -and (Test-Path -LiteralPath $systemdBridge))
if ($haveSqlitePayload -and (-not $CfNrDeployLight)) {
  Write-Host "=== SQLite: sync bridge/schema -> $RemoteCronusRoot ===" -ForegroundColor Cyan
  $remoteDeploySystemd = "$RemoteCronusRoot/deploy/systemd"
  & ssh @SshRemoteOpts "${PiUser}@${PiHost}" "mkdir -p '$remoteScripts/sql' '$remoteDeploySystemd'"
  if ($null -ne $sqliteInit -and (Test-Path -LiteralPath $sqliteInit)) {
    & scp @SshScpOpts "$sqliteInit" "${PiUser}@${PiHost}:$remoteScripts/init_cronusfarm_sqlite.py"
  }
  if ($null -ne $sqliteBridge -and (Test-Path -LiteralPath $sqliteBridge)) {
    & scp @SshScpOpts "$sqliteBridge" "${PiUser}@${PiHost}:$remoteScripts/cronusfarm_sqlite_bridge.py"
  }
  if ($null -ne $sqliteAdminApi -and (Test-Path -LiteralPath $sqliteAdminApi)) {
    & scp @SshScpOpts "$sqliteAdminApi" "${PiUser}@${PiHost}:$remoteScripts/cronusfarm_admin_api.py"
  }
  if ($null -ne $sqlSchema -and (Test-Path -LiteralPath $sqlSchema)) {
    & scp @SshScpOpts "$sqlSchema" "${PiUser}@${PiHost}:$remoteScripts/sql/cronusfarm_record_v1.sql"
  }
  if ($null -ne $sqlAdminV2 -and (Test-Path -LiteralPath $sqlAdminV2)) {
    & scp @SshScpOpts "$sqlAdminV2" "${PiUser}@${PiHost}:$remoteScripts/sql/cronusfarm_admin_v2.sql"
  }
  if ($null -ne $systemdBridge -and (Test-Path -LiteralPath $systemdBridge)) {
    & scp @SshScpOpts "$systemdBridge" "${PiUser}@${PiHost}:$remoteDeploySystemd/cronusfarm-sqlite-bridge.service"
  }
  $piCheckKv = Join-Path $CronusDeployScriptDir "pi-check-sqlite-kv.sh"
  if (Test-Path $piCheckKv) {
    & scp @SshScpOpts "$piCheckKv" "${PiUser}@${PiHost}:$remoteScripts/pi-check-sqlite-kv.sh"
    & ssh @SshRemoteOpts "${PiUser}@${PiHost}" "chmod +x '$remoteScripts/pi-check-sqlite-kv.sh'"
  }
  $piAiSetup = Join-Path $CronusDeployScriptDir "pi-ai-setup.sh"
  if (Test-Path $piAiSetup) {
    & scp @SshScpOpts "$piAiSetup" "${PiUser}@${PiHost}:$remoteScripts/pi-ai-setup.sh"
    & ssh @SshRemoteOpts "${PiUser}@${PiHost}" "chmod +x '$remoteScripts/pi-ai-setup.sh'"
  }
  if (($null -ne $sqliteBridge -and (Test-Path -LiteralPath $sqliteBridge)) -or ($null -ne $sqliteInit -and (Test-Path -LiteralPath $sqliteInit))) {
    # sudo/systemctl이 환경에 따라 멈추는 경우가 있어 timeout으로 보호
    & ssh @SshRemoteOpts "${PiUser}@${PiHost}" "timeout 12s sudo systemctl restart cronusfarm-sqlite-bridge.service 2>/dev/null || true"
  }
}

# Hailo GStreamer: 스크립트 + ~/CronusFarm/Hailo (best.hef / best.onnx / yolov8.json)
$hailoPy = Join-Path $CronusDeployScriptDir "cronusfarm_hailo_stream.py"
if ((-not $CfNrDeployLight) -and (Test-Path -LiteralPath $hailoPy)) {
  Write-Host "=== Hailo: cronusfarm_hailo_stream.py -> $remoteScripts ===" -ForegroundColor Cyan
  & scp @SshScpOpts "$hailoPy" "${PiUser}@${PiHost}:$remoteScripts/cronusfarm_hailo_stream.py"
}
$hailoRepoDir = Join-Path $repoRoot "Hailo"
if ((-not $CfNrDeployLight) -and (Test-Path -LiteralPath $hailoRepoDir)) {
  Write-Host "=== Hailo: CronusFarm/Hailo -> $RemoteCronusRoot/Hailo ===" -ForegroundColor Cyan
  $remoteHailo = "$RemoteCronusRoot/Hailo"
  & ssh @SshRemoteOpts "${PiUser}@${PiHost}" "mkdir -p '$remoteHailo'"
  Get-ChildItem -Path $hailoRepoDir -File -ErrorAction SilentlyContinue | ForEach-Object {
    & scp @SshScpOpts "$($_.FullName)" "${PiUser}@${PiHost}:$remoteHailo/$($_.Name)"
  }
}

# 텔레그램 플로우용 systemd EnvironmentFile(비밀값은 Pi의 /etc/cronusfarm/nodered-telegram.env 만)
$tgInstall = Join-Path $CronusDeployScriptDir "pi-install-nodered-telegram-env.sh"
$tgDropIn = Join-Path $repoRoot "deploy\systemd\nodered.service.d\10-cronusfarm-telegram.conf"
$tgEnvEx = Join-Path $repoRoot "deploy\env\nodered-telegram.env.example"
$nrAiCamDropIn = Join-Path $repoRoot "deploy\systemd\nodered.service.d\20-cronusfarm-hailo-camera.conf"
if ((-not $CfNrDeployLight) -and (Test-Path $tgInstall) -and (Test-Path $tgDropIn) -and (Test-Path $tgEnvEx)) {
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

# Node-RED 기동 후 cronusfarm-camera-ai try-restart(drop-in). 텔레그램 블록과 독립.
if ((-not $CfNrDeployLight) -and (Test-Path $nrAiCamDropIn)) {
  Write-Host "=== Node-RED drop-in: NR 기동 후 ustreamer+hailo restart ===" -ForegroundColor Cyan
  $remoteNrDropOnly = "$RemoteCronusRoot/deploy/systemd/nodered.service.d"
  & ssh @SshRemoteOpts "${PiUser}@${PiHost}" "mkdir -p '$remoteNrDropOnly'"
  & scp @SshScpOpts "$nrAiCamDropIn" "${PiUser}@${PiHost}:$remoteNrDropOnly/20-cronusfarm-hailo-camera.conf"
  $nrAiDropCmd = "sudo mkdir -p /etc/systemd/system/nodered.service.d && sudo cp '$remoteNrDropOnly/20-cronusfarm-hailo-camera.conf' /etc/systemd/system/nodered.service.d/20-cronusfarm-hailo-camera.conf && sudo rm -f /etc/systemd/system/nodered.service.d/20-cronusfarm-camera-ai.conf && sudo systemctl daemon-reload"
  & ssh @SshRemoteOpts "${PiUser}@${PiHost}" $nrAiDropCmd
}

if (-not $SkipGrafana) {
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
      & ssh @SshRemoteOpts "${PiUser}@${PiHost}" "timeout 90 sh -c '$remoteGfCmd'" 2>$null
      if ($LASTEXITCODE -ne 0) {
        Write-Host "WARN: Grafana copy/reload failed or timeout (sudo/path). Manual: sudo cp /tmp/*.json /var/lib/grafana/dashboards/" -ForegroundColor Yellow
      }
    }
  }

  $gfDropIn = Join-Path $repoRoot "deploy\grafana\systemd\grafana-server.service.d\99-cronusfarm-panels.conf"
  if (Test-Path $gfDropIn) {
    Write-Host "=== Grafana: allow Text panel iframe(systemd drop-in) ===" -ForegroundColor Cyan
    & scp @SshScpOpts "$gfDropIn" "${PiUser}@${PiHost}:/tmp/99-cronusfarm-panels.conf"
    $gfSysCmd = "sudo mkdir -p /etc/systemd/system/grafana-server.service.d && sudo cp /tmp/99-cronusfarm-panels.conf /etc/systemd/system/grafana-server.service.d/ && sudo systemctl daemon-reload && (sudo systemctl restart grafana-server 2>/dev/null || sudo systemctl restart grafana 2>/dev/null || true)"
    & ssh @SshRemoteOpts "${PiUser}@${PiHost}" "timeout 120 sh -c '$gfSysCmd'" 2>$null
    if ($LASTEXITCODE -ne 0) {
      Write-Host "WARN: Grafana systemd drop-in failed or timeout. Check GF_PANELS_DISABLE_SANITIZE_HTML on Pi." -ForegroundColor Yellow
    }
  }
} else {
  Write-Host "=== Grafana: skipped (-SkipGrafana) ===" -ForegroundColor Yellow
}

# -ApplyNodeRed 없이 종료하는 경우: NR merged 는 적용하지 않지만 카메라 유닛은 이 시점에서 반영
if ((-not $ApplyNodeRed) -and (-not $SkipAiCamera)) {
  $cameraSvc = Join-Path $repoRoot "deploy\systemd\cronusfarm-camera-ai.service"
  $cameraPy = Join-Path $CronusDeployScriptDir "cronusfarm_camera_ai.py"
  if ((Test-Path -LiteralPath $cameraSvc) -and (Test-Path -LiteralPath $cameraPy)) {
    $ust = (& ssh @SshRemoteOpts "${PiUser}@${PiHost}" 'pgrep -x ustreamer >/dev/null 2>&1 && echo yes || echo no').Trim()
    if ($ust -eq "yes") {
      Write-Host "=== AI camera: ustreamer running - skip cronusfarm-camera-ai (UVC in use) ===" -ForegroundColor Yellow
    } else {
      Write-Host "=== AI camera: cronusfarm_camera_ai.py + systemd -> Pi ===" -ForegroundColor Cyan
      $remoteDeploySd = "$RemoteCronusRoot/deploy/systemd"
      & ssh @SshRemoteOpts "${PiUser}@${PiHost}" "mkdir -p '$remoteDeploySd'"
      & scp @SshScpOpts "$cameraPy" "${PiUser}@${PiHost}:$remoteScripts/cronusfarm_camera_ai.py"
      & scp @SshScpOpts "$cameraSvc" "${PiUser}@${PiHost}:$remoteDeploySd/cronusfarm-camera-ai.service"
      $svcOnPi = "$remoteDeploySd/cronusfarm-camera-ai.service"
      $q = [char]34
      $inner = "cp $svcOnPi /etc/systemd/system/cronusfarm-camera-ai.service && systemctl daemon-reload && systemctl enable cronusfarm-camera-ai.service && systemctl restart cronusfarm-camera-ai.service"
      $camRemote = "timeout 135s sudo -n bash -c ${q}${inner}${q}"
      & ssh @SshRemoteOpts "${PiUser}@${PiHost}" $camRemote
      if ($LASTEXITCODE -ne 0) {
        Write-Host "WARN: cronusfarm-camera-ai deploy/restart exit $LASTEXITCODE - Pi: journalctl -u cronusfarm-camera-ai -n 60" -ForegroundColor Yellow
      }
    }
  }
}

if (-not $ApplyNodeRed) {
  Write-Host "OK: saved nodered/*.json and apply scripts on Pi." -ForegroundColor Green
  Write-Host "Auto apply: .\\scripts\\deploy-cronusfarm-pi.ps1 -ApplyNodeRed" -ForegroundColor Green
  exit 0
}

Write-Host "=== Node-RED: merge then apply flows.json + restart ===" -ForegroundColor Cyan
if ($UseSplitFlows) {
  Write-Host "Merge source: split 3 files only (editor layout may differ from CronusFarm_NodeRED_flow.json)" -ForegroundColor Yellow
} elseif (Test-Path $exportPath) {
  Write-Host "Merge source: CronusFarm_NodeRED_flow.json (keep export node layout) — default" -ForegroundColor Cyan
} else {
  Write-Host "Merge source: split 3 files (no export JSON)" -ForegroundColor Yellow
}
Write-Host "NOTE: running Node-RED flow will be fully replaced by repo JSON." -ForegroundColor Yellow
Write-Host "Also: patch settings.js paths(/ui /admin) after flows apply (WARN only on failure)" -ForegroundColor Yellow
if ($NodeRedMergedOnly) {
  Write-Host "WARN: Pi ~/CronusFarm/nodered split/*.json + dashboard/ NOT updated (merged-deploy.json only)." -ForegroundColor Yellow
}

if (-not $CfNrDeployLight) {
  & ssh @SshRemoteOpts "${PiUser}@${PiHost}" "if [[ -x '$remoteScripts/pi-install-nodered-telegram-env.sh' ]]; then sed -i 's/\r$//' '$remoteScripts/pi-install-nodered-telegram-env.sh' 2>/dev/null || true; bash '$remoteScripts/pi-install-nodered-telegram-env.sh'; else echo 'skip: pi-install-nodered-telegram-env.sh missing'; fi"
  if ($LASTEXITCODE -ne 0) {
    Write-Host "WARN: telegram env systemd apply failed (sudo/path). On Pi: bash ~/CronusFarm/scripts/pi-install-nodered-telegram-env.sh" -ForegroundColor Yellow
  }
} else {
  Write-Host "Skip: telegram env installer (light deploy)" -ForegroundColor DarkGray
}

if (-not $CfNrDeployLight) {
  Write-Host "=== Node-RED: nginx upstream (1882) vs 502 fix ===" -ForegroundColor Cyan
  & ssh @SshRemoteOpts "${PiUser}@${PiHost}" "if [[ -x '$remoteScripts/pi-nodered-ensure-upstream-for-nginx.sh' ]]; then bash '$remoteScripts/pi-nodered-ensure-upstream-for-nginx.sh'; else echo 'skip: pi-nodered-ensure-upstream-for-nginx.sh missing' >&2; fi"
}

# 로컬에서 merge_nodered_deploy.py 실행 → 분할 dashboard → 내보내기 동기화 후 merged-deploy.json 생성
# Windows에서는 PATH에 python 이 없고 py 런처만 있는 경우가 있어 둘 다 허용한다.

if ((-not $CfNrDeployLight) -and (Test-Path $dash2Sh)) {
  Write-Host "=== Node-RED: Dashboard2 @flowfuse (/nrdb2) install check ===" -ForegroundColor Cyan
  & ssh @SshRemoteOpts "${PiUser}@${PiHost}" "if [[ -x '$remoteScripts/pi-nodered-install-dashboard2.sh' ]]; then bash '$remoteScripts/pi-nodered-install-dashboard2.sh'; else echo 'WARN: pi-nodered-install-dashboard2.sh missing' >&2; fi"
} elseif ($CfNrDeployLight) {
  Write-Host "Skip: Dashboard2 install check (light deploy)" -ForegroundColor DarkGray
}

$spaPatchPy = Join-Path $CronusDeployScriptDir "patch_settings_spa.py"
if ($ApplyNodeRed -and (Test-Path $spaPatchPy) -and $NodeRedMergedOnly) {
  Write-Host "=== Dashboard: settings SPA patch (merged-only) ===" -ForegroundColor Cyan
  if (Get-Command python -ErrorAction SilentlyContinue) {
    & python $spaPatchPy
  } elseif (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3 $spaPatchPy
  }
}

$mergeScript = Join-Path $CronusDeployScriptDir "merge_nodered_deploy.py"
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
  throw "Node-RED apply script failed (exit: $LASTEXITCODE). Pi: journalctl -u nodered -n 80; test -r ~/.node-red/flows.json"
}

Invoke-CronusPiSettingsPatch

# NR flows 반영 후에 실행: 재시작이 길어도 대시보드 배포는 이미 끝난 상태
if (-not $SkipAiCamera) {
  $cameraSvc = Join-Path $repoRoot "deploy\systemd\cronusfarm-camera-ai.service"
  $cameraPy = Join-Path $CronusDeployScriptDir "cronusfarm_camera_ai.py"
  if ((Test-Path -LiteralPath $cameraSvc) -and (Test-Path -LiteralPath $cameraPy)) {
    $ust = (& ssh @SshRemoteOpts "${PiUser}@${PiHost}" 'pgrep -x ustreamer >/dev/null 2>&1 && echo yes || echo no').Trim()
    if ($ust -eq "yes") {
      Write-Host "=== AI camera: ustreamer running - skip cronusfarm-camera-ai (UVC in use) ===" -ForegroundColor Yellow
    } else {
      Write-Host "=== AI camera: cronusfarm_camera_ai.py + systemd -> Pi ===" -ForegroundColor Cyan
      $remoteDeploySd = "$RemoteCronusRoot/deploy/systemd"
      & ssh @SshRemoteOpts "${PiUser}@${PiHost}" "mkdir -p '$remoteDeploySd'"
      & scp @SshScpOpts "$cameraPy" "${PiUser}@${PiHost}:$remoteScripts/cronusfarm_camera_ai.py"
      & scp @SshScpOpts "$cameraSvc" "${PiUser}@${PiHost}:$remoteDeploySd/cronusfarm-camera-ai.service"
      $svcOnPi = "$remoteDeploySd/cronusfarm-camera-ai.service"
      $q = [char]34
      $inner = "cp $svcOnPi /etc/systemd/system/cronusfarm-camera-ai.service && systemctl daemon-reload && systemctl enable cronusfarm-camera-ai.service && systemctl restart cronusfarm-camera-ai.service"
      $camRemote = "timeout 135s sudo -n bash -c ${q}${inner}${q}"
      & ssh @SshRemoteOpts "${PiUser}@${PiHost}" $camRemote
      if ($LASTEXITCODE -ne 0) {
        Write-Host "WARN: cronusfarm-camera-ai deploy/restart exit $LASTEXITCODE - Pi: journalctl -u cronusfarm-camera-ai -n 60" -ForegroundColor Yellow
      }
    }
  }
} else {
  Write-Host "=== AI camera: skipped (-SkipAiCamera) ===" -ForegroundColor Yellow
}

if ($NodeRedMergedOnly) {
  Write-Host "OK: Node-RED merged-deploy.json only (fast)" -ForegroundColor Green
} elseif ($CfNrDeployLight) {
  Write-Host "OK: Node-RED light deploy (split JSON + dashboard static synced)" -ForegroundColor Green
} elseif ($SkipArduino) {
  Write-Host "OK: Node-RED flow deployed (Arduino skipped)" -ForegroundColor Green
} else {
  Write-Host "OK: Arduino(upcode) + Node-RED flow deployed" -ForegroundColor Green
}
