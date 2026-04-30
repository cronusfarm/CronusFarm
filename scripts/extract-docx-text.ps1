param(
  [Parameter(Mandatory = $true)]
  [string]$DocxPath,

  [int]$MaxChars = 200000
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $DocxPath)) {
  throw "파일이 없습니다: $DocxPath"
}

$tmp = Join-Path $env:TEMP ("docx_" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $tmp | Out-Null

try {
  # Expand-Archive는 확장자가 .zip일 때만 지원하는 환경이 있어, 임시로 .zip로 복사 후 해제합니다.
  $zipPath = Join-Path $tmp "doc.zip"
  Copy-Item -LiteralPath $DocxPath -Destination $zipPath -Force
  Expand-Archive -LiteralPath $zipPath -DestinationPath $tmp -Force
  $xmlPath = Join-Path $tmp "word/document.xml"
  if (-not (Test-Path -LiteralPath $xmlPath)) {
    throw "document.xml을 찾지 못했습니다: $xmlPath"
  }

  # 일부 문서에서 XML이 엄밀하지 않아 [xml] 파싱이 실패할 수 있어, 정규식으로 텍스트 노드를 추출합니다.
  $raw = Get-Content -LiteralPath $xmlPath -Raw -Encoding UTF8
  $matches = [regex]::Matches($raw, '<w:t\b[^>]*>(.*?)</w:t>', [System.Text.RegularExpressions.RegexOptions]::Singleline)
  $parts = foreach ($m in $matches) {
    $s = $m.Groups[1].Value
    if ([string]::IsNullOrWhiteSpace($s)) { continue }
    [System.Net.WebUtility]::HtmlDecode($s)
  }
  $text = ($parts -join " ")
  if ($text.Length -gt $MaxChars) {
    $text = $text.Substring(0, $MaxChars)
  }
  Write-Output $text
} finally {
  Remove-Item -LiteralPath $tmp -Recurse -Force -ErrorAction SilentlyContinue
}

