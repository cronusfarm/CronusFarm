# Pi SSH 호스트 선택
# - PiHost 가 비어 있으면: PiHostLan 이 비어 있으면 LAN 탐색 없이 PiHostWan(기본 Tailscale)만 사용.
# - PiHostLan 에 IP/호스트를 넣으면: 해당 주소로 SSH:22 응답 시 LAN 우선, 아니면 PiHostWan.
function Get-CronusPiHost {
  param(
    [string]$PiHost,
    [string]$PiHostLan = "",
    [string]$PiHostWan = "ida.mango-larch.ts.net",
    [string]$PiUser = "dooly"
  )
  if ($null -ne $PiHost -and $PiHost.Trim().Length -gt 0) {
    return $PiHost.Trim()
  }
  $trimLan = if ($null -eq $PiHostLan) { "" } else { $PiHostLan.Trim() }
  if ($trimLan.Length -eq 0) {
    Write-Host "[Pi] LAN 미사용(기본): ${PiUser}@${PiHostWan}" -ForegroundColor DarkCyan
    return $PiHostWan
  }
  $lanOk = $false
  try {
    $lanOk = [bool](Test-NetConnection -ComputerName $trimLan -Port 22 -InformationLevel Quiet -WarningAction SilentlyContinue)
  } catch { }
  if ($lanOk) {
    Write-Host "[Pi] LAN SSH 사용: ${PiUser}@${trimLan}" -ForegroundColor DarkCyan
    return $trimLan
  }
  Write-Host "[Pi] LAN(22) 미응답, WAN 사용: ${PiUser}@${PiHostWan}" -ForegroundColor DarkYellow
  return $PiHostWan
}
