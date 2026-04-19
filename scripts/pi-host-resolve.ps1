# Pi 접속 호스트: LAN(기본 192.168.1.22) SSH 포트 응답 시 LAN, 아니면 WAN(기본 MagicDNS)
function Get-CronusPiHost {
  param(
    [string]$PiHost,
    [string]$PiHostLan = "192.168.1.22",
    [string]$PiHostWan = "ida.mango-larch.ts.net",
    [string]$PiUser = "dooly"
  )
  if ($null -ne $PiHost -and $PiHost.Trim().Length -gt 0) {
    return $PiHost.Trim()
  }
  $lanOk = $false
  try {
    $lanOk = [bool](Test-NetConnection -ComputerName $PiHostLan -Port 22 -InformationLevel Quiet -WarningAction SilentlyContinue)
  } catch { }
  if ($lanOk) {
    Write-Host "[Pi] LAN SSH 사용: ${PiUser}@${PiHostLan}" -ForegroundColor DarkCyan
    return $PiHostLan
  }
  Write-Host "[Pi] LAN(22) 미응답, WAN 사용: ${PiUser}@${PiHostWan}" -ForegroundColor DarkYellow
  return $PiHostWan
}
