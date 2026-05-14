"""Grafana 운영 UI 대시보드 JSON 생성 — Node-RED는 적재만, 화면은 Grafana 네이티브 그래픽."""
import json
from pathlib import Path

DS_UID = "efjwqrorrfxtsf"
BUCKET = "cronusfarm"

root = Path(__file__).resolve().parents[1]
out = root / "grafana" / "dashboards" / "cronusfarm_operator_ui.json"

panels: list = []
pid = 0


def next_id() -> int:
    global pid
    pid += 1
    return pid


def row(title: str, y: int) -> dict:
    return {
        "type": "row",
        "title": title,
        "gridPos": {"h": 1, "w": 24, "x": 0, "y": y},
        "collapsed": False,
        "id": next_id(),
    }


def flux_last(field: str) -> str:
    return f"""from(bucket: "{BUCKET}")
  |> range(start: -30m)
  |> filter(fn: (r) => r._measurement == "tele" and r._field == "{field}")
  |> last()"""


def flux_range(field: str) -> str:
    return f"""from(bucket: "{BUCKET}")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r._measurement == "tele" and r._field == "{field}")
  |> aggregateWindow(every: v.windowPeriod, fn: last, createEmpty: false)"""


def stat_panel(title: str, field: str, y: int, x: int, w: int, unit: str, steps: list) -> dict:
    return {
        "type": "stat",
        "title": title,
        "gridPos": {"h": 5, "w": w, "x": x, "y": y},
        "datasource": {"type": "influxdb", "uid": DS_UID},
        "targets": [
            {
                "refId": "A",
                "datasource": {"type": "influxdb", "uid": DS_UID},
                "query": flux_last(field),
            }
        ],
        "fieldConfig": {
            "defaults": {
                "unit": unit,
                "decimals": 1,
                "thresholds": {"mode": "absolute", "steps": steps},
                "color": {"mode": "thresholds"},
            },
            "overrides": [],
        },
        "options": {
            "colorMode": "background",
            "graphMode": "area",
            "justifyMode": "center",
            "orientation": "auto",
            "textMode": "value_and_name",
            "wideLayout": True,
        },
        "id": next_id(),
    }


def gauge_panel(title: str, field: str, y: int, x: int, w: int, unit: str, steps: list) -> dict:
    return {
        "type": "gauge",
        "title": title,
        "gridPos": {"h": 6, "w": w, "x": x, "y": y},
        "datasource": {"type": "influxdb", "uid": DS_UID},
        "targets": [
            {
                "refId": "A",
                "datasource": {"type": "influxdb", "uid": DS_UID},
                "query": flux_last(field),
            }
        ],
        "fieldConfig": {
            "defaults": {
                "unit": unit,
                "thresholds": {"mode": "absolute", "steps": steps},
            },
            "overrides": [],
        },
        "options": {"reduceOptions": {"calcs": ["lastNotNull"]}},
        "id": next_id(),
    }


def bargauge_channels(title: str, fields: list[str], y: int, h: int) -> dict:
    targets = []
    for i, f in enumerate(fields):
        targets.append(
            {
                "refId": chr(65 + i),
                "datasource": {"type": "influxdb", "uid": DS_UID},
                "query": flux_last(f),
            }
        )
    return {
        "type": "bargauge",
        "title": title,
        "gridPos": {"h": h, "w": 24, "x": 0, "y": y},
        "datasource": {"type": "influxdb", "uid": DS_UID},
        "targets": targets,
        "fieldConfig": {
            "defaults": {
                "min": 0,
                "max": 1,
                "unit": "none",
                "thresholds": {
                    "mode": "absolute",
                    "steps": [
                        {"color": "semi-dark-red", "value": None},
                        {"color": "green", "value": 0.5},
                    ],
                },
            },
            "overrides": [],
        },
        "options": {
            "displayMode": "lcd",
            "orientation": "horizontal",
            "reduceOptions": {"calcs": ["lastNotNull"]},
            "showUnfilled": True,
        },
        "id": next_id(),
    }


def timeseries_rich(title: str, fields: list[str], y: int, h: int) -> dict:
    targets = []
    for i, f in enumerate(fields):
        targets.append(
            {
                "refId": chr(65 + i),
                "datasource": {"type": "influxdb", "uid": DS_UID},
                "query": flux_range(f),
            }
        )
    return {
        "type": "timeseries",
        "title": title,
        "gridPos": {"h": h, "w": 24, "x": 0, "y": y},
        "datasource": {"type": "influxdb", "uid": DS_UID},
        "targets": targets,
        "fieldConfig": {
            "defaults": {
                "custom": {
                    "drawStyle": "line",
                    "lineInterpolation": "smooth",
                    "lineWidth": 2,
                    "fillOpacity": 25,
                    "gradientMode": "opacity",
                    "spanNulls": False,
                },
                "color": {"mode": "palette-classic"},
            },
            "overrides": [],
        },
        "options": {
            "legend": {"displayMode": "list", "placement": "bottom", "calcs": ["lastNotNull"]},
        },
        "id": next_id(),
    }


# --- 패널 구성 ---
y = 0
panels.append(
    {
        "type": "text",
        "title": "",
        "gridPos": {"h": 3, "w": 24, "x": 0, "y": y},
        "options": {
            "mode": "markdown",
            "content": "### CronusFarm 운영 화면 (Grafana)\n\n- **데이터**: Node-RED MQTT 플로우가 Influx `tele` 로 적재한 필드를 그립니다.\n- **제어 UI**는 Node-RED Dashboard를 쓰고, **모니터링·화려한 그래프**는 이 대시보드에서 구성합니다.\n- 센서 필드명(`temp` 등)이 펌웨어/플로우와 다르면 해당 Stat 패널만 데이터 없음으로 나올 수 있습니다.\n",
        },
        "id": next_id(),
    }
)
y += 3

panels.append(row("환경 스냅샷 (Stat)", y))
y += 1
# 흔한 S: 섹션 키 — 없으면 패널만 비어 있음
_env = [
    ("내부 온도", "temp", "celsius", [{"color": "blue", "value": None}, {"color": "green", "value": 18}, {"color": "red", "value": 30}]),
    ("습도", "humidity", "percent", [{"color": "super-light-blue", "value": None}, {"color": "green", "value": 40}, {"color": "orange", "value": 85}]),
    ("pH", "ph", "none", [{"color": "red", "value": None}, {"color": "yellow", "value": 5.5}, {"color": "green", "value": 6.0}, {"color": "orange", "value": 7.5}]),
    ("EC", "ec", "µS/cm", [{"color": "dark-blue", "value": None}, {"color": "green", "value": 500}, {"color": "orange", "value": 2500}]),
    ("CO₂", "co2", "ppm", [{"color": "green", "value": None}, {"color": "yellow", "value": 800}, {"color": "red", "value": 1500}]),
]
_w = 4
for i, (title, field, unit, steps) in enumerate(_env):
    panels.append(stat_panel(title, field, y, i * _w, _w, unit, steps))
y += 5

panels.append(row("가드 · 외기", y))
y += 1
panels.append(
    gauge_panel(
        "가드 정상(1=OK)",
        "guard_ok",
        y,
        0,
        6,
        "none",
        [{"color": "red", "value": None}, {"color": "green", "value": 1}],
    )
)
panels.append(
    gauge_panel(
        "Max-on 트립",
        "guard_mx",
        y,
        6,
        6,
        "none",
        [{"color": "green", "value": None}, {"color": "red", "value": 1}],
    )
)
panels.append(
    gauge_panel(
        "Min-off 대기",
        "guard_mf",
        y,
        12,
        6,
        "none",
        [{"color": "green", "value": None}, {"color": "orange", "value": 1}],
    )
)
panels.append(
    gauge_panel(
        "기상청 온도",
        "kma_temp",
        y,
        18,
        6,
        "celsius",
        [{"color": "blue", "value": None}, {"color": "green", "value": 15}, {"color": "red", "value": 32}],
    )
)
y += 6

panels.append(row("채널 출력 (Bar gauge, 마지막 값)", y))
y += 1
panels.append(
    bargauge_channels(
        "LED / 펌프 ON 비율 (0–1)",
        ["led_a1", "led_a2", "led_b1", "led_b2", "pump_a1", "pump_a2", "pump_b1", "pump_b2"],
        y,
        8,
    )
)
y += 8

panels.append(row("팬 · 예비 채널", y))
y += 1
panels.append(
    bargauge_channels(
        "Fan / C·D 펌프",
        ["fan_a1", "fan_a2", "fan_b1", "fan_b2", "pump_c1", "pump_c2", "pump_d1", "pump_d2"],
        y,
        6,
    )
)
y += 6

panels.append(row("시계열 추세", y))
y += 1
panels.append(
    timeseries_rich(
        "환경 (temp·humidity·ph·ec)",
        ["temp", "humidity", "ph", "ec"],
        y,
        8,
    )
)
y += 8
panels.append(
    timeseries_rich(
        "가드 / 외기",
        ["guard_ok", "guard_mx", "guard_mf", "kma_temp"],
        y,
        7,
    )
)
y += 7
panels.append(
    timeseries_rich(
        "LED·펌프·팬 (0–1)",
        [
            "led_a1",
            "led_a2",
            "led_b1",
            "pump_a1",
            "pump_a2",
            "pump_b1",
            "pump_b2",
            "fan_a1",
            "fan_b1",
            "fan_b2",
        ],
        y,
        10,
    )
)

dash = {
    "uid": "cronusfarm-operator-ui",
    "title": "CronusFarm 운영 UI (Grafana 그래픽)",
    "tags": ["cronusfarm", "operator", "ui", "influx"],
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
