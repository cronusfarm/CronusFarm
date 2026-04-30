param(
  [int] $Port = 1881,
  [string] $UserDir = "",
  [switch] $Safe
)

$ErrorActionPreference = "Stop"

function Assert-Command($name) {
  if (-not (Get-Command $name -ErrorAction SilentlyContinue)) {
    throw "필수 명령을 찾지 못했습니다: $name"
  }
}

Assert-Command "node-red"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$defaultUserDir = Join-Path $repoRoot ".nodered-local"
if ([string]::IsNullOrWhiteSpace($UserDir)) {
  $UserDir = $defaultUserDir
}

if (-not (Test-Path $UserDir)) {
  New-Item -ItemType Directory -Force -Path $UserDir | Out-Null
}

Write-Host "CronusFarm 로컬 Node-RED(UI) 실행" -ForegroundColor Cyan
Write-Host "- Port    : $Port"
Write-Host "- userDir : $UserDir"
Write-Host ""
Write-Host "브라우저: http://127.0.0.1:$Port/ui/" -ForegroundColor Green

# Node-RED v4 + Dashboard v3 조합은 socket.io 호환성으로 /ui가 비는 경우가 있어,
# 로컬 userDir에 설치된 Node-RED(v3.x)로 실행합니다(PI 전환과도 호환).
$localNr = Join-Path $UserDir "node_modules\\node-red\\red.js"
if (-not (Test-Path $localNr)) {
  throw "로컬 Node-RED(red.js)가 없습니다. 먼저 아래에서 설치하세요:`n  cd $UserDir; npm install node-red@3.1.15 node-red-dashboard@3.6.6"
}

$args = @("$localNr", "-p", "$Port", "-u", "$UserDir")
if ($Safe) { $args += "--safe" }

& node @args

