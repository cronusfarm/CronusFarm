#!/usr/bin/env bash
curl -s "http://127.0.0.1/farm/cronusfarm-sqlite/api/channel/timeline?device_id=cronusfarm-01&channel=pump_c1&hours=24" | python3 -c "
import json,sys
j=json.load(sys.stdin)
pts=j.get('points') or []
on=sum(1 for p in pts if p.get('state') in (1,True))
print('points',len(pts),'on_samples',on,'window_end',j.get('window_end_ms'))
if pts:
    print('first',pts[0],'last',pts[-1])
"
