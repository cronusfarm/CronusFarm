#!/bin/bash
# pi-install-grafana-stack.sh
# InfluxDB 1.x + Grafana 설치 및 초기 설정 (Raspberry Pi / Debian 기반)

set -euo pipefail

INFLUX_DB="cronusfarm"
INFLUX_USER="cronusfarm"
INFLUX_PASS="cronusfarm1234"
GRAFANA_PORT=3000
INFLUX_PORT=8086

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
log()  { echo -e "${GREEN}[INFO]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }

log "InfluxDB 설치 중..."
if command -v influxd &>/dev/null; then
    warn "InfluxDB 이미 설치됨, 스킵"
else
    # 2026년 키 회전 대응(DA61C26A0585BD3B 등): 최신 키 사용
    sudo mkdir -p /etc/apt/keyrings/
    wget -qO- https://repos.influxdata.com/influxdata-archive.key \
        | gpg --dearmor | sudo tee /etc/apt/keyrings/influxdb.gpg > /dev/null
    echo "deb [signed-by=/etc/apt/keyrings/influxdb.gpg] https://repos.influxdata.com/debian stable main" \
        | sudo tee /etc/apt/sources.list.d/influxdata.list
    sudo apt-get update -qq
    sudo apt-get install -y influxdb
fi

sudo systemctl enable --now influxdb
sleep 2
log "InfluxDB 서비스 시작 완료"

log "InfluxDB DB 초기화: $INFLUX_DB"
influx -execute "CREATE DATABASE $INFLUX_DB" 2>/dev/null || warn "DB 이미 존재 (무시)"
influx -execute "CREATE USER $INFLUX_USER WITH PASSWORD '$INFLUX_PASS'" 2>/dev/null || warn "사용자 이미 존재 (무시)"
influx -execute "GRANT ALL ON $INFLUX_DB TO $INFLUX_USER" 2>/dev/null || true
# 주의: RP 이름이 숫자로 시작하면(예: 90days) InfluxQL에서 명시 참조/ALTER가 까다로울 수 있음.
# 10초 원본을 1년+ 보관할 수 있도록, 문자로 시작하는 RP를 기본으로 둡니다.
influx -execute "CREATE RETENTION POLICY raw400d ON \"$INFLUX_DB\" DURATION 400d REPLICATION 1 DEFAULT" \
    2>/dev/null || warn "RP 이미 존재 (무시)"
log "InfluxDB 초기화 완료 (DB: $INFLUX_DB, 보관: 400일)"

log "Grafana 설치 중..."
if command -v grafana-server &>/dev/null; then
    warn "Grafana 이미 설치됨, 스킵"
else
    # 최소 의존성만 설치(환경에 따라 software-properties-common이 없을 수 있음)
    sudo apt-get install -y apt-transport-https wget gpg
    sudo mkdir -p /etc/apt/keyrings/
    wget -q -O - https://apt.grafana.com/gpg.key \
        | gpg --dearmor | sudo tee /etc/apt/keyrings/grafana.gpg > /dev/null
    echo "deb [signed-by=/etc/apt/keyrings/grafana.gpg] https://apt.grafana.com stable main" \
        | sudo tee /etc/apt/sources.list.d/grafana.list
    sudo apt-get update -qq
    sudo apt-get install -y grafana
fi

sudo systemctl enable --now grafana-server
sleep 3
log "Grafana 서비스 시작 완료"

log "Grafana DataSource 등록 중..."
GRAFANA_URL="http://localhost:${GRAFANA_PORT}"
for i in $(seq 1 15); do
    if curl -sf "$GRAFANA_URL/api/health" &>/dev/null; then break; fi
    sleep 2
done

DS_PAYLOAD=$(cat <<EOF
{
  "name": "InfluxDB-CronusFarm",
  "type": "influxdb",
  "url": "http://localhost:${INFLUX_PORT}",
  "access": "proxy",
  "database": "${INFLUX_DB}",
  "user": "${INFLUX_USER}",
  "secureJsonData": { "password": "${INFLUX_PASS}" },
  "isDefault": true
}
EOF
)

HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
    -X POST "$GRAFANA_URL/api/datasources" \
    -H "Content-Type: application/json" \
    -u "admin:admin" \
    -d "$DS_PAYLOAD")

if [[ "$HTTP_CODE" == "200" || "$HTTP_CODE" == "409" ]]; then
    log "DataSource 등록 완료 (HTTP $HTTP_CODE)"
else
    warn "DataSource 등록 응답: $HTTP_CODE (수동 확인 필요)"
fi

if command -v ufw &>/dev/null; then
    sudo ufw allow ${GRAFANA_PORT}/tcp comment "Grafana"  2>/dev/null || true
    sudo ufw allow ${INFLUX_PORT}/tcp comment "InfluxDB" 2>/dev/null || true
fi

PI_IP=$(hostname -I | awk '{print $1}')
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  CronusFarm Grafana Stack 설치 완료!${NC}"
echo -e "${GREEN}========================================${NC}"
echo -e "  Grafana  : http://${PI_IP}:${GRAFANA_PORT}  (admin / admin)"
echo -e "  InfluxDB : http://${PI_IP}:${INFLUX_PORT}"
echo -e "             DB: ${INFLUX_DB} / User: ${INFLUX_USER}"
echo ""
echo -e "${YELLOW}다음 단계: Node-RED에 InfluxDB 노드를 추가하세요.${NC}"
echo -e "  cd ~/.node-red && npm install node-red-contrib-influxdb"