# Pi SSH 호스트 선택
# - PiHost 가 비어 있으면: PiHostLan 이 비어 있으면 LAN 탐색 없이 PiHostWan(기본 Tailscale)만 사용.
# - PiHostLan 에 IP/호스트를 넣으면: 해당 주소로 SSH:22 응답 시 LAN 우선, 아니면 PiHostWan.
# - PiHost·PiHostLan 둘 다 비었을 때: WAN(22) 응답 실패 시 — 2026-05-05 까지만 ida LAN 폴백 192.168.1.22 시도
function Test-CronusSshPort {
  param(
    [string]$ComputerName,
    [int]$TimeoutMs = 3500
  )
  if ($null -eq $ComputerName -or $ComputerName.Trim().Length -eq 0) { return $false }
  try {
    $c = New-Object System.Net.Sockets.TcpClient
    $iar = $c.BeginConnect($ComputerName.Trim(), 22, $null, $null)
    if (-not $iar.AsyncWaitHandle.WaitOne($TimeoutMs, $false)) {
      try { $c.Close() } catch { }
      return $false
    }
    $c.EndConnect($iar)
    $c.Close()
    return $true
  } catch {
    return $false
  }
}

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
    $wanOk = Test-CronusSshPort -ComputerName $PiHostWan
    if ($wanOk) {
      Write-Host "[Pi] WAN SSH 사용: ${PiUser}@${PiHostWan}" -ForegroundColor DarkCyan
      return $PiHostWan
    }
    $fallbackDeadline = Get-Date "2026-05-05T23:59:59"
    $fallbackLan = "192.168.1.22"
    if ((Get-Date) -le $fallbackDeadline) {
      $lanOk = Test-CronusSshPort -ComputerName $fallbackLan
      if ($lanOk) {
        Write-Host "[Pi] WAN(22) 미응답 — LAN 폴백(만료 2026-05-05): ${PiUser}@${fallbackLan}" -ForegroundColor DarkYellow
        return $fallbackLan
      }
    }
    Write-Host "[Pi] WAN 기본 사용(연결은 스크립트에서 확인): ${PiUser}@${PiHostWan}" -ForegroundColor DarkCyan
    return $PiHostWan
  }
  $lanOk = Test-CronusSshPort -ComputerName $trimLan
  if ($lanOk) {
    Write-Host "[Pi] LAN SSH 사용: ${PiUser}@${trimLan}" -ForegroundColor DarkCyan
    return $trimLan
  }
  Write-Host "[Pi] LAN(22) 미응답, WAN 사용: ${PiUser}@${PiHostWan}" -ForegroundColor DarkYellow
  return $PiHostWan
}
