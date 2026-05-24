# Google OAuth 마무리: deploy/env/oauth2-proxy.env 또는 환경변수 → Pi 적용
# 1) example 복사 후 편집:
#      copy deploy\env\oauth2-proxy.env.example deploy\env\oauth2-proxy.env
# 2) CLIENT_ID / CLIENT_SECRET 채운 뒤 이 스크립트 실행
param(
  [string]$PiHost = "ida.mango-larch.ts.net"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$envFile = Join-Path $root "deploy\env\oauth2-proxy.env"

if (Test-Path $envFile) {
  Get-Content $envFile | ForEach-Object {
    if ($_ -match '^\s*#' -or $_ -notmatch '^\s*([A-Za-z0-9_]+)\s*=\s*(.*)$') { return }
    $n = $Matches[1]
    $v = $Matches[2].Trim().Trim('"')
    Set-Item -Path "Env:$n" -Value $v
  }
  Write-Host "loaded: deploy/env/oauth2-proxy.env"
}

& (Join-Path $PSScriptRoot "pi-apply-oauth2-credentials.ps1") -PiHost $PiHost
