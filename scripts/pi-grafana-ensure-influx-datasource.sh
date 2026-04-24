#!/bin/bash
# Grafana에 InfluxDB 1.x 데이터소스 InfluxDB-CronusFarm 이 없으면 등록한다.
# 사용: bash pi-grafana-ensure-influx-datasource.sh
# (admin 비밀번호가 기본 admin 이 아니면 환경변수 GRAFANA_PASSWORD 설정)

set -euo pipefail

GRAFANA_URL="${GRAFANA_URL:-http://127.0.0.1:3000}"
GRAFANA_USER="${GRAFANA_USER:-admin}"
GRAFANA_PASS="${GRAFANA_PASSWORD:-admin}"
INFLUX_PORT="${INFLUX_PORT:-8086}"
INFLUX_DB="${INFLUX_DB:-cronusfarm}"
INFLUX_USER="${INFLUX_USER:-cronusfarm}"
INFLUX_PASS="${INFLUX_PASS:-cronusfarm1234}"

if curl -sf "$GRAFANA_URL/api/datasources/name/InfluxDB-CronusFarm" \
    -u "$GRAFANA_USER:$GRAFANA_PASS" >/dev/null; then
  echo "[OK] 데이터소스 InfluxDB-CronusFarm 이미 존재"
  exit 0
fi

TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT

cat >"$TMP" <<EOF
{
  "name": "InfluxDB-CronusFarm",
  "type": "influxdb",
  "url": "http://127.0.0.1:${INFLUX_PORT}",
  "access": "proxy",
  "database": "${INFLUX_DB}",
  "user": "${INFLUX_USER}",
  "secureJsonData": { "password": "${INFLUX_PASS}" },
  "isDefault": true,
  "jsonData": { "httpMode": "GET" }
}
EOF

CODE=$(curl -sS -o /tmp/grafana-ds-out.txt -w "%{http_code}" \
  -X POST "$GRAFANA_URL/api/datasources" \
  -H "Content-Type: application/json" \
  -u "$GRAFANA_USER:$GRAFANA_PASS" \
  -d @"$TMP")

if [[ "$CODE" == "200" ]]; then
  echo "[OK] InfluxDB-CronusFarm 데이터소스 등록 완료 (HTTP $CODE)"
  exit 0
fi

echo "[ERR] 데이터소스 등록 실패 HTTP $CODE" >&2
cat /tmp/grafana-ds-out.txt >&2 || true
exit 1
