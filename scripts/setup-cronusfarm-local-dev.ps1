# CronusFarm 로컬 개발 환경 일괄 설정 (Windows PowerShell)
# - 분할 플로우 머지 → merged-deploy.json
# - .nodered-local\flows.json 동기화 (Pi/Tailscale 브로커·수정된 inject 등 반영)
# - .nodered-local npm 의존성 설치(선택)
#
# 사용:
#   .\scripts\setup-cronusfarm-local-dev.ps1
#   .\scripts\setup-cronusfarm-local-dev.ps1 -SkipNpm
# Pi 반영·Mosquitto/브리지는 이 스크립트 범위 밖(SSH로 별도 적용).

param(
  [switch] $SkipNpm,
  [switch] $SkipMerge
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

$scriptDir = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
$repoRoot = (Resolve-Path (Join-Path $scriptDir "..")).Path
$nrDir = Join-Path $repoRoot ".nodered-local"
$merged = Join-Path $repoRoot "nodered\merged-deploy.json"
$mergePy = Join-Path $scriptDir "merge_nodered_deploy.py"

Write-Host "=== CronusFarm 로컬 개발 환경 설정 ===" -ForegroundColor Cyan
Write-Host "repoRoot: $repoRoot"

if (-not $SkipMerge) {
  if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "python 이 PATH 에 없습니다. Python 3 설치 후 다시 실행하세요."
  }
  Write-Host "--- merge_nodered_deploy.py --use-split ---" -ForegroundColor DarkCyan
  Push-Location $repoRoot
  try {
    & python $mergePy --use-split
    if ($LASTEXITCODE -ne 0) { throw "merge_nodered_deploy.py 실패 (exit $LASTEXITCODE)" }
  } finally {
    Pop-Location
  }
} else {
  Write-Host "[SkipMerge] 머지 생략" -ForegroundColor Yellow
}

if (-not (Test-Path $merged)) {
  throw "merged-deploy.json 없음: $merged"
}

if (-not (Test-Path $nrDir)) {
  New-Item -ItemType Directory -Force -Path $nrDir | Out-Null
}

$flowsOut = Join-Path $nrDir "flows.json"
Copy-Item -Force $merged $flowsOut
Write-Host "--- flows 동기화 완료 ---" -ForegroundColor Green
Write-Host "         $flowsOut"

$applySettings = Join-Path $scriptDir "apply-nodered-local-settings.ps1"
if (Test-Path $applySettings) {
  & $applySettings -UserDir $nrDir -RepoRoot $repoRoot
}

if (-not $SkipNpm) {
  $pkg = Join-Path $nrDir "package.json"
  if (Test-Path $pkg) {
    if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
      Write-Host "[WARN] npm 없음 — node_modules 설치 생략" -ForegroundColor Yellow
    } else {
      Write-Host "--- npm install (.nodered-local) ---" -ForegroundColor DarkCyan
      Push-Location $nrDir
      try {
        npm install
        if ($LASTEXITCODE -ne 0) { throw "npm install 실패 (exit $LASTEXITCODE)" }
      } finally {
        Pop-Location
      }
    }
  } else {
    Write-Host "[INFO] package.json 없음 — run-nodered-local-ui.ps1 안내에 따라 수동 npm install" -ForegroundColor DarkYellow
  }
}

Write-Host ""
Write-Host "다음 단계:" -ForegroundColor Cyan
Write-Host "  1) NR 기동: .\scripts\run-nodered-local-ui.ps1   (또는 동일 스크립트에 -SyncFlows 는 이미 flows 복사됨)"
Write-Host "  2) 브라우저: http://127.0.0.1:1881/ — 필요 시 Deploy"
Write-Host "  3) 로컬 SQLite 브리지만 쓸 때: 다른 터미널에서 python scripts\cronusfarm_sqlite_bridge.py"
Write-Host "     원격 Pi 브리지 URL 유지 시 env: CRONUSFARM_SQLITE_BRIDGE_URL (run-nodered-local-ui.ps1 기본값 참고)"
Write-Host "  4) Pi: Mosquitto 0.0.0.0:1883 / systemd 브리지 0.0.0.0:18766 — docs\raspi_setup.md"
Write-Host ""
Write-Host "완료." -ForegroundColor Green
