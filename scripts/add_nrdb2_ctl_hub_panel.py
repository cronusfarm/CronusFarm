# NRDB2 설정(/nrdb2/settings) 하단에 관제 허브 카드(D1 /ui 와 동등) 추가
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DASH = ROOT / "nodered" / "flows_cronusfarm_dashboard.json"

GROUP_ID = "f1e2d3c4b5a6800b"
TPL_ID = "f1e2d3c4b5a6f022"
PAGE_ID = "f1e2d3c4b5a68003"
TAB_Z = "tab_cronus_dash"
FN_KV = "cf_fn_ctl_kv"

FORMAT = r"""<template>
  <div class="cf2-ctlhub">
    <div class="cf-ctl-hub">
      <div class="t">스마트팜 관제 허브</div>
      <div class="s">목표 pH·EC·온도·습도를 설정하면 SQLite <code>settings_kv</code>에 저장됩니다. 시계열 그래프는 Grafana(InfluxDB)에서 확인하세요. 브리지 미기동 시 슬라이더는 HTTP 오류를 무시합니다.</div>
      <div class="badges">
        <span class="bd">Influx: tele + guard_*</span>
        <span class="bd">SQLite: 이력·설정</span>
        <span class="bd">DEVICE_ID: flow.deviceId</span>
      </div>
    </div>
    <div v-for="r in rows" :key="r.topic" class="cf2-slrow">
      <div class="cf2-sllab">{{ r.label }}</div>
      <input class="cf2-sl" type="range" :min="r.min" :max="r.max" :step="r.step" v-model.number="r.v" @change="push(r)" />
      <div class="cf2-slval">{{ fmt(r) }}</div>
    </div>
    <div class="cf2-hint">슬라이더를 놓을 때(change) SQLite 브리지로 전송됩니다.</div>
  </div>
</template>

<script>
export default {
  data () {
    return {
      rows: [
        { label: '목표 pH', topic: 'ctl_target_ph', min: 0, max: 14, step: 0.1, v: 7.0 },
        { label: '목표 EC (mS/cm)', topic: 'ctl_target_ec', min: 0, max: 3, step: 0.05, v: 1.0 },
        { label: '목표 온도 (°C)', topic: 'ctl_target_temp_c', min: 10, max: 35, step: 0.5, v: 25.0 },
        { label: '목표 습도 (%)', topic: 'ctl_target_rh_pct', min: 30, max: 90, step: 1, v: 60 }
      ]
    }
  },
  methods: {
    fmt (r) {
      const x = Number(r.v)
      if (!isFinite(x)) return '-'
      if (Math.abs(r.step) >= 1) return String(Math.round(x))
      return String(Math.round(x * 1000) / 1000).replace(/\.0+$/, (m) => m)
    },
    push (r) {
      const v = Number(r.v)
      if (!isFinite(v)) return
      this.send({ topic: r.topic, payload: v })
    }
  }
}
</script>

<style scoped>
.cf2-ctlhub { display: flex; flex-direction: column; gap: 10px; padding: 4px 2px 8px; }
.cf-ctl-hub {
  font-family: 'Noto Sans KR', system-ui, sans-serif;
  color: #e6edf7;
  padding: 10px 12px;
  background: linear-gradient(135deg, rgba(46,125,50,.28), rgba(13,71,161,.22));
  border-radius: 14px;
  border: 1px solid rgba(255,255,255,.1);
}
.cf-ctl-hub .t { font-size: 15px; font-weight: 800; margin-bottom: 6px; color: #b9f6ca; }
.cf-ctl-hub .s { font-size: 12px; line-height: 1.45; color: #c8d6ee; }
.cf-ctl-hub code { font-size: 11px; background: rgba(0,0,0,.25); padding: 1px 6px; border-radius: 6px; color: #e1f5fe; }
.cf-ctl-hub .badges { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; }
.cf-ctl-hub .bd { font-size: 11px; padding: 4px 10px; border-radius: 999px; background: rgba(255,255,255,.06); border: 1px solid rgba(255,255,255,.1); }
.cf2-slrow {
  display: grid;
  grid-template-columns: minmax(0, 8.5rem) 1fr 4.2rem;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  border-radius: 12px;
  background: rgba(255,255,255,.04);
  border: 1px solid rgba(255,255,255,.09);
}
.cf2-sllab { font-size: 12px; font-weight: 800; color: #e6edf7; }
.cf2-sl { width: 100%; accent-color: #4f8cff; }
.cf2-slval { font-size: 13px; font-weight: 800; color: #fff; text-align: right; font-variant-numeric: tabular-nums; }
.cf2-hint { font-size: 10px; color: #90a4ae; padding: 0 4px; }
</style>
"""


def main() -> None:
    data = json.loads(DASH.read_text(encoding="utf-8-sig"))
    ids = {n.get("id") for n in data if isinstance(n, dict)}
    if GROUP_ID in ids or TPL_ID in ids:
        print("SKIP: already inserted")
        return

    grp = {
        "id": GROUP_ID,
        "type": "ui-group",
        "name": "\uAD00\uC81C \uD5C8\uBE0C \u2014 \uD658\uACBD \uBAA9\uD45C\u00B7\uC784\uACC4 (SQLite)",
        "page": PAGE_ID,
        "width": "12",
        "height": "1",
        "order": 6,
        "showTitle": True,
        "className": "",
        "visible": "true",
        "disabled": "false",
        "groupType": "default",
    }
    tpl = {
        "id": TPL_ID,
        "type": "ui-template",
        "z": TAB_Z,
        "group": GROUP_ID,
        "page": "",
        "ui": "",
        "name": "NRDB2 관제 허브(목표 pH\u00B7EC\u00B7온습)",
        "order": 0,
        "width": "12",
        "height": "12",
        "head": "",
        "format": FORMAT,
        "storeOutMessages": True,
        "passthru": False,
        "resendOnRefresh": True,
        "templateScope": "local",
        "className": "",
        "x": 200,
        "y": 1740,
        "wires": [[FN_KV]],
    }
    data.append(grp)
    data.append(tpl)
    DASH.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    print(f"OK appended {GROUP_ID} {TPL_ID}")


if __name__ == "__main__":
    main()
