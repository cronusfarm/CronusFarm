# farm-ui Pi 배포 직후: 권한 복구 + JS HTTP 200 검증 (fix-farm-ui / deploy-cronusfarm 공용)
param(
  [Parameter(Mandatory = $true)][string] $PiHost,
  [Parameter(Mandatory = $true)][string] $PiUser,
  [Parameter(Mandatory = $true)][string] $RemoteDist,
  [Parameter(Mandatory = $true)][string] $FarmUiDistLocal,
  [Parameter(Mandatory = $true)][string] $ScriptDir,
  [string[]] $SshOpts = @("-o", "ConnectTimeout=30", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=accept-new")
)

$ErrorActionPreference = "Stop"
$permsSh = Join-Path $ScriptDir "pi-fix-farm-ui-perms.sh"
if (-not (Test-Path $permsSh)) { throw "pi-fix-farm-ui-perms.sh 없음: $permsSh" }

& scp @SshOpts $permsSh "${PiUser}@${PiHost}:/tmp/pi-fix-farm-ui-perms.sh"
if ($LASTEXITCODE -ne 0) { throw "scp pi-fix-farm-ui-perms.sh failed" }
& ssh @SshOpts "${PiUser}@${PiHost}" "sed -i 's/\r$//' /tmp/pi-fix-farm-ui-perms.sh 2>/dev/null || true; bash /tmp/pi-fix-farm-ui-perms.sh"
if ($LASTEXITCODE -ne 0) { throw "pi-fix-farm-ui-perms.sh failed" }

$indexHtml = Join-Path $FarmUiDistLocal "index.html"
$jsName = (Select-String -Path $indexHtml -Pattern 'assets/(index-[^"]+\.js)' | ForEach-Object { $_.Matches[0].Groups[1].Value } | Select-Object -First 1)
if (-not $jsName) { throw "dist/index.html 에서 JS 번들명을 찾지 못함" }
& ssh @SshOpts "${PiUser}@${PiHost}" "test -r '$RemoteDist/assets/$jsName' && curl -sf -o /dev/null -w '%{http_code}' http://127.0.0.1/farm/ui/assets/$jsName | grep -q '^200$'"
if ($LASTEXITCODE -ne 0) { throw "farm-ui JS HTTP 검증 실패: /farm/ui/assets/$jsName" }
Write-Host "OK: farm-ui perms + HTTP 200 ($jsName)" -ForegroundColor DarkGray
