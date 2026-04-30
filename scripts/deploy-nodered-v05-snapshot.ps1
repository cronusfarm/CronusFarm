param(
  [string] $PiHost = "",
  [string] $PiHostLan = "",
  [string] $PiHostWan = "ida.mango-larch.ts.net",
  [string] $PiUser = "dooly",
  [string] $RemoteCronusRoot = "/home/dooly/CronusFarm"
)

$ErrorActionPreference = "Stop"

try {
  if ($PSVersionTable.PSVersion.Major -lt 6) { chcp 65001 | Out-Null }
  $utf8 = New-Object System.Text.UTF8Encoding $false
  [Console]::OutputEncoding = $utf8
  [Console]::InputEncoding = $utf8
  $OutputEncoding = $utf8
} catch { }

function Assert-Command($name) {
  if (-not (Get-Command $name -ErrorAction SilentlyContinue)) {
    throw "필수 명령을 찾지 못했습니다: $name"
  }
}
Assert-Command "ssh"
Assert-Command "scp"
Assert-Command "git"

$SshOpts = @(
  "-o", "ConnectTimeout=30",
  "-o", "BatchMode=yes",
  "-o", "StrictHostKeyChecking=accept-new"
)

. (Join-Path $PSScriptRoot "pi-host-resolve.ps1")
$PiHost = Get-CronusPiHost -PiHost $PiHost -PiHostLan $PiHostLan -PiHostWan $PiHostWan -PiUser $PiUser

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$tmpDir = Join-Path $env:TEMP ("cronusfarm-v05-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $tmpDir | Out-Null

try {
  $merged = Join-Path $tmpDir "merged-v05.json"
  # v0.5.1의 Node-RED 3개 플로우(JSON 배열) 병합
  $files = @(
    "nodered/flows_cronusfarm_mqtt.json",
    "nodered/flows_cronusfarm_dashboard.json",
    "nodered/flows_cronusfarm_devflow_flow.json"
  )
  $arr = foreach ($f in $files) {
    $raw = git -C $repoRoot show ("v0.5.1:" + $f)
    $raw = ($raw -join "`n").Trim()
    if (-not ($raw.StartsWith("[") -and $raw.EndsWith("]"))) { throw "v0.5.1 JSON 배열 아님: $f" }
    $inner = $raw.Substring(1, $raw.Length - 2).Trim()
    if ($inner.Length -gt 0) { $inner }
  }
  $body = "[" + ($arr -join ",") + "]"
  [System.IO.File]::WriteAllText($merged, $body, (New-Object System.Text.UTF8Encoding $false))

  $remoteScripts = "$RemoteCronusRoot/scripts"
  & ssh @SshOpts "${PiUser}@${PiHost}" "mkdir -p '$remoteScripts'"

  $setupSh = Join-Path $repoRoot "scripts/pi-nodered-multiplex-v05.sh"
  if (-not (Test-Path $setupSh)) { throw "setup 스크립트 없음: $setupSh" }

  Write-Host "=== v0.5.1 스냅샷 업로드: merged-v05.json + setup 스크립트 ===" -ForegroundColor Cyan
  & ssh @SshOpts "${PiUser}@${PiHost}" "mkdir -p ~/.node-red-v05"
  & scp @SshOpts "$merged" "${PiUser}@${PiHost}:~/.node-red-v05/merged-v05.json"
  & scp @SshOpts "$setupSh" "${PiUser}@${PiHost}:$remoteScripts/pi-nodered-multiplex-v05.sh"
  & ssh @SshOpts "${PiUser}@${PiHost}" "chmod +x '$remoteScripts/pi-nodered-multiplex-v05.sh'"

  Write-Host "=== Pi에서 멀티 인스턴스 구성 실행(nginx + node-red v05) ===" -ForegroundColor Yellow
  Write-Host "sudo 권한이 필요합니다. 비밀번호 입력이 필요하면 Pi 콘솔에서 실행하세요." -ForegroundColor Yellow
  & ssh @SshOpts "${PiUser}@${PiHost}" "bash '$remoteScripts/pi-nodered-multiplex-v05.sh'"

  Write-Host "완료: /admin, /ui(최신) + /admin/v0.5, /ui/0.5(스냅샷)" -ForegroundColor Green
} finally {
  Remove-Item -Recurse -Force $tmpDir -ErrorAction SilentlyContinue
}

