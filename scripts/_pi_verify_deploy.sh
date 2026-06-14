#!/bin/bash
set -eu
cd ~/CronusFarm
python3 scripts/patch_farm_env_fix.py
python3 scripts/patch_dashboard_pi_system_layout.py
python3 scripts/patch_dashboard_monitor_extended.py
python3 scripts/merge_nodered_deploy.py --use-split
bash scripts/pi-nodered-apply-merged.sh nodered/merged-deploy.json
bash scripts/pi-enable-mqtt-watch.sh || true
python3 scripts/pi-kma-refresh-now.py || true
sudo systemctl restart nodered
python3 -c "import json;r=json.load(open('/home/dooly/.node-red/flows.json',encoding='utf-8-sig'));m=next(x for x in r if x.get('id')=='cf_fn_farm_env_merge');print('merge_has_enrich', 'enrichKmaAir' in m.get('func',''))"
systemctl is-active cronusfarm-mqtt-watch.service || true
mosquitto_sub -h 127.0.0.1 -t cronusfarm/kma/snapshot -C 1 -W 3 2>/dev/null | head -c 200 || echo no_kma_mqtt
