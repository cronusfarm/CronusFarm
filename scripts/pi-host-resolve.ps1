# Pi SSH 호스트 선택 (운영 Pi = ida)
# - LAN: 192.168.0.222 (PiHost 비었을 때 22번 응답하면 우선)
# - Tailscale: ida.mango-larch.ts.net (LAN 없을 때)
# - PiHost 가 ida / ida.local 이면 DNS 오해석 방지 — LAN(222)→Tailscale 순으로 고름
# - PiHost 에 IP·FQDN 직접 주면 그대로 사용
# - PiHostLan 지정 시: 해당 IP에 22 응답하면 사용, 아니면 WAN
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
    $raw = $PiHost.Trim()
    if ($raw -match '^(?i)ida(\.local)?$') {
      $lanIda = "192.168.0.222"
      if (Test-CronusSshPort -ComputerName $lanIda) {
        Write-Host "[Pi] ida→LAN: ${PiUser}@${lanIda}" -ForegroundColor DarkCyan
        return $lanIda
      }
      if (Test-CronusSshPort -ComputerName $PiHostWan) {
        Write-Host "[Pi] ida→Tailscale: ${PiUser}@${PiHostWan}" -ForegroundColor DarkCyan
        return $PiHostWan
      }
      Write-Host "[Pi] ida: SSH(22) 없음, Tailscale 호스트 반환: ${PiUser}@${PiHostWan}" -ForegroundColor DarkYellow
      return $PiHostWan
    }
    return $raw
  }
  $trimLan = if ($null -eq $PiHostLan) { "" } else { $PiHostLan.Trim() }
  if ($trimLan.Length -eq 0) {
    $preferredLan = "192.168.0.222"
    if (Test-CronusSshPort -ComputerName $preferredLan) {
      Write-Host "[Pi] LAN SSH: ${PiUser}@${preferredLan}" -ForegroundColor DarkCyan
      return $preferredLan
    }
    $wanOk = Test-CronusSshPort -ComputerName $PiHostWan
    if ($wanOk) {
      Write-Host "[Pi] WAN SSH: ${PiUser}@${PiHostWan}" -ForegroundColor DarkCyan
      return $PiHostWan
    }
    Write-Host "[Pi] LAN/WAN(22) no response, default WAN: ${PiUser}@${PiHostWan}" -ForegroundColor DarkYellow
    return $PiHostWan
  }
  $lanOk = Test-CronusSshPort -ComputerName $trimLan
  if ($lanOk) {
    Write-Host "[Pi] LAN SSH: ${PiUser}@${trimLan}" -ForegroundColor DarkCyan
    return $trimLan
  }
  Write-Host "[Pi] LAN(22) no response, use WAN: ${PiUser}@${PiHostWan}" -ForegroundColor DarkYellow
  return $PiHostWan
}
