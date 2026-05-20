# CronusFarm 로컬 Node-RED userDir — settings.js 에 httpStatic(/cronusfarm-static) 보장
# Chart.js·설정 iframe 등 nodered/dashboard 정적 파일 서빙 (Bed 타임라인 그래프)

param(
  [string] $UserDir = "",
  [string] $RepoRoot = ""
)

$ErrorActionPreference = "Stop"

$scriptDir = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
if ([string]::IsNullOrWhiteSpace($RepoRoot)) {
  $RepoRoot = (Resolve-Path (Join-Path $scriptDir "..")).Path
}
if ([string]::IsNullOrWhiteSpace($UserDir)) {
  $UserDir = Join-Path $RepoRoot ".nodered-local"
}

$dashRoot = (Join-Path $RepoRoot "nodered\dashboard")
if (-not (Test-Path $dashRoot)) {
  throw "dashboard 폴더 없음: $dashRoot"
}
$dashRootJs = ($dashRoot -replace '\\', '/')

if (-not (Test-Path $UserDir)) {
  New-Item -ItemType Directory -Force -Path $UserDir | Out-Null
}

$settingsPath = Join-Path $UserDir "settings.js"
$chartJs = Join-Path $dashRoot "vendor\chart.umd.min.js"
if (-not (Test-Path $chartJs)) {
  Write-Host "[WARN] chart.umd.min.js 없음: $chartJs" -ForegroundColor Yellow
}

# Node-RED 4: httpStatic=디스크 경로, httpStaticRoot=URL 접두사 (배열 path/root 는 표시가 뒤바뀌어 404 남)
$httpStaticBlock = @"
    httpStatic: '$dashRootJs',
    httpStaticRoot: '/cronusfarm-static/',
"@

function Write-SettingsMinimal {
  param([string] $Path)
  $content = @"
// CronusFarm 로컬 개발 — nodered/dashboard 정적 파일 (Chart.js, 설정 HTML)
module.exports = {
$httpStaticBlock
};
"@
  [System.IO.File]::WriteAllText($Path, $content, (New-Object System.Text.UTF8Encoding $false))
}

function Repair-BrokenCommentedHttpStatic {
  param([string] $Js)
  # 잘못된 삽입: //httpStatic: [ 아래에 주석 없는 { path: '/cronusfarm-static' ... }
  if ($Js -match "(?ms)//httpStatic:\s*\[\s*\r?\n\s*\{\s*path:\s*['""]/cronusfarm-static") {
    return [regex]::Replace(
      $Js,
      "(?ms)//httpStatic:\s*\[[\s\S]*?//\],",
      $httpStaticBlock.TrimEnd(','),
      1
    )
  }
  return $Js
}

function Set-ActiveHttpStatic {
  param([string] $Js)
  $js2 = Repair-BrokenCommentedHttpStatic $Js
  if ($js2 -match "(?m)^\s*httpStatic\s*:\s*'") {
    $js2 = [regex]::Replace($js2, "(?m)^\s*httpStatic\s*:\s*'[^']*'", "    httpStatic: '$dashRootJs'", 1)
    if ($js2 -match "(?m)^\s*//\s*httpStaticRoot\s*:") {
      $js2 = [regex]::Replace($js2, "(?m)^\s*//\s*httpStaticRoot\s*:\s*'[^']*'", "    httpStaticRoot: '/cronusfarm-static/'", 1)
    } elseif ($js2 -notmatch "(?m)^\s*httpStaticRoot\s*:") {
      $js2 = [regex]::Replace($js2, "(?m)^\s*httpStatic\s*:\s*'[^']*',?", "`${0}`n    httpStaticRoot: '/cronusfarm-static/',", 1)
    } else {
      $js2 = [regex]::Replace($js2, "(?m)^\s*httpStaticRoot\s*:\s*'[^']*'", "    httpStaticRoot: '/cronusfarm-static/'", 1)
    }
    return $js2
  }
  if ($js2 -match "(?m)^\s*httpStatic\s*:\s*\[") {
    $js2 = [regex]::Replace($js2, "(?ms)^\s*httpStatic\s*:\s*\[[\s\S]*?\],", $httpStaticBlock.TrimEnd(','), 1)
    return $js2
  }
  if ($js2 -match "/cronusfarm-static") {
    return $js2
  }
  if ($js2 -match "(?ms)//httpStatic:\s*\[") {
    return [regex]::Replace($js2, "(?ms)//httpStatic:\s*\[[\s\S]*?//\],", $httpStaticBlock.TrimEnd(','), 1)
  }
  if ($js2 -match "module\.exports\s*=\s*\{") {
    return [regex]::Replace($js2, "(module\.exports\s*=\s*\{)", "`${1}`n$httpStaticBlock`n", 1)
  }
  throw "settings.js 형식을 인식하지 못했습니다: $settingsPath"
}

if (-not (Test-Path $settingsPath)) {
  Write-SettingsMinimal $settingsPath
  Write-Host "[OK] settings.js 생성: $settingsPath" -ForegroundColor Green
  return
}

$js = Get-Content $settingsPath -Raw -Encoding UTF8
$js2 = Set-ActiveHttpStatic $js
if ($js2 -eq $js) {
  Write-Host "[OK] settings.js httpStatic 이미 있음" -ForegroundColor DarkGray
} else {
  [System.IO.File]::WriteAllText($settingsPath, $js2, (New-Object System.Text.UTF8Encoding $false))
  Write-Host "[OK] settings.js httpStatic 적용" -ForegroundColor Green
}
