# Pi에 Google OAuth CLIENT_ID/SECRET 반영 후 oauth2-proxy·nginx 로그인 적용
param(
  [string]$PiHost,
  [string]$ClientId,
  [string]$ClientSecret,
  [string]$RedirectUrl,
  [string]$EmailDomains
)

$ErrorActionPreference = "Stop"
if (-not $PiHost) { $PiHost = "ida.mango-larch.ts.net" }
if (-not $RedirectUrl) { $RedirectUrl = "https://cronusfarm.duckdns.org/oauth2/callback" }
if (-not $EmailDomains) { $EmailDomains = "*" }
if (-not $ClientId) { $ClientId = $env:OAUTH2_PROXY_CLIENT_ID }
if (-not $ClientSecret) { $ClientSecret = $env:OAUTH2_PROXY_CLIENT_SECRET }

if (-not $ClientId -or -not $ClientSecret) {
  $localEnv = Join-Path (Split-Path -Parent $PSScriptRoot) "deploy\env\oauth2-proxy.env"
  if (Test-Path $localEnv) {
    Get-Content $localEnv | ForEach-Object {
      if ($_ -match '^\s*#' -or $_ -notmatch '^\s*([A-Za-z0-9_]+)\s*=\s*(.*)$') { return }
      $n = $Matches[1]
      $v = $Matches[2].Trim().Trim('"').Trim()
      if ($n -eq 'OAUTH2_PROXY_CLIENT_ID') { $ClientId = $v }
      if ($n -eq 'OAUTH2_PROXY_CLIENT_SECRET') { $ClientSecret = $v }
    }
  }
}
if ($ClientId) { $ClientId = $ClientId.Trim() }
if ($ClientSecret) { $ClientSecret = $ClientSecret.Trim() }

if (-not $ClientId -or -not $ClientSecret) {
  throw "OAUTH2_PROXY_CLIENT_ID/SECRET 없음. deploy\env\oauth2-proxy.env 편집 후 pi-finish-oauth2-login.ps1 실행"
}

$envBody = @"
# Google OAuth (pi-apply-oauth2-credentials.ps1)
OAUTH2_PROXY_CLIENT_ID=$ClientId
OAUTH2_PROXY_CLIENT_SECRET=$ClientSecret
OAUTH2_PROXY_REDIRECT_URL=$RedirectUrl
OAUTH2_PROXY_EMAIL_DOMAINS=$EmailDomains
"@

$tmp = [System.IO.Path]::GetTempFileName()
[System.IO.File]::WriteAllText($tmp, $envBody.Replace("`r`n", "`n"), [System.Text.UTF8Encoding]::new($false))
scp -o ConnectTimeout=20 -o BatchMode=yes $tmp "dooly@${PiHost}:/tmp/oauth2-proxy.env"
Remove-Item $tmp -Force

$remote = @'
set -e
sudo install -m 0640 -o root -g dooly /tmp/oauth2-proxy.env /etc/cronusfarm/oauth2-proxy.env
rm -f /tmp/oauth2-proxy.env
bash ~/CronusFarm/scripts/pi-install-oauth2-proxy-google.sh
bash ~/CronusFarm/scripts/pi-fix-farm-ui-perms.sh 2>/dev/null || true
systemctl is-active cronusfarm-oauth2-proxy
curl -fsS -m 2 -o /dev/null -w "oauth2_auth:%{http_code}\n" http://127.0.0.1:4180/oauth2/auth || true
'@

ssh -T -o ConnectTimeout=25 -o BatchMode=yes "dooly@$PiHost" $remote
Write-Host "OK - https://cronusfarm.duckdns.org/farm/ui/ (Google 로그인 확인)"
