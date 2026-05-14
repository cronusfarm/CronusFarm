# best.onnx 를 CronusFarm/Hailo/best.onnx 로 복사하고, 선택 시 WSL(x86)에서 HEF 컴파일·Pi 동기화
#
# 사용 예:
#   .\scripts\cronusfarm-hailo-prepare-best.ps1 -OnnxPath "D:\models\best.onnx"
#   .\scripts\cronusfarm-hailo-prepare-best.ps1   # 자동 탐색(Hailo\best.onnx, runs\...\best.onnx, Downloads 등)
#   .\scripts\cronusfarm-hailo-prepare-best.ps1 -OnnxPath "..." -RunCompileInWsl   # WSL에 hailo DFC 설치 후
#   .\scripts\cronusfarm-hailo-prepare-best.ps1 -OnnxPath "..." -DeployToPi       # Pi에 Hailo/ 업로드만

param(
  [string] $OnnxPath = "",
  [string] $PiUser = "dooly",
  [string] $PiHost = "",
  [string] $PiHostLan = "192.168.0.222",
  [string] $PiHostWan = "ida.mango-larch.ts.net",
  [string] $RemoteCronusRoot = "/home/dooly/CronusFarm",
  [switch] $DeployToPi,
  [switch] $RunCompileInWsl
)

$ErrorActionPreference = "Stop"

$CronusDeployScriptDir = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
$repoRoot = Split-Path $CronusDeployScriptDir -Parent
. (Join-Path $CronusDeployScriptDir "pi-host-resolve.ps1")

function ConvertTo-WslPath([string] $WindowsPath) {
  $p = $WindowsPath.Trim()
  if ($p -match '^([A-Za-z]):\\(.*)$') {
    $d = $Matches[1].ToLowerInvariant()
    $rest = $Matches[2] -replace '\\', '/'
    return "/mnt/$d/$rest"
  }
  throw "WSL 경로 변환 불가: $WindowsPath"
}

$hailoDir = Join-Path $repoRoot "Hailo"
if (-not (Test-Path -LiteralPath $hailoDir)) {
  New-Item -ItemType Directory -Path $hailoDir -Force | Out-Null
}

if ([string]::IsNullOrWhiteSpace($OnnxPath)) {
  $candidates = @(
    (Join-Path $repoRoot "Hailo\best.onnx"),
    (Join-Path $repoRoot "runs\detect\train\weights\best.onnx"),
    (Join-Path $repoRoot "runs\detect\train2\weights\best.onnx"),
    (Join-Path $repoRoot "runs\detect\train3\weights\best.onnx"),
    (Join-Path $env:USERPROFILE "Downloads\best.onnx"),
    (Join-Path $env:USERPROFILE "OneDrive\Downloads\best.onnx")
  )
  foreach ($p in $candidates) {
    if (Test-Path -LiteralPath $p) {
      $OnnxPath = $p
      Write-Host "[Hailo] 자동 선택: $OnnxPath" -ForegroundColor Cyan
      break
    }
  }
}

if ([string]::IsNullOrWhiteSpace($OnnxPath) -or -not (Test-Path -LiteralPath $OnnxPath)) {
  throw "best.onnx 을 찾지 못했습니다. -OnnxPath 로 지정하거나 Colab/학습 산출물을 Hailo\best.onnx 또는 Downloads\best.onnx 로 두세요."
}

$dest = Join-Path $hailoDir "best.onnx"
$srcFull = (Get-Item -LiteralPath $OnnxPath).FullName
$dstExists = Test-Path -LiteralPath $dest
$dstFull = if ($dstExists) { (Get-Item -LiteralPath $dest).FullName } else { "" }
if ($srcFull -ieq $dstFull) {
  Write-Host "OK: 이미 $dest (복사 생략)" -ForegroundColor Green
} else {
  Copy-Item -LiteralPath $OnnxPath -Destination $dest -Force
  Write-Host "OK: $dest" -ForegroundColor Green
}

if ($RunCompileInWsl) {
  $shLinux = ConvertTo-WslPath (Join-Path $CronusDeployScriptDir "linux-x86-hailo-dfc-compile-best.sh")
  $hailoLinux = ConvertTo-WslPath $hailoDir
  Write-Host "=== WSL: Hailo DFC 컴파일 (x86_64, hailo CLI 필요) ===" -ForegroundColor Cyan
  wsl -e bash -lc "set -e; chmod +x '$shLinux'; export CRONUSFARM_HAILO_DIR='$hailoLinux'; '$shLinux'"
}

if ($DeployToPi) {
  $PiHost = Get-CronusPiHost -PiHost $PiHost -PiHostLan $PiHostLan -PiHostWan $PiHostWan -PiUser $PiUser
  $SshScpOpts = @(
    "-o", "ConnectTimeout=30",
    "-o", "BatchMode=yes",
    "-o", "StrictHostKeyChecking=accept-new"
  )
  $SshRemoteOpts = @(
    "-T",
    "-o", "ConnectTimeout=30",
    "-o", "BatchMode=yes",
    "-o", "StrictHostKeyChecking=accept-new"
  )
  $remoteHailo = "$RemoteCronusRoot/Hailo"
  $remoteScripts = "$RemoteCronusRoot/scripts"
  & ssh @SshRemoteOpts "${PiUser}@${PiHost}" "mkdir -p '$remoteHailo'"
  Get-ChildItem -Path $hailoDir -File -ErrorAction SilentlyContinue | ForEach-Object {
    & scp @SshScpOpts $_.FullName "${PiUser}@${PiHost}:$remoteHailo/$($_.Name)"
  }
  $hailoPy = Join-Path $CronusDeployScriptDir "cronusfarm_hailo_stream.py"
  if (Test-Path -LiteralPath $hailoPy) {
    & scp @SshScpOpts $hailoPy "${PiUser}@${PiHost}:$remoteScripts/cronusfarm_hailo_stream.py"
  }
  Write-Host "OK: Pi $remoteHailo 동기화 완료" -ForegroundColor Green
}

if (-not $RunCompileInWsl -and -not $DeployToPi) {
  Write-Host "다음: WSL(x86)+DFC 에서 .\scripts\linux-x86-hailo-dfc-compile-best.sh 실행 후 -DeployToPi 또는 deploy-cronusfarm-pi.ps1" -ForegroundColor DarkYellow
}
