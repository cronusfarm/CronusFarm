"""PHW3988/Cronus 플로우 JSON 검증."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# PHW 노드가 있어야 하는 파일만 엄격 검증
PHW_FILES = [
    ROOT / "nodered" / "merged-deploy.json",
    ROOT / "nodered" / "flows_cronusfarm_dashboard.json",
    ROOT / "nodered" / "flows_pi_editor_latest.json",
]
MQTT_ONLY = ROOT / "nodered" / "flows_cronusfarm_mqtt.json"

PICK_TO_GAUGE = {
    "d5483828b614bd88": "480e017a1bfbfe7b",
    "874f552956291ad6": "2141fe178c3e2c88",
    "4fa53d4c97a59637": "a0a33715ba8ca5eb",
    "b22f8d4f771bb409": "f61aebaa74026feb",
    "f951ab2f0f813b4d": "9d76b919dae993f9",
    "9651686f7f601ac8": "1800ba1474d7135c",
}


def verify(path: Path) -> list[str]:
    issues: list[str] = []
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    blob = json.dumps(data, ensure_ascii=False).lower()
    by = {n["id"]: n for n in data if isinstance(n, dict) and n.get("id")}

    if "hivemq" in blob or "d7013a5209d5fe9b" in by:
        issues.append("HIVEMQ 잔존")
    if "sf_3team" in blob:
        issues.append("sf_3team 잔존")
    if "192.168.60.132" in blob:
        issues.append("구 IP 192.168.60.132 잔존")

    tuya = by.get("8ed219bf73293e78", {})
    if tuya.get("deviceIp") != "14.32.231.191":
        issues.append(f"Tuya IP={tuya.get('deviceIp')!r}")

    mqtt = by.get("4fd2979510810d5f", {})
    if mqtt.get("broker") != "d6b7f6c1b2b3c4d5":
        issues.append(f"MQTT broker={mqtt.get('broker')!r}")
    if mqtt.get("topic") != "cronus/water":
        issues.append(f"MQTT topic={mqtt.get('topic')!r}")

    if "cf_phw_fn_sqlite01" not in by:
        issues.append("SQLite function 노드 없음")

    fn_map = by.get("201f991e49bff34f", {})
    wires = (fn_map.get("wires") or [[]])[0]
    for need in ("cf_phw_fn_sqlite01", "d93926e2264775ad", "d803759f55603ec6"):
        if need not in wires:
            issues.append(f"fn_map 미연결: {need}")

    for pick, gauge in PICK_TO_GAUGE.items():
        p = by.get(pick, {})
        gw = (p.get("wires") or [[]])[0]
        if gauge not in gw:
            issues.append(f"pick {pick} → gauge {gauge} 끊김")

    if by.get("8ed219bf73293e78", {}).get("z") not in (
        "tab_cronus_dash",
        "02ccfe788704ab49",
    ):
        issues.append(f"Tuya z={by.get('8ed219bf73293e78', {}).get('z')}")

    gauges = sum(
        1
        for n in data
        if n.get("type") == "ui_gauge" and n.get("group") == "ui_grp_gh_data"
    )
    if gauges != 6:
        issues.append(f"게이지 수={gauges} (기대 6)")

    drop = {"d7013a5209d5fe9b", "2c66449a4d7d4656", "554c1b474239d145"}
    if drop & set(by):
        issues.append(f"제거 대상 노드 잔존: {drop & set(by)}")

    return issues


def verify_mqtt_no_hive(path: Path) -> list[str]:
    issues: list[str] = []
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    blob = json.dumps(data, ensure_ascii=False).lower()
    by = {n["id"]: n for n in data if isinstance(n, dict) and n.get("id")}
    if "hivemq" in blob or "d7013a5209d5fe9b" in by:
        issues.append("HIVEMQ 잔존")
    if "sf_3team" in blob:
        issues.append("sf_3team 잔존")
    return issues


def main() -> int:
    failed = False
    for p in PHW_FILES:
        if not p.is_file():
            print(f"SKIP 없음: {p.name}")
            continue
        issues = verify(p)
        if issues:
            failed = True
            print(f"FAIL {p.name}:")
            for i in issues:
                print(f"  - {i}")
        else:
            print(f"OK   {p.name}")
    if MQTT_ONLY.is_file():
        issues = verify_mqtt_no_hive(MQTT_ONLY)
        if issues:
            failed = True
            print(f"FAIL {MQTT_ONLY.name}:")
            for i in issues:
                print(f"  - {i}")
        else:
            print(f"OK   {MQTT_ONLY.name} (mqtt)")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
