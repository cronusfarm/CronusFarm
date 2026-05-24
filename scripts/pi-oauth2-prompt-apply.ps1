# Google OAuth Web 클라이언트 ID/SECRET 입력 → deploy/env/oauth2-proxy.env → Pi 적용
# PowerShell에서 직접 실행 (채팅에 비밀 붙이지 말 것)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$envFile = Join-Path $root "deploy\env\oauth2-proxy.env"

Write-Host ""
Write-Host "=== CronusFarm Google OAuth (웹 클라이언트) ===" -ForegroundColor Cyan
Write-Host "Console: API 및 서비스 > 사용자 인증 정보 > OAuth 클라이언트 ID > 웹 애플리케이션"
Write-Host "JavaScript 원본:     https://cronusfarm.duckdns.org  (경로 없음)"
Write-Host "리디렉션 URI:        https://cronusfarm.duckdns.org/oauth2/callback"
Write-Host ""

$open = Read-Host "Google Console 브라우저 열기? (Y/n)"
if ($open -ne "n" -and $open -ne "N") {
  Start-Process "https://console.cloud.google.com/apis/credentials"
  Start-Sleep -Seconds 1
  Start-Process "https://console.cloud.google.com/auth/overview"
}

$id = Read-Host "클라이언트 ID (....apps.googleusercontent.com)"
$secPlain = Read-Host "클라이언트 보안 비밀" -AsSecureString
$sec = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
  [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secPlain)
)

if (-not $id -or -not $sec) { throw "ID 또는 SECRET 비어 있음" }

@(
  "# Google OAuth — pi-oauth2-prompt-apply.ps1",
  "OAUTH2_PROXY_CLIENT_ID=$id",
  "OAUTH2_PROXY_CLIENT_SECRET=$sec",
  "OAUTH2_PROXY_REDIRECT_URL=https://cronusfarm.duckdns.org/oauth2/callback",
  "OAUTH2_PROXY_EMAIL_DOMAINS=*"
) | Set-Content -Path $envFile -Encoding UTF8

Write-Host "saved: deploy\env\oauth2-proxy.env" -ForegroundColor Green
& (Join-Path $PSScriptRoot "pi-finish-oauth2-login.ps1")
