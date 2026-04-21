param(
  [string] $PiHost = "",
  [string] $PiHostLan = "",
  [string] $PiHostWan = "ida.mango-larch.ts.net",
  [string] $PiUser = "dooly",
  [string] $RemoteCronusRoot = "/home/dooly/CronusFarm",
  [switch] $SkipArduino,
  [switch] $ApplyNodeRed,
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
& ssh @SshOpts "${PiUser}@${PiHost}" "mkdir -p '$remoteNodered' '$remoteScripts'"

Write-Host "=== Node-RED: 플로우 JSON 동기화 -> $remoteNodered ===" -ForegroundColor Cyan
& scp @SshOpts "$mqttPath" "${PiUser}@${PiHost}:$remoteNodered/flows_cronusfarm_mqtt.json"
& scp @SshOpts "$dashPath" "${PiUser}@${PiHost}:$remoteNodered/flows_cronusfarm_dashboard.json"
& scp @SshOpts "$devFlowPath" "${PiUser}@${PiHost}:$remoteNodered/flows_cronusfarm_devflow_flow.json"

$applySh = Join-Path $PSScriptRoot "pi-nodered-apply-merged.sh"
if (-not (Test-Path $applySh)) {
  throw "pi-nodered-apply-merged.sh 없음: $applySh"
}
& scp @SshOpts "$applySh" "${PiUser}@${PiHost}:$remoteScripts/pi-nodered-apply-merged.sh"
& ssh @SshOpts "${PiUser}@${PiHost}" "chmod +x '$remoteScripts/pi-nodered-apply-merged.sh'"

if (-not $ApplyNodeRed) {
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
  $mergedBody = Merge-NrJsonArrays @($mqttPath, $dashPath, $devFlowPath)
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

if ($SkipArduino) {
  Write-Host "완료: Node-RED 플로우 배포 (Arduino 업로드는 생략됨)" -ForegroundColor Green
} else {
  Write-Host "완료: Arduino(upcode) + Node-RED 플로우 배포" -ForegroundColor Green
}
