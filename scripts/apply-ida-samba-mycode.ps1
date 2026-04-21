# Thalia 등 개발 PC에서 실행: ida 의 Samba [MyCode] path 를 CronusFarm 으로 맞춤(pi 스크립트 업로드 후 sudo 실행)
param(
  [string] $PiHost = "",
  [string] $PiHostLan = "",
  [string] $PiHostWan = "ida.mango-larch.ts.net",
  [string] $PiUser = "dooly"
)

$ErrorActionPreference = "Stop"

function Assert-Command($name) {
  if (-not (Get-Command $name -ErrorAction SilentlyContinue)) {
    throw "필수 명령을 찾지 못했습니다: $name"
  }
}
Assert-Command "ssh"
Assert-Command "scp"

$SshOpts = @("-o", "ConnectTimeout=30", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=accept-new")
. (Join-Path $PSScriptRoot "pi-host-resolve.ps1")
$PiHost = Get-CronusPiHost -PiHost $PiHost -PiHostLan $PiHostLan -PiHostWan $PiHostWan -PiUser $PiUser

$sh = Join-Path $PSScriptRoot "pi-apply-samba-mycode-cronusfarm.sh"
if (-not (Test-Path $sh)) {
  throw "스크립트 없음: $sh"
}

$remote = "/tmp/pi-apply-samba-mycode-cronusfarm.sh"
& scp @SshOpts $sh "${PiUser}@${PiHost}:${remote}"
& ssh @SshOpts "${PiUser}@${PiHost}" "chmod +x '$remote' && sudo bash '$remote'"
if ($LASTEXITCODE -ne 0) {
  throw "ida 적용 실패(ssh 종료 코드: $LASTEXITCODE)"
}

Write-Host "ida Samba [MyCode] 적용 완료." -ForegroundColor Green
