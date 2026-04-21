# push 전에 원격 브랜치 현재 커밋을 날짜·시간 태그(backup/…)로 남긴 뒤 push 합니다.
# 사용: 저장소 루트에서 .\scripts\git-push-with-backup.ps1
#       또는 -Branch main -Remote origin

param(
  [string] $Remote = "origin",
  [string] $Branch = ""
)

$ErrorActionPreference = "Stop"

if (-not $Branch) {
  $Branch = (git rev-parse --abbrev-ref HEAD).Trim()
}

git fetch $Remote
$remoteRef = "$Remote/$Branch"
if (git rev-parse --verify $remoteRef 2>$null) {
  $ts = Get-Date -Format "yyyy-MM-dd-HHmmss"
  $tagName = "backup/$ts"
  $hash = (git rev-parse $remoteRef).Trim()
  git tag -a $tagName $hash -m "push 전 원격 $remoteRef 스냅샷 ($ts)"
  git push $Remote $tagName
  Write-Host "백업 태그 생성·푸시: $tagName -> $hash" -ForegroundColor Green
} else {
  Write-Host "원격에 $remoteRef 가 없어 태그 생략(최초 push 가능)." -ForegroundColor Yellow
}

git push -u $Remote $Branch
Write-Host "완료: $Remote $Branch" -ForegroundColor Green
