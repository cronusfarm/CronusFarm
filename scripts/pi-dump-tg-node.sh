#!/usr/bin/env bash
set -euo pipefail
python3 <<'PY'
import json
f = json.load(open("/home/dooly/.node-red/flows.json"))
for nid in ("cf_hreq_tg_getup", "cf_fn_tg_dispatch"):
    n = next(x for x in f if x.get("id") == nid)
    print("===", nid)
    print(json.dumps(n, indent=2, ensure_ascii=False)[:2000])
PY
sudo python3 /home/dooly/CronusFarm/scripts/pi-diag-telegram-ai.py
