# Pi 홈 `~/cronusfarm` (소문자) 백업

## 백업 시점

- 2026-05-11 — Git 커밋으로 보관 (원본은 Pi에서 삭제)

## 원본 위치

- 호스트: LAN `192.168.1.22` (SSH), 사용자 `dooly`
- 경로: `/home/dooly/cronusfarm`

## 왜 백업했는지

- Linux는 경로 **대소문자를 구분**하므로 `~/CronusFarm` 과 `~/cronusfarm` 은 **서로 다른 디렉터리**이다.
- 이 저장소의 배포 스크립트·문서가 쓰는 정식 루트는 **`/home/dooly/CronusFarm`** (대문자 C·F) 뿐이다.
- Pi에서 확인한 바, 소문자 `cronusfarm` 은 **`nodered/`만 있는 작은 잔재·중복본**(전체 `arduino/`, `scripts/` 등 없음)으로 보였다.
- **삭제 전 혹시 모를 참고용**으로 트리 전체를 이 디렉터리(`pi-cronusfarm-tree/`)에 복사해 두었다.

## 삭제

- 백업 후 Pi에서 `~/cronusfarm` 디렉터리는 제거한다.
