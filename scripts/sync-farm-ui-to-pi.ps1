# farm-ui dist → Pi + 권한·HTTP 검증 (scp 직후 403 방지)
param(
  [string] $PiHost = "",
  [string] $PiUser = "dooly"
)
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "pi-host-resolve.ps1")
$PiHost = Get-CronusPiHost -PiHost $PiHost -PiUser $PiUser
$SshOpts = @("-o", "ConnectTimeout=30", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=accept-new")
$repoRoot = Split-Path $PSScriptRoot -Parent
& (Join-Path $PSScriptRoot "build-farm-ui.ps1")
$localDist = Join-Path $repoRoot "farm-ui\dist"
$remoteDist = "/home/dooly/CronusFarm/farm-ui/dist"
& ssh @SshOpts "${PiUser}@${PiHost}" "mkdir -p '$remoteDist'"
Get-ChildItem -Path $localDist -Recurse -File | ForEach-Object {
  $rel = $_.FullName.Substring($localDist.Length).TrimStart('\', '/').Replace('\', '/')
  $remoteDir = "$remoteDist/$(Split-Path $rel -Parent)"
  if ($rel -match '/') {
    & ssh @SshOpts "${PiUser}@${PiHost}" "mkdir -p '$remoteDir'"
  }
  & scp @SshOpts $_.FullName "${PiUser}@${PiHost}:$remoteDist/$rel"
}
& (Join-Path $PSScriptRoot "Invoke-FarmUiPostDeploy.ps1") `
  -PiHost $PiHost -PiUser $PiUser -RemoteDist $remoteDist `
  -FarmUiDistLocal $localDist -ScriptDir $PSScriptRoot -SshOpts $SshOpts
Write-Host "OK: farm-ui synced with perms check" -ForegroundColor Green
