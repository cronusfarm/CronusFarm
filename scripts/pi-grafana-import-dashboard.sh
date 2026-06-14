#!/bin/bash
# pi-grafana-import-dashboard.sh
# Grafana 대시보드 JSON import + node-red-contrib-influxdb 설치
# 사용: bash pi-grafana-import-dashboard.sh <dashboard.json 경로>

set -euo pipefail

DASHBOARD_JSON="${1:-/home/dooly/CronusFarm/grafana/cronusfarm-dashboard.json}"
GRAFANA_URL="http://localhost:3000"
GRAFANA_USER="admin"
GRAFANA_PASS="${GRAFANA_PASSWORD:-admin}"
NR_DIR="${NODE_RED_DIR:-$HOME/.node-red}"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
log()  { echo -e "${GREEN}[INFO]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }

log "node-red-contrib-influxdb 설치 확인..."
cd "$NR_DIR"
if npm list node-red-contrib-influxdb &>/dev/null; then
    warn "node-red-contrib-influxdb 이미 설치됨"
else
    npm install node-red-contrib-influxdb
    log "설치 완료. Node-RED 재시작 중..."
    sudo systemctl restart nodered 2>/dev/null || true
    sleep 5
fi

log "Grafana 응답 대기 중..."
for i in $(seq 1 20); do
    if curl -sf "$GRAFANA_URL/api/health" &>/dev/null; then break; fi
    sleep 3
    [[ $i -eq 20 ]] && { echo "Grafana 응답 없음"; exit 1; }
done

[[ ! -f "$DASHBOARD_JSON" ]] && { echo "대시보드 JSON 없음: $DASHBOARD_JSON"; exit 1; }

log "대시보드 import: $DASHBOARD_JSON"

DS_UID=$(curl -sf "$GRAFANA_URL/api/datasources/name/InfluxDB-CronusFarm" \
    -u "$GRAFANA_USER:$GRAFANA_PASS" \
    | python3 -c "import sys,json; print(json.load(sys.stdin)['uid'])" 2>/dev/null || echo "")

DASHBOARD_CONTENT=$(cat "$DASHBOARD_JSON")
if [[ -n "$DS_UID" ]]; then
    DASHBOARD_CONTENT=$(echo "$DASHBOARD_CONTENT" | sed "s/\${DS_INFLUXDB}/$DS_UID/g")
    log "DataSource UID 교체: $DS_UID"
fi

IMPORT_PAYLOAD=$(python3 -c "
import json, sys
content = sys.stdin.read()
dash = json.loads(content)
dash.pop('__inputs', None)
dash.pop('__requires', None)
dash['id'] = None
print(json.dumps({'dashboard': dash, 'overwrite': True, 'folderId': 0}))
" <<< "$DASHBOARD_CONTENT")

HTTP_CODE=$(curl -s -o /tmp/grafana-import-result.json -w "%{http_code}" \
    -X POST "$GRAFANA_URL/api/dashboards/import" \
    -H "Content-Type: application/json" \
    -u "$GRAFANA_USER:$GRAFANA_PASS" \
    -d "$IMPORT_PAYLOAD")

if [[ "$HTTP_CODE" == "200" ]]; then
    DASH_URL=$(python3 -c "import json; d=json.load(open('/tmp/grafana-import-result.json')); print(d.get('importedUrl',''))" 2>/dev/null || echo "")
    PI_IP=$(hostname -I | awk '{print $1}')
    log "대시보드 import 성공!"
    echo -e "${GREEN}접속 URL: http://${PI_IP}:3000${DASH_URL}${NC}"
else
    warn "import 응답 코드: $HTTP_CODE"
    cat /tmp/grafana-import-result.json
fi
