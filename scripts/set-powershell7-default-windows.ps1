# PC 기본 셸을 PowerShell 7.6.x(pwsh)로 맞춤. Windows PowerShell 5.1은 OS 구성요소라 삭제 불가 — 바로가기·기본 프로필만 정리.
#Requires -Version 5.1
$ErrorActionPreference = "Stop"

try {
  if ($PSVersionTable.PSVersion.Major -lt 6) { chcp 65001 | Out-Null }
  $utf8 = New-Object System.Text.UTF8Encoding $false
  [Console]::OutputEncoding = $utf8
  $OutputEncoding = $utf8
} catch { }

function Resolve-PwshPath {
  try {
    $real = & pwsh -NoProfile -Command '(Get-Process -Id $PID).Path' 2>$null
    if ($real -and (Test-Path -LiteralPath $real)) { return $real.Trim() }
  } catch { }
  $cmd = Get-Command pwsh -ErrorAction SilentlyContinue
  if ($cmd -and $cmd.Source -and (Test-Path -LiteralPath $cmd.Source)) {
    $item = Get-Item -LiteralPath $cmd.Source -ErrorAction SilentlyContinue
    if ($item.Target -and (Test-Path -LiteralPath $item.Target)) {
      return (Resolve-Path -LiteralPath $item.Target).Path
    }
    return $cmd.Source
  }
  $candidates = @(
    "$env:ProgramFiles\PowerShell\7\pwsh.exe",
    (Get-ChildItem "$env:ProgramFiles\WindowsApps\Microsoft.PowerShell_*_x64__*\pwsh.exe" -ErrorAction SilentlyContinue |
      Sort-Object { $_.VersionInfo.ProductVersion } -Descending | Select-Object -First 1 -ExpandProperty FullName)
  )
  foreach ($c in $candidates) {
    if ($c -and (Test-Path -LiteralPath $c)) { return $c }
  }
  throw "pwsh.exe not found. Run: winget install Microsoft.PowerShell"
}

$pwshPath = Resolve-PwshPath
$ver = (Get-Item -LiteralPath $pwshPath).VersionInfo.ProductVersion
Write-Host "PowerShell 7: $pwshPath ($ver)" -ForegroundColor Cyan

# --- Windows Terminal: default = PowerShell 7, hide 5.1 ---
$wtPaths = @(
  "$env:LOCALAPPDATA\Packages\Microsoft.WindowsTerminal_8wekyb3d8bbwe\LocalState\settings.json",
  "$env:LOCALAPPDATA\Microsoft\Windows Terminal\settings.json"
)
$ps7Guid = "{574e775e-4f2a-5b96-ac1e-a2962a402336}"
$ps51Guid = "{61c54bbd-c2c6-5271-96e7-009a87ff44bf}"

foreach ($wtFile in $wtPaths) {
  if (-not (Test-Path -LiteralPath $wtFile)) { continue }
  $bak = "$wtFile.bak.ps7-$(Get-Date -Format 'yyyyMMddHHmmss')"
  Copy-Item -LiteralPath $wtFile -Destination $bak -Force
  $json = Get-Content -LiteralPath $wtFile -Raw -Encoding UTF8 | ConvertFrom-Json
  $json.defaultProfile = $ps7Guid
  foreach ($p in $json.profiles.list) {
    if ($p.guid -eq $ps51Guid) {
      $p.hidden = $true
    }
    if ($p.name -match 'PowerShell Preview') {
      $p.hidden = $true
    }
    if ($p.guid -eq $ps7Guid) {
      $p.name = "PowerShell 7"
      $p.hidden = $false
    }
  }
  $json | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $wtFile -Encoding UTF8
  Write-Host "OK Windows Terminal: $wtFile" -ForegroundColor Green
}

# --- Win11: 기본 터미널 앱 = Windows Terminal (가능 시) ---
try {
  $startup = "HKCU:\Console\%%Startup"
  if (-not (Test-Path $startup)) { New-Item -Path $startup -Force | Out-Null }
  Set-ItemProperty -Path $startup -Name Delegation -Value "{2ea604f0-2597-4b2d-8ad2-3b5d6c533770}" -Type String -ErrorAction Stop
  Write-Host "OK Default terminal app: Windows Terminal (registry)" -ForegroundColor Green
} catch {
  Write-Host "WARN: Default terminal registry skipped: $_" -ForegroundColor Yellow
}

# --- 시작 메뉴: PowerShell 7 바로가기, 5.1 사용자 바로가기 제거 ---
$startUser = [Environment]::GetFolderPath("Programs")
$lnk7 = Join-Path $startUser "PowerShell 7.lnk"
$Wsh = New-Object -ComObject WScript.Shell
$s = $Wsh.CreateShortcut($lnk7)
$s.TargetPath = $pwshPath
$s.Arguments = "-NoLogo"
$s.WorkingDirectory = $env:USERPROFILE
$s.Description = "PowerShell 7"
$s.Save()
Write-Host "OK Start menu: $lnk7" -ForegroundColor Green

$removePatterns = @(
  "$startUser\Windows PowerShell",
  "$env:ProgramData\Microsoft\Windows\Start Menu\Programs\Windows PowerShell"
)
foreach ($pat in $removePatterns) {
  if (Test-Path -LiteralPath $pat) {
    Remove-Item -LiteralPath $pat -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "Removed Start shortcut folder: $pat" -ForegroundColor Yellow
  }
}

# --- 작업 표시줄: PowerShell 7 고정 (실패해도 계속) ---
try {
  $pinDir = Join-Path $env:APPDATA "Microsoft\Internet Explorer\Quick Launch\User Pinned\TaskBar"
  if (Test-Path $pinDir) {
    Get-ChildItem $pinDir -Filter "*PowerShell*" -ErrorAction SilentlyContinue | ForEach-Object {
      if ($_.Name -match 'Windows PowerShell' -or $_.Target -match 'WindowsPowerShell\\v1\.0') {
        Remove-Item $_.FullName -Force -ErrorAction SilentlyContinue
        Write-Host "Unpinned old taskbar: $($_.Name)" -ForegroundColor Yellow
      }
    }
  }
  $verb = (New-Object -ComObject Shell.Application).Namespace($startUser).ParseName("PowerShell 7.lnk").Verbs() |
    Where-Object { $_.Name -match 'pin|고정' } | Select-Object -First 1
  if ($verb) {
    $verb.DoIt()
    Write-Host "OK Taskbar: pinned PowerShell 7 (if Explorer allowed)" -ForegroundColor Green
  }
} catch {
  Write-Host "WARN: Taskbar pin manual: Start menu 'PowerShell 7' -> Pin to taskbar" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Note: Windows PowerShell 5.1 (powershell.exe) cannot be uninstalled — it is part of Windows." -ForegroundColor DarkGray
Write-Host "      It is hidden from Terminal and Start menu shortcuts removed where possible." -ForegroundColor DarkGray
Write-Host "Open NEW terminal and run: pwsh -Command `"`$PSVersionTable.PSVersion`"" -ForegroundColor DarkGray
