"""Grafana 관제 대시보드 JSON 생성 (InfluxDB Flux)."""
import json
from pathlib import Path

DS_UID = "efjwqrorrfxtsf"
BUCKET = "cronusfarm"

root = Path(__file__).resolve().parents[1]
out = root / "grafana" / "dashboards" / "cronusfarm_control_room.json"

panels = []
y = 0


def row(title: str, y_off: int, h: int = 1):
    global y
    y = y_off
    return {
        "type": "row",
        "title": title,
        "gridPos": {"h": h, "w": 24, "x": 0, "y": y_off},
        "collapsed": False,
        "id": len(panels) + 100,
    }


def ts_panel(title: str, fields: list[str], y_pos: int, h: int = 8):
    targets = []
    for i, f in enumerate(fields):
        q = f'''from(bucket: "{BUCKET}")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r._measurement == "tele" and r._field == "{f}")
  |> aggregateWindow(every: v.windowPeriod, fn: last, createEmpty: false)'''
        targets.append(
            {
                "refId": chr(65 + i),
                "datasource": {"type": "influxdb", "uid": DS_UID},
                "query": q,
            }
        )
    return {
        "type": "timeseries",
        "title": title,
        "gridPos": {"h": h, "w": 24, "x": 0, "y": y_pos},
        "datasource": {"type": "influxdb", "uid": DS_UID},
        "targets": targets,
        "fieldConfig": {
            "defaults": {
                "custom": {"drawStyle": "line", "lineInterpolation": "smooth", "fillOpacity": 15},
                "color": {"mode": "palette-classic"},
            },
            "overrides": [],
        },
        "options": {"legend": {"displayMode": "list", "placement": "bottom"}},
        "id": len(panels) + 200,
    }


def gauge_panel(title: str, field: str, y_pos: int, x: int, w: int, unit: str, thresholds: list):
    q = f'''from(bucket: "{BUCKET}")
  |> range(start: -30m)
  |> filter(fn: (r) => r._measurement == "tele" and r._field == "{field}")
  |> last()'''
    return {
        "type": "gauge",
        "title": title,
        "gridPos": {"h": 6, "w": w, "x": x, "y": y_pos},
        "datasource": {"type": "influxdb", "uid": DS_UID},
        "targets": [
            {
                "refId": "A",
                "datasource": {"type": "influxdb", "uid": DS_UID},
                "query": q,
            }
        ],
        "fieldConfig": {
            "defaults": {
                "unit": unit,
                "thresholds": {"mode": "absolute", "steps": thresholds},
            },
            "overrides": [],
        },
        "options": {"reduceOptions": {"calcs": ["lastNotNull"]}},
        "id": len(panels) + 300,
    }


panels.append(row("관제 개요 · 가드 · 기상", 0))
panels.append(
    gauge_panel(
        "가드 정상(1=OK)",
        "guard_ok",
        1,
        0,
        6,
        "none",
        [
            {"color": "red", "value": None},
            {"color": "green", "value": 1},
        ],
    )
)
panels.append(
    gauge_panel(
        "Max-on 트립",
        "guard_mx",
        1,
        6,
        6,
        "none",
        [
            {"color": "green", "value": None},
            {"color": "red", "value": 1},
        ],
    )
)
panels.append(
    gauge_panel(
        "Min-off 대기",
        "guard_mf",
        1,
        12,
        6,
        "none",
        [
            {"color": "green", "value": None},
            {"color": "orange", "value": 1},
        ],
    )
)
panels.append(
    gauge_panel(
        "기상청 온도 (KMA)",
        "kma_temp",
        1,
        18,
        6,
        "celsius",
        [
            {"color": "blue", "value": None},
            {"color": "green", "value": 15},
            {"color": "red", "value": 32},
        ],
    )
)

panels.append(row("A/B 베드 출력 / 자동모드", 8))
panels.append(
    ts_panel(
        "LED / 펌프 상태 (0–1)",
        [
            "led_a1",
            "led_a2",
            "led_b1",
            "led_b2",
            "pump_a1",
            "pump_a2",
            "pump_b1",
            "pump_b2",
        ],
        9,
        9,
    )
)

panels.append(row("팬 · 예비 채널(C/D)", 18))
panels.append(
    ts_panel(
        "팬·예비 펌프",
        ["fan_a1", "fan_a2", "fan_b1", "fan_b2", "pump_c1", "pump_c2", "pump_d1", "pump_d2"],
        19,
        8,
    )
)

panels.append(row("펌프 주기 (초)", 27))
panels.append(
    ts_panel(
        "ON 구간(초)",
        ["pump_a1_on_s", "pump_a2_on_s", "pump_b1_on_s", "pump_b2_on_s"],
        28,
        7,
    )
)

dash = {
    "uid": "cronusfarm-control-room",
    "title": "CronusFarm 관제실 (제어·가드·Influx)",
    "tags": ["cronusfarm", "control-room", "influx"],
    "timezone": "Asia/Seoul",
    "refresh": "10s",
    "schemaVersion": 39,
    "version": 1,
    "time": {"from": "now-24h", "to": "now"},
    "templating": {
        "list": [
            {
                "name": "bucket",
                "type": "constant",
                "label": "Bucket",
                "query": BUCKET,
                "current": {"text": BUCKET, "value": BUCKET},
                "hide": 2,
            }
        ]
    },
    "panels": panels,
}

out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(dash, ensure_ascii=False, indent=2), encoding="utf-8")
print("OK", out)
