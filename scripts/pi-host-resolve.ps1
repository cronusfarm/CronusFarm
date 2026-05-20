# Pi SSH 호스트 선택 (운영 Pi = ida)
# - 서비스 URL·MQTT 등: scripts/cronusfarm-network.ps1 (LAN → Tailscale → DuckDNS)
# - SSH 22: Tailscale / LAN 192.168.60.222
# - PiHost 가 ida / ida.local 이면 DNS 오해석 방지 — Tailscale 우선 → LAN(222) 폴백
# - PiHost 에 IP·FQDN 직접 주면 그대로 사용
# - PiHostLan 지정 시: 해당 IP에 22 응답하면 사용, 아니면 WAN
function Get-CronusTailscalePiIp {
  $ts = Get-Command tailscale -ErrorAction SilentlyContinue
  if (-not $ts) { return $null }
  try {
    $line = & tailscale status 2>$null | Where-Object { $_ -match '\sida\s' } | Select-Object -First 1
    if ($line -match '(\d+\.\d+\.\d+\.\d+)') { return $Matches[1] }
  } catch { }
  return $null
}

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
  $netPs1 = Join-Path $PSScriptRoot "cronusfarm-network.ps1"
  if ((Test-Path $netPs1) -and [string]::IsNullOrWhiteSpace($PiHost)) {
    try {
      . $netPs1
      $ep = Get-CronusFarmPiEndpoint
      if ($ep.Via -eq "LAN") {
        Write-Host "[Pi] SSH/LAN(서비스): ${PiUser}@$($ep.Host)" -ForegroundColor DarkCyan
        return $ep.Host
      }
    } catch { }
  }
  if ($null -ne $PiHost -and $PiHost.Trim().Length -gt 0) {
    $raw = $PiHost.Trim()
    if ($raw -match '^(?i)ida(\.local)?$') {
      if (Test-CronusSshPort -ComputerName $PiHostWan) {
        Write-Host "[Pi] ida→Tailscale 우선: ${PiUser}@${PiHostWan}" -ForegroundColor DarkCyan
        return $PiHostWan
      }
      $lanIda = "192.168.60.222"
      if (Test-CronusSshPort -ComputerName $lanIda) {
        Write-Host "[Pi] ida→LAN 폴백: ${PiUser}@${lanIda}" -ForegroundColor DarkCyan
        return $lanIda
      }
      Write-Host "[Pi] ida: SSH(22) 없음, Tailscale 호스트 반환: ${PiUser}@${PiHostWan}" -ForegroundColor DarkYellow
      return $PiHostWan
    }
    return $raw
  }
  $trimLan = if ($null -eq $PiHostLan) { "" } else { $PiHostLan.Trim() }
  if ($trimLan.Length -eq 0) {
    $wanOk = Test-CronusSshPort -ComputerName $PiHostWan
    if ($wanOk) {
      Write-Host "[Pi] Tailscale SSH 우선: ${PiUser}@${PiHostWan}" -ForegroundColor DarkCyan
      return $PiHostWan
    }
    $preferredLan = "192.168.60.222"
    if (Test-CronusSshPort -ComputerName $preferredLan) {
      Write-Host "[Pi] LAN SSH 폴백: ${PiUser}@${preferredLan}" -ForegroundColor DarkCyan
      return $preferredLan
    }
    $tsIp = Get-CronusTailscalePiIp
    if ($tsIp -and (Test-CronusSshPort -ComputerName $tsIp)) {
      Write-Host "[Pi] Tailscale IP 폴백: ${PiUser}@${tsIp}" -ForegroundColor DarkCyan
      return $tsIp
    }
    Write-Host "[Pi] LAN/WAN(22) 응답 없음, 기본 Tailscale: ${PiUser}@${PiHostWan}" -ForegroundColor DarkYellow
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
