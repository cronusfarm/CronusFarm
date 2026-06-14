#!/usr/bin/env bash
# 하위 호환 — SQLite·MQTT 쿨다운 env 일괄 적용
exec bash "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/pi-apply-nodered-cronusfarm-env.sh" "$@"
