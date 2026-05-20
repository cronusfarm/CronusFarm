# CronusFarm network path + latency check (PC -> Pi)
# Console text is English so Windows PowerShell 5.1 does not mangle Korean.
param(
  [string]$DeviceId = "cronusfarm-01",
  [string]$Channel = "led_a1",
  [switch]$SkipLocalNr,
  [string]$ReportPath = ""
)

$ErrorActionPreference = "Continue"
. (Join-Path $PSScriptRoot "cronusfarm-network.ps1")

$lines = [System.Collections.Generic.List[string]]::new()
function Log([string]$s, [string]$color = "") {
  $lines.Add($s)
  if ($color) { Write-Host $s -ForegroundColor $color }
  else { Write-Host $s }
}

$q = "device_id=$DeviceId&channel=$Channel&hours=24"
$qb = "device_id=$DeviceId&channels=$Channel,pump_a1&hours=24"
$hosts = Get-CronusNetHosts
$lan = [string]$hosts.lan
$ts = [string]$hosts.tailscale
$duck = [string]$hosts.duckdns

$lanOk = (Test-CronusTcpPort -ComputerName $lan -Port 1880) -or (Test-CronusTcpPort -ComputerName $lan -Port 22)

Log "=== CronusFarm network diagnose ===" "Cyan"
if (-not $lanOk) {
  Log "[note] PC is NOT on Pi LAN ($lan). LAN failures are expected. Compare Tailscale vs DuckDNS only." "DarkGray"
}
Log ""

Log "[1] TCP ports: 22 (SSH) / 1880 (nginx UI) / 18766 (sqlite bridge)" "Yellow"
foreach ($pair in @(
  @("LAN", $lan),
  @("Tailscale", $ts),
  @("DuckDNS", $duck)
)) {
  $name, $h = $pair
  $p1880 = Test-CronusTcpPort -ComputerName $h -Port 1880
  $p18766 = Test-CronusTcpPort -ComputerName $h -Port 18766
  $p22 = Test-CronusTcpPort -ComputerName $h -Port 22
  $note = if ($name -eq "LAN" -and -not $lanOk) { "  (remote PC - ignore)" } else { "" }
  Log ("  {0,-10} {1,-28} 22={2} 1880={3} 18766={4}{5}" -f $name, $h, $p22, $p1880, $p18766, $note)
}

Log ""
Log "[2] Ping (ICMP, reference only)" "Yellow"
foreach ($pair in @(@("LAN", $lan), @("TS", $ts), @("DuckDNS", $duck))) {
  $name, $h = $pair
  try {
    $p = Test-Connection -ComputerName $h -Count 2 -ErrorAction Stop
    $avg = ($p | Measure-Object -Property ResponseTime -Average).Average
    Log ("  {0,-8} {1} avg={2}ms" -f $name, $h, [int]$avg)
  } catch {
    $msg = if ($name -eq "LAN" -and -not $lanOk) { "SKIP (different network)" } else { "FAIL / ICMP blocked" }
    Log ("  {0,-8} {1} {2}" -f $name, $h, $msg)
  }
}

Log ""
Log "[3] Timeline API latency (HTTP, same as dashboard)" "Yellow"
$tests = @(
  @{ L = "TS nginx 1ch"; U = "http://${ts}:1880/farm/cronusfarm-sqlite/api/channel/timeline?$q" },
  @{ L = "TS nginx batch"; U = "http://${ts}:1880/farm/cronusfarm-sqlite/api/channel/timeline/batch?$qb" },
  @{ L = "TS bridge 1ch"; U = "http://${ts}:18766/api/channel/timeline?$q" },
  @{ L = "Duck nginx 1ch"; U = "http://${duck}:1880/farm/cronusfarm-sqlite/api/channel/timeline?$q" },
  @{ L = "Duck nginx batch"; U = "http://${duck}:1880/farm/cronusfarm-sqlite/api/channel/timeline/batch?$qb" }
)
if (-not $SkipLocalNr) {
  $tests += @{ L = "localhost NR 1ch"; U = "http://127.0.0.1:1881/farm/cronusfarm-sqlite/api/channel/timeline?$q" }
}
if ($lanOk) {
  $tests += @{ L = "LAN nginx 1ch"; U = "http://${lan}:1880/farm/cronusfarm-sqlite/api/channel/timeline?$q" }
}

$bestMs = [int]::MaxValue
$bestLabel = ""
foreach ($t in $tests) {
  try {
    $sw = [Diagnostics.Stopwatch]::StartNew()
    $r = Invoke-WebRequest -Uri $t.U -UseBasicParsing -TimeoutSec 60
    $sw.Stop()
    $ms = [int]$sw.ElapsedMilliseconds
    Log ("  {0,-18} {1,6}ms  HTTP {2}  len={3}" -f $t.L, $ms, $r.StatusCode, $r.Content.Length)
    if ($ms -lt $bestMs) { $bestMs = $ms; $bestLabel = $t.L }
  } catch {
    Log ("  {0,-18} FAIL  {1}" -f $t.L, $_.Exception.Message)
  }
}

Log ""
Log "[4] Summary" "Yellow"
Log "  - On Pi itself API is <50ms. Multi-second from PC = WAN/VPN round-trip (not a UI bug)."
Log "  - Dashboard URLs:"
Log "      Tailscale: http://${ts}:1880/ui/"
Log "      DuckDNS:   http://${duck}:1880/ui/"
Log "  - Charts use timeline/batch (one HTTP call per Bed). Old 16-channel = much slower."
Log "  - Port 18766 optional; nginx :1880/farm/... is enough for /ui."
Log "  - Local Node-RED :1881 still proxies to Pi bridge (slow when remote)."
if ($bestLabel) {
  Log ("  - Fastest this run: {0} ({1}ms)" -f $bestLabel, $bestMs) "Green"
  if ($bestLabel -match "^Duck") {
    Log "  - Tip: use DuckDNS URL above if you are off-LAN (often faster than Tailscale)." "Green"
  }
}
$ep = Get-CronusFarmPiEndpoint
Log ("  - cronusfarm-network default host: {0} ({1})" -f $ep.Host, $ep.Via) "DarkCyan"

if ($ReportPath) {
  $utf8Bom = New-Object System.Text.UTF8Encoding $true
  [System.IO.File]::WriteAllLines($ReportPath, $lines, $utf8Bom)
  Log ""
  Log "Report saved (UTF-8): $ReportPath" "DarkCyan"
}
