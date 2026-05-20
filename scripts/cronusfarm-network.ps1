# CronusFarm Pi 접속 호스트·포트 (라우터 포워딩·LAN/Tailscale/DuckDNS)
# 사용: . "$PSScriptRoot\cronusfarm-network.ps1"

$ErrorActionPreference = "Stop"

$script:CronusNetworkJsonPath = Join-Path $PSScriptRoot "cronusfarm-network.json"
if (-not (Test-Path $script:CronusNetworkJsonPath)) {
  throw "cronusfarm-network.json 없음: $script:CronusNetworkJsonPath"
}
$script:CronusNet = Get-Content $script:CronusNetworkJsonPath -Raw -Encoding UTF8 | ConvertFrom-Json

function Get-CronusNetPorts {
  return $script:CronusNet.ports
}

function Get-CronusNetHosts {
  return $script:CronusNet.hosts
}

function Test-CronusTcpPort {
  param(
    [string]$ComputerName,
    [int]$Port,
    [int]$TimeoutMs = 3500
  )
  if ([string]::IsNullOrWhiteSpace($ComputerName) -or $Port -le 0) { return $false }
  try {
    $c = New-Object System.Net.Sockets.TcpClient
    $iar = $c.BeginConnect($ComputerName.Trim(), $Port, $null, $null)
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

function Test-CronusPiReachable {
  param([string]$HostName)
  $ports = Get-CronusNetPorts
  $probe = @($ports.mqtt, $ports.nginx) | Select-Object -Unique
  foreach ($p in $probe) {
    if (Test-CronusTcpPort -ComputerName $HostName -Port $p) {
      return $true
    }
  }
  return $false
}

<#
  호스트 선택:
  - LocalDev: Tailscale 고정 (로컬 Node-RED 개발)
  - 그 외: LAN → Tailscale → DuckDNS (MQTT/nginx 포트로 TCP 프로브)
#>
function Get-CronusFarmPiEndpoint {
  param(
    [switch]$LocalDev,
    [string]$LanHost = "",
    [string]$TailscaleHost = "",
    [string]$DuckDnsHost = ""
  )

  $h = Get-CronusNetHosts
  $p = Get-CronusNetPorts

  if ([string]::IsNullOrWhiteSpace($LanHost)) { $LanHost = [string]$h.lan }
  if ([string]::IsNullOrWhiteSpace($TailscaleHost)) { $TailscaleHost = [string]$h.tailscale }
  if ([string]::IsNullOrWhiteSpace($DuckDnsHost)) { $DuckDnsHost = [string]$h.duckdns }

  if ($LocalDev) {
    Write-Host "[CronusNet] 로컬 개발 → Tailscale: $TailscaleHost" -ForegroundColor DarkCyan
    return [pscustomobject]@{
      Host       = $TailscaleHost
      Via        = "Tailscale(LocalDev)"
      MqttPort   = $p.mqtt
      NginxPort  = $p.nginx
      NrPort     = $p.nrLatest
      SqlitePort = $p.sqliteBridge
      CctvPort   = $p.cctvStream
      HailoPort  = $p.hailoMjpeg
    }
  }

  if ((Test-CronusPiReachable -HostName $LanHost)) {
    Write-Host "[CronusNet] LAN: $LanHost (MQTT:$($p.mqtt) / nginx:$($p.nginx))" -ForegroundColor DarkCyan
    return [pscustomobject]@{
      Host       = $LanHost
      Via        = "LAN"
      MqttPort   = $p.mqtt
      NginxPort  = $p.nginx
      NrPort     = $p.nrLatest
      SqlitePort = $p.sqliteBridge
      CctvPort   = $p.cctvStream
      HailoPort  = $p.hailoMjpeg
    }
  }

  if ((Test-CronusPiReachable -HostName $TailscaleHost)) {
    Write-Host "[CronusNet] Tailscale: $TailscaleHost" -ForegroundColor DarkCyan
    return [pscustomobject]@{
      Host       = $TailscaleHost
      Via        = "Tailscale"
      MqttPort   = $p.mqtt
      NginxPort  = $p.nginx
      NrPort     = $p.nrLatest
      SqlitePort = $p.sqliteBridge
      CctvPort   = $p.cctvStream
      HailoPort  = $p.hailoMjpeg
    }
  }

  if ((Test-CronusPiReachable -HostName $DuckDnsHost)) {
    Write-Host "[CronusNet] DuckDNS: $DuckDnsHost" -ForegroundColor DarkCyan
    return [pscustomobject]@{
      Host       = $DuckDnsHost
      Via        = "DuckDNS"
      MqttPort   = $p.mqtt
      NginxPort  = $p.nginx
      NrPort     = $p.nrLatest
      SqlitePort = $p.sqliteBridge
      CctvPort   = $p.cctvStream
      HailoPort  = $p.hailoMjpeg
    }
  }

  Write-Host "[CronusNet] 프로브 실패 → Tailscale 기본: $TailscaleHost" -ForegroundColor DarkYellow
  return [pscustomobject]@{
    Host       = $TailscaleHost
    Via        = "Tailscale(Fallback)"
    MqttPort   = $p.mqtt
    NginxPort  = $p.nginx
    NrPort     = $p.nrLatest
    SqlitePort = $p.sqliteBridge
    CctvPort   = $p.cctvStream
    HailoPort  = $p.hailoMjpeg
  }
}

function Set-CronusFarmPiEnv {
  param(
    [Parameter(Mandatory = $true)]
    $Endpoint
  )
  $env:CRONUSFARM_PI_HOST = $Endpoint.Host
  $env:CRONUSFARM_MQTT_PORT = [string]$Endpoint.MqttPort
  $env:CRONUSFARM_NGINX_PORT = [string]$Endpoint.NginxPort
  $env:CRONUSFARM_NR_PORT = [string]$Endpoint.NrPort
  $env:CRONUSFARM_SQLITE_BRIDGE_URL = "http://$($Endpoint.Host):$($Endpoint.SqlitePort)"
  $env:CRONUSFARM_SQLITE_BRIDGE_PORT = [string]$Endpoint.SqlitePort
  $env:CRONUSFARM_CCTV_PORT = [string]$Endpoint.CctvPort
  $env:CRONUSFARM_HAILO_PORT = [string]$Endpoint.HailoPort
}
