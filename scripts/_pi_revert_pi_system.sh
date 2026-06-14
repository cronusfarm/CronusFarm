#!/bin/bash
set -eu
cd ~/CronusFarm
python3 scripts/patch_dashboard_pi_system_revert.py
python3 scripts/merge_nodered_deploy.py --use-split
bash scripts/pi-nodered-apply-merged.sh nodered/merged-deploy.json
python3 -c "import json;r=json.load(open('/home/dooly/.node-red/flows.json',encoding='utf-8-sig'));ids={'ui_tpl_pi_system','fn_pi_system_merge'};print('removed',not any(x.get('id') in ids for x in r));u=next(x for x in r if x.get('id')=='ui_txt_uptime');print('uptime_w',u.get('width'))"
