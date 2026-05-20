# CronusFarm 설정 SPA (farm-ui) 빌드
$ErrorActionPreference = "Stop"
$scriptDir = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
$farmUi = Join-Path (Split-Path $scriptDir -Parent) "farm-ui"
if (-not (Test-Path $farmUi)) {
  throw "farm-ui 없음: $farmUi"
}

Push-Location $farmUi
try {
  if (-not (Test-Path "node_modules")) {
    Write-Host "=== farm-ui: npm install ===" -ForegroundColor Cyan
    npm install
    if ($LASTEXITCODE -ne 0) { throw "npm install 실패" }
  }
  Write-Host "=== farm-ui: npm run build ===" -ForegroundColor Cyan
  npm run build
  if ($LASTEXITCODE -ne 0) { throw "npm run build 실패" }
  $dist = Join-Path $farmUi "dist\index.html"
  if (-not (Test-Path $dist)) {
    throw "dist/index.html 없음 — base=/farm/ui/ 빌드 확인"
  }
  Write-Host "[OK] farm-ui dist: $dist" -ForegroundColor Green
} finally {
  Pop-Location
}
