#!/bin/bash
# Pi(또는 Linux)에서 CronusFarm SQLite + Influx 시드 실행
# 사용: CRONUS_ROOT=/home/dooly/CronusFarm bash pi-seed-cronusfarm-environment.sh [--purge-influx]
# 추가 인자는 seed-cronusfarm-environment.py 에 그대로 전달됩니다.

set -euo pipefail

ROOT="${CRONUS_ROOT:-$HOME/CronusFarm}"
mkdir -p "$ROOT/data" "$ROOT/db"

exec python3 "$ROOT/scripts/seed-cronusfarm-environment.py" \
  --sqlite "$ROOT/data/cronusfarm.sqlite" \
  --schema "$ROOT/db/sqlite_schema.sql" \
  "$@"
