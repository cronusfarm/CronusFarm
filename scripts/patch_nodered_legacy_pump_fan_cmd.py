"""구형 pump/fan cmd 경로 차단 — flows_cronusfarm_dashboard.json"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "nodered" / "flows_cronusfarm_dashboard.json"
flows = json.loads(path.read_text(encoding="utf-8"))
by_id = {n["id"]: n for n in flows}

SW = "c7b2b8e7cc1b92a1"  # ui_switch (MQTT 탭 구 펌프)
SL = "a8c1c0fe3cc39d21"  # ui_slider (MQTT 탭 구 팬 PWM)
LEGACY_FN = "c2d5b8a8b3cc12a1"

DISABLED_FUNC = """// [비활성] 구형 payload `pump=… fan=…` 는 CronusFarm.ino 가 해석하지 않습니다.
// A~D Bed 디지털 제어는 Dashboard v2 채널 스위치/카드( led_a1, pump_a1 … )를 사용하세요.
return null;"""

for nid in (SW, SL):
    n = by_id.get(nid)
    if n:
        n["wires"] = []

n = by_id.get(LEGACY_FN)
if n:
    n["func"] = DISABLED_FUNC
    n["wires"] = []

path.write_text(json.dumps(flows, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
print("patched", path)
