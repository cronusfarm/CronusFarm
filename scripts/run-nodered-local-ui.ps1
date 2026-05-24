param(
  [int] $Port = 1881,
  [string] $UserDir = "",
  [switch] $Safe,
  [switch] $SyncFlows
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

Assert-Command "node"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$defaultUserDir = Join-Path $repoRoot ".nodered-local"
if ([string]::IsNullOrWhiteSpace($UserDir)) {
  $UserDir = $defaultUserDir
}

if (-not (Test-Path $UserDir)) {
  New-Item -ItemType Directory -Force -Path $UserDir | Out-Null
}

$applySettings = Join-Path $PSScriptRoot "apply-nodered-local-settings.ps1"
if (Test-Path $applySettings) {
  & $applySettings -UserDir $UserDir -RepoRoot $repoRoot
}

Write-Host "CronusFarm 로컬 Node-RED(UI) 실행" -ForegroundColor Cyan
Write-Host "- Port    : $Port"
Write-Host "- userDir : $UserDir"
Write-Host ""

$netPs1 = Join-Path $PSScriptRoot "cronusfarm-network.ps1"
if (Test-Path $netPs1) {
  . $netPs1
  # LAN(192.168.60.222) 우선 — Tailscale 고정 시 RTT 2~4s·요청 6s+ 병목
  $ep = Get-CronusFarmPiEndpoint
  Set-CronusFarmPiEnv $ep
  $env:CRONUSFARM_SQLITE_BRIDGE_PORT = [string]$ep.SqlitePort
} else {
  if (-not $env:CRONUSFARM_PI_HOST) { $env:CRONUSFARM_PI_HOST = "ida.mango-larch.ts.net" }
  if (-not $env:CRONUSFARM_MQTT_PORT) { $env:CRONUSFARM_MQTT_PORT = "1883" }
  if (-not $env:CRONUSFARM_SQLITE_BRIDGE_URL) {
    $piHost = $env:CRONUSFARM_PI_HOST.TrimEnd('/')
    $env:CRONUSFARM_SQLITE_BRIDGE_URL = "http://${piHost}:18766"
  }
}
$env:CRONUSFARM_LOCAL_DEV = "1"

$mergedDeploy = Join-Path $repoRoot "nodered\merged-deploy.json"
$flowsPath = Join-Path $UserDir "flows.json"
if ($SyncFlows) {
  if (-not (Test-Path $mergedDeploy)) {
    throw "merged-deploy.json 없음: python scripts\merge_nodered_deploy.py --use-split 먼저 실행"
  }
  Copy-Item -Force $mergedDeploy $flowsPath
  Write-Host "[SyncFlows] merged-deploy.json -> flows.json" -ForegroundColor Yellow
}

Write-Host "[원격 Pi] $($env:CRONUSFARM_PI_HOST) | MQTT $($env:CRONUSFARM_MQTT_PORT) | SQLite: $($env:CRONUSFARM_SQLITE_BRIDGE_URL)" -ForegroundColor DarkGray
Write-Host "           merge 후 -SyncFlows 로 flows 동기화 가능" -ForegroundColor DarkGray
Write-Host ""

$brokerPat = '"broker"\s*:\s*"127\.0\.0\.1"'
if ((Test-Path $flowsPath) -and (Select-String -Path $flowsPath -Pattern $brokerPat -Quiet)) {
  Write-Host "[WARN] flows.json MQTT broker 가 127.0.0.1 입니다. merge + -SyncFlows 권장." -ForegroundColor Yellow
  Write-Host ""
}

Write-Host "편집기: http://127.0.0.1:$Port/" -ForegroundColor Green
Write-Host "Dashboard 1 (/ui): http://127.0.0.1:$Port/ui/" -ForegroundColor Green

$nodeVer = (node -v).TrimStart('v')
$nodeMaj = [int]($nodeVer.Split('.')[0])
if ($nodeMaj -ge 22) {
  Write-Host "[INFO] Node.js v$nodeVer : Node-RED 4.x 필요 (3.x는 util.log 오류)." -ForegroundColor Yellow
}

$localNr = Join-Path $UserDir "node_modules\node-red\red.js"
$nrNpmPkgs = 'node-red@4 node-red-dashboard@3.6.6'

if (-not (Test-Path $localNr)) {
  $lines = @(
    '로컬 Node-RED(red.js)가 없습니다. 설치:'
    ''
    ('  cd ' + $UserDir)
    ('  npm install ' + $nrNpmPkgs)
    ''
    '3.x만 있으면 node_modules 삭제 후 위 npm install 반복'
  )
  throw ($lines -join [Environment]::NewLine)
}

$nrPkgJson = Join-Path $UserDir "node_modules\node-red\package.json"
if (Test-Path $nrPkgJson) {
  $nrMeta = Get-Content $nrPkgJson -Raw -Encoding UTF8 | ConvertFrom-Json
  $nrInstalled = [string]$nrMeta.version
  if ($nrInstalled -match '^3\.' -and $nodeMaj -ge 22) {
    $lines = @(
      ('node-red ' + $nrInstalled + ' + Node.js v' + $nodeVer + ' : Node-RED 3.x 는 Node 22+ 에서 기동 불가')
      ''
      ('  cd ' + $UserDir)
      '  Remove-Item -Recurse -Force node_modules'
      '  Remove-Item -Force package-lock.json -ErrorAction SilentlyContinue'
      ('  npm install ' + $nrNpmPkgs)
      ''
      'Then run this script again.'
    )
    throw ($lines -join [Environment]::NewLine)
  }
}

$nodeArgs = @($localNr, '-p', "$Port", '-u', $UserDir)
if ($Safe) {
  $nodeArgs += '--safe'
}

& node @nodeArgs
