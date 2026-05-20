# best.onnx 를 CronusFarm/Hailo/best.onnx 로 복사하고, 선택 시 WSL(x86)에서 HEF 컴파일·Pi 동기화
#
# 사용 예:
#   .\scripts\cronusfarm-hailo-prepare-best.ps1 -OnnxPath "D:\models\best.onnx"
#   .\scripts\cronusfarm-hailo-prepare-best.ps1   # 자동 탐색(Hailo\best.onnx, runs\...\best.onnx, Downloads 등)
#   .\scripts\cronusfarm-hailo-prepare-best.ps1 -OnnxPath "..." -RunCompileInWsl   # WSL에 hailo DFC 설치 후
#   .\scripts\cronusfarm-hailo-prepare-best.ps1 -DeployToPi -HefOnly   # best.hef 만 Pi 업로드 + AI 설정
#   .\scripts\cronusfarm-hailo-prepare-best.ps1 -DeployToPi -SetupOnPi # 업로드 후 pi-hailo-setup.sh 실행

param(
  [string] $OnnxPath = "",
  [string] $PiUser = "dooly",
  [string] $PiHost = "",
  [string] $PiHostLan = "",
  [string] $PiHostWan = "ida.mango-larch.ts.net",
  [string] $RemoteCronusRoot = "/home/dooly/CronusFarm",
  [switch] $DeployToPi,
  [switch] $RunCompileInWsl,
  [switch] $HefOnly,
  [switch] $SetupOnPi
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

$hefLocal = Join-Path $hailoDir "best.hef"
if ($HefOnly -and -not (Test-Path -LiteralPath $hefLocal)) {
  throw "Hailo\best.hef 가 없습니다."
}

if (-not $HefOnly) {
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
  $remoteDeploySd = "$RemoteCronusRoot/deploy/systemd"
  & ssh @SshRemoteOpts "${PiUser}@${PiHost}" "mkdir -p '$remoteHailo' '$remoteScripts' '$remoteDeploySd'"
  if ($HefOnly) {
    & scp @SshScpOpts $hefLocal "${PiUser}@${PiHost}:$remoteHailo/best.hef"
    Write-Host "OK: best.hef -> Pi $remoteHailo" -ForegroundColor Green
  } else {
    Get-ChildItem -Path $hailoDir -File -ErrorAction SilentlyContinue | ForEach-Object {
      & scp @SshScpOpts $_.FullName "${PiUser}@${PiHost}:$remoteHailo/$($_.Name)"
    }
    Write-Host "OK: Pi $remoteHailo 동기화 완료" -ForegroundColor Green
  }
  $hailoPy = Join-Path $CronusDeployScriptDir "cronusfarm_hailo_stream.py"
  $setupSh = Join-Path $CronusDeployScriptDir "pi-hailo-setup.sh"
  $svcSrc = Join-Path $repoRoot "deploy\systemd\cronusfarm-hailo-stream.service"
  if (Test-Path -LiteralPath $hailoPy) {
    & scp @SshScpOpts $hailoPy "${PiUser}@${PiHost}:$remoteScripts/cronusfarm_hailo_stream.py"
  }
  if (Test-Path -LiteralPath $setupSh) {
    & scp @SshScpOpts $setupSh "${PiUser}@${PiHost}:$remoteScripts/pi-hailo-setup.sh"
    & ssh @SshRemoteOpts "${PiUser}@${PiHost}" "chmod +x '$remoteScripts/pi-hailo-setup.sh'; sed -i 's/\r$//' '$remoteScripts/pi-hailo-setup.sh' 2>/dev/null || true"
  }
  if (Test-Path -LiteralPath $svcSrc) {
    & scp @SshScpOpts $svcSrc "${PiUser}@${PiHost}:$remoteDeploySd/cronusfarm-hailo-stream.service"
  }
  if ($SetupOnPi -or $HefOnly) {
    Write-Host "=== Pi: pi-hailo-setup.sh (systemd + Hailo 스트림) ===" -ForegroundColor Cyan
    & ssh @SshRemoteOpts "${PiUser}@${PiHost}" "bash '$remoteScripts/pi-hailo-setup.sh'"
    if ($LASTEXITCODE -ne 0) {
      throw "pi-hailo-setup.sh 실패 (exit $LASTEXITCODE). Pi에서 journalctl -u cronusfarm-hailo-stream -n 80"
    }
  }
}

if (-not $RunCompileInWsl -and -not $DeployToPi) {
  Write-Host "다음: WSL(x86)+DFC 에서 .\scripts\linux-x86-hailo-dfc-compile-best.sh 실행 후 -DeployToPi 또는 deploy-cronusfarm-pi.ps1" -ForegroundColor DarkYellow
}
