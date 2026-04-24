param(
  [string] $PiHost = "",
  [string] $PiHostLan = "",
  [string] $PiHostWan = "ida.mango-larch.ts.net",
  [string] $PiUser = "dooly",
  [string] $RemoteCronusRoot = "/home/dooly/CronusFarm",
  [switch] $SkipArduino,
  [switch] $ApplyNodeRed,
  [switch] $SetupPi,
  [switch] $UploadArduino,
  [switch] $InstallGrafanaStack,
  [switch] $ImportDashboard,
  [switch] $ApplyInfluxFlow,
  [switch] $SeedCronusEnvironment,
  [switch] $SeedCronusPurge,
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
$SshOpts = @(
  "-o", "ConnectTimeout=30",
  "-o", "BatchMode=yes",
  "-o", "ServerAliveInterval=15",
  "-o", "ServerAliveCountMax=3",
  "-o", "StrictHostKeyChecking=accept-new"
)

. (Join-Path $PSScriptRoot "pi-host-resolve.ps1")
$PiHost = Get-CronusPiHost -PiHost $PiHost -PiHostLan $PiHostLan -PiHostWan $PiHostWan -PiUser $PiUser

$nrDir = Join-Path $PSScriptRoot "..\nodered"
$mqttPath = Join-Path $nrDir "flows_cronusfarm_mqtt.json"
$dashPath = Join-Path $nrDir "flows_cronusfarm_dashboard.json"
$devFlowPath = Join-Path $nrDir "flows_cronusfarm_devflow_flow.json"
$influxFlowPath = Join-Path $nrDir "flows_cronusfarm_influxdb.json"
$bedApiFlowPath = Join-Path $nrDir "flows_cronusfarm_bed_api.json"
if (-not (Test-Path $mqttPath) -or -not (Test-Path $dashPath) -or -not (Test-Path $devFlowPath)) {
  throw "Node-RED 플로우 JSON이 없습니다: $nrDir"
}

# -UploadArduino는 "R4+R3 동시 업로드" 경로이므로, 기존 upcode(R4 단독) 실행과 중복되지 않게 우선합니다.
if ($UploadArduino) {
  $SkipArduino = $true
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
& ssh @SshOpts "${PiUser}@${PiHost}" "mkdir -p '$remoteNodered' '$remoteScripts'"

# --- Pi 초기 셋업/유틸 스크립트 동기화 ---
$piSetup = Join-Path $PSScriptRoot "pi-initial-setup.sh"
$piSetupCli = Join-Path $PSScriptRoot "pi-setup-arduino-cli.sh"
$piUpload = Join-Path $PSScriptRoot "pi-arduino-upload.sh"
$piGrafStack = Join-Path $PSScriptRoot "pi-install-grafana-stack.sh"
$piGrafEnsureDs = Join-Path $PSScriptRoot "pi-grafana-ensure-influx-datasource.sh"
$piGrafImport = Join-Path $PSScriptRoot "pi-grafana-import-dashboard.sh"
$piSeedEnv = Join-Path $PSScriptRoot "pi-seed-cronusfarm-environment.sh"
$seedEnvPy = Join-Path $PSScriptRoot "seed-cronusfarm-environment.py"
$dbSchemaLocal = Join-Path $PSScriptRoot "..\db\sqlite_schema.sql"
$need = @($piSetup, $piSetupCli, $piUpload, $piGrafStack, $piGrafEnsureDs, $piGrafImport, $piSeedEnv, $seedEnvPy)
foreach ($p in $need) {
  if (-not (Test-Path $p)) { throw "필수 스크립트 없음: $p" }
  & scp @SshOpts "$p" "${PiUser}@${PiHost}:$remoteScripts/$(Split-Path $p -Leaf)"
}
& ssh @SshOpts "${PiUser}@${PiHost}" "chmod +x '$remoteScripts/pi-initial-setup.sh' '$remoteScripts/pi-setup-arduino-cli.sh' '$remoteScripts/pi-arduino-upload.sh' '$remoteScripts/pi-install-grafana-stack.sh' '$remoteScripts/pi-grafana-ensure-influx-datasource.sh' '$remoteScripts/pi-grafana-import-dashboard.sh' '$remoteScripts/pi-seed-cronusfarm-environment.sh'"

& ssh @SshOpts "${PiUser}@${PiHost}" "mkdir -p '$RemoteCronusRoot/db' '$RemoteCronusRoot/data'"
if (Test-Path $dbSchemaLocal) {
  & scp @SshOpts "$dbSchemaLocal" "${PiUser}@${PiHost}:$RemoteCronusRoot/db/sqlite_schema.sql"
}

Write-Host "=== Node-RED: 플로우 JSON 동기화 -> $remoteNodered ===" -ForegroundColor Cyan
& scp @SshOpts "$mqttPath" "${PiUser}@${PiHost}:$remoteNodered/flows_cronusfarm_mqtt.json"
& scp @SshOpts "$dashPath" "${PiUser}@${PiHost}:$remoteNodered/flows_cronusfarm_dashboard.json"
& scp @SshOpts "$devFlowPath" "${PiUser}@${PiHost}:$remoteNodered/flows_cronusfarm_devflow_flow.json"
if (Test-Path $influxFlowPath) {
  & scp @SshOpts "$influxFlowPath" "${PiUser}@${PiHost}:$remoteNodered/flows_cronusfarm_influxdb.json"
}
if (Test-Path $bedApiFlowPath) {
  & scp @SshOpts "$bedApiFlowPath" "${PiUser}@${PiHost}:$remoteNodered/flows_cronusfarm_bed_api.json"
}

# Grafana 대시보드 JSON 동기화
$grafDir = Join-Path $PSScriptRoot "..\grafana"
$grafDash = Join-Path $grafDir "cronusfarm-dashboard.json"
if (Test-Path $grafDash) {
  & ssh @SshOpts "${PiUser}@${PiHost}" "mkdir -p '$RemoteCronusRoot/grafana'"
  & scp @SshOpts "$grafDash" "${PiUser}@${PiHost}:$RemoteCronusRoot/grafana/cronusfarm-dashboard.json"
}

$applySh = Join-Path $PSScriptRoot "pi-nodered-apply-merged.sh"
if (-not (Test-Path $applySh)) {
  throw "pi-nodered-apply-merged.sh 없음: $applySh"
}
& scp @SshOpts "$applySh" "${PiUser}@${PiHost}:$remoteScripts/pi-nodered-apply-merged.sh"
& ssh @SshOpts "${PiUser}@${PiHost}" "chmod +x '$remoteScripts/pi-nodered-apply-merged.sh'"

# --- 선택 실행: Pi 셋업/그래파나/아두이노 업로드 ---
if ($SetupPi) {
  Write-Host "=== Pi 초기 설정(최초 1회) ===" -ForegroundColor Cyan
  Write-Host "주의: apt 업그레이드/서비스 설치/설정 변경이 포함됩니다." -ForegroundColor Yellow
  & ssh @SshOpts "${PiUser}@${PiHost}" "sudo -n bash '$remoteScripts/pi-initial-setup.sh'"
}

if ($UploadArduino) {
  Write-Host "=== Arduino: R4/R3 컴파일+업로드(Pi) ===" -ForegroundColor Cyan
  $remoteArduinoRoot = "$RemoteCronusRoot/arduino"
  & ssh @SshOpts "${PiUser}@${PiHost}" "mkdir -p '$remoteArduinoRoot/CronusFarm' '$remoteArduinoRoot/CronusFarmPanel'"
  $localArduinoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\arduino')).Path
  & scp @SshOpts -r "$localArduinoRoot/CronusFarm/*" "${PiUser}@${PiHost}:$remoteArduinoRoot/CronusFarm/"
  & scp @SshOpts -r "$localArduinoRoot/CronusFarmPanel/*" "${PiUser}@${PiHost}:$remoteArduinoRoot/CronusFarmPanel/"
  if ($StopNodeRedDuringArduinoUpload) {
    & ssh @SshOpts "${PiUser}@${PiHost}" "sudo -n systemctl stop nodered.service" 2>$null
  }
  if ($AutoPort) {
    & ssh @SshOpts "${PiUser}@${PiHost}" "bash '$remoteScripts/pi-arduino-upload.sh' '$remoteArduinoRoot' --auto-port"
  } else {
    & ssh @SshOpts "${PiUser}@${PiHost}" "bash '$remoteScripts/pi-arduino-upload.sh' '$remoteArduinoRoot'"
  }
  if ($StopNodeRedDuringArduinoUpload) {
    & ssh @SshOpts "${PiUser}@${PiHost}" "sudo -n systemctl start nodered.service" 2>$null
  }
}

if ($InstallGrafanaStack) {
  Write-Host "=== Grafana Stack 설치(InfluxDB+Grafana) ===" -ForegroundColor Cyan
  & ssh @SshOpts "${PiUser}@${PiHost}" "bash '$remoteScripts/pi-install-grafana-stack.sh'"
}

if ($ImportDashboard) {
  Write-Host "=== Grafana: Influx 데이터소스 확인 후 대시보드 import ===" -ForegroundColor Cyan
  & ssh @SshOpts "${PiUser}@${PiHost}" "bash '$remoteScripts/pi-grafana-ensure-influx-datasource.sh'"
  & ssh @SshOpts "${PiUser}@${PiHost}" "bash '$remoteScripts/pi-grafana-import-dashboard.sh' '$RemoteCronusRoot/grafana/cronusfarm-dashboard.json'"
}

if (-not $ApplyNodeRed) {
  if ($SeedCronusEnvironment) {
    Write-Host "=== CronusFarm DB 시드(SQLite + Influx) ===" -ForegroundColor Cyan
    $purgeArg = ""
    if ($SeedCronusPurge) { $purgeArg = "--purge-influx" }
    & ssh @SshOpts "${PiUser}@${PiHost}" "CRONUS_ROOT='$RemoteCronusRoot' bash '$remoteScripts/pi-seed-cronusfarm-environment.sh' $purgeArg"
  }
  Write-Host "완료: Pi에 nodered/*.json 및 적용 스크립트 저장됨." -ForegroundColor Green
  Write-Host "Node-RED에 자동 반영: .\scripts\deploy-cronusfarm-pi.ps1 -ApplyNodeRed" -ForegroundColor Green
  exit 0
}

Write-Host "=== Node-RED: 플로우 병합 후 API 배포 (기존 flows.json 백업) ===" -ForegroundColor Cyan
Write-Host "주의: 실행 중인 Node-RED **전체 플로우**가 저장소 내용으로 교체됩니다." -ForegroundColor Yellow

function Merge-NrJsonArrays([string[]]$paths) {
  $cores = foreach ($p in $paths) {
    $raw = (Get-Content $p -Raw -Encoding UTF8).TrimStart([char]0xFEFF).Trim()
    if (-not ($raw.StartsWith("[") -and $raw.EndsWith("]"))) {
      throw "JSON 배열이 아님: $p"
    }
    $inner = $raw.Substring(1, $raw.Length - 2).Trim()
    if ($inner.Length -gt 0) { $inner }
  }
  $joined = ($cores -join ",")
  "[$joined]"
}

$tmp = [System.IO.Path]::GetTempFileName() + ".json"
try {
  $mergeList = @($mqttPath, $dashPath, $devFlowPath)
  if ($ApplyInfluxFlow) {
    if (-not (Test-Path $influxFlowPath)) {
      throw "flows_cronusfarm_influxdb.json 없음(ApplyInfluxFlow 요청됨): $influxFlowPath"
    }
    $mergeList += $influxFlowPath
  }
  if (Test-Path $bedApiFlowPath) {
    $mergeList += $bedApiFlowPath
  }
  $mergedBody = Merge-NrJsonArrays $mergeList
  $utf8NoBom = New-Object System.Text.UTF8Encoding $false
  [System.IO.File]::WriteAllText($tmp, $mergedBody, $utf8NoBom)
  $mergedRemote = "$remoteNodered/merged-deploy.json"
  & scp @SshOpts "$tmp" "${PiUser}@${PiHost}:$mergedRemote"
  & ssh @SshOpts "${PiUser}@${PiHost}" "bash '$remoteScripts/pi-nodered-apply-merged.sh' '$mergedRemote'"
  if ($LASTEXITCODE -ne 0) {
    throw "Node-RED POST /flows 실패 (원격 종료 코드: $LASTEXITCODE). Pi에서 merged JSON·node-red-log 확인."
  }
} finally {
  Remove-Item -Force $tmp -ErrorAction SilentlyContinue
}

if ($SeedCronusEnvironment) {
  Write-Host "=== CronusFarm DB 시드(SQLite + Influx) ===" -ForegroundColor Cyan
  $purgeArg = ""
  if ($SeedCronusPurge) { $purgeArg = "--purge-influx" }
  & ssh @SshOpts "${PiUser}@${PiHost}" "CRONUS_ROOT='$RemoteCronusRoot' bash '$remoteScripts/pi-seed-cronusfarm-environment.sh' $purgeArg"
}

if ($SkipArduino) {
  Write-Host "완료: Node-RED 플로우 배포 (Arduino 업로드는 생략됨)" -ForegroundColor Green
} else {
  Write-Host "완료: Arduino(upcode) + Node-RED 플로우 배포" -ForegroundColor Green
}
