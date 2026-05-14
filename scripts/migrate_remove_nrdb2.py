# NRDB2(FlowFuse) 제거: 정적 HTML(nodered/dashboard/…) 생성 + MQTT KV 프록시. 대시보드 설정 탭 UI는 저장소에서 자동 생성하지 않음.
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NR = ROOT / "nodered"
DEV = NR / "flows_cronusfarm_devflow_flow.json"
DASH = NR / "flows_cronusfarm_dashboard.json"
MQTT = NR / "flows_cronusfarm_mqtt.json"
HTML_OUT = NR / "dashboard" / "cronusfarm_d1_settings_tools.html"
SCH_SRC = ROOT / "_t_f1e2d3c4b5a6f020.txt"
CTL_SRC = ROOT / "_ctl.txt"

NR_DEV_IDS = {
    "f1e2d3c4b5a68002",
    "f1e2d3c4b5a68003",
    "f1e2d3c4b5a68004",
    "f1e2d3c4b5a68005",
    "f1e2d3c4b5a68006",
    "f1e2d3c4b5a68007",
    "f1e2d3c4b5a68008",
    "f1e2d3c4b5a68009",
    "f1e2d3c4b5a6800a",
    "f1e2d3c4b5a6800b",
    "cf_nrdb2_page_schedhub",
    "cf_nrdb2_grp_sched",
    "cf_nrdb2_grp_hub",
}

NR_DASH_TEMPLATE_IDS = {
    "f1e2d3c4b5a6f010",
    "f1e2d3c4b5a6f011",
    "f1e2d3c4b5a6f012",
    "f1e2d3c4b5a6f013",
    "f1e2d3c4b5a6f014",
    "f1e2d3c4b5a6f020",
    "f1e2d3c4b5a6f022",
    "cf_nrdb2_t_sched_clone",
    "cf_nrdb2_t_hub_clone",
}

RM_GRP = {"ui_grp_nrdb2_shell", "ui_tpl_nrdb2_in_settings"}


def split_vue_sfc(text: str) -> tuple[str, str, str]:
    mt = re.search(r"<template>\s*([\s\S]*?)\s*</template>", text)
    ms = re.search(r"<script>\s*([\s\S]*?)\s*</script>", text)
    mz = re.search(r"<style[^>]*>\s*([\s\S]*?)\s*</style>", text)
    if not mt or not ms:
        raise ValueError("template/script 없음")
    return mt.group(1).strip(), ms.group(1).strip(), (mz.group(1).strip() if mz else "")


def build_settings_html() -> str:
    sch_raw = SCH_SRC.read_text(encoding="utf-8")
    ctl_raw = CTL_SRC.read_text(encoding="utf-8")
    sch_tpl, sch_js, sch_css = split_vue_sfc(sch_raw)
    ctl_tpl, ctl_js, ctl_css = split_vue_sfc(ctl_raw)
    sch_tpl = sch_tpl.replace(
        '<input v-model="deviceId"',
        '<input id="cf-sch-device-id" v-model="deviceId"',
        1,
    )
    sch_js = sch_js.replace("export default", "const ScheduleApp =")
    sch_js = sch_js.replace(
        "for (let i = 0; i < 7; i++) this.$set(row.days, i, true)",
        "for (let i = 0; i < 7; i++) row.days[i] = true",
    )
    ctl_js = ctl_js.replace("export default", "const CtlApp =")
    ctl_js = ctl_js.replace(
        """    push (r) {
      const v = Number(r.v)
      if (!isFinite(v)) return
      this.send({ topic: r.topic, payload: v })
    }""",
        """    async push (r) {
      const v = Number(r.v)
      if (!isFinite(v)) return
      const el = document.getElementById('cf-sch-device-id')
      const deviceId = (el && el.value) ? String(el.value).trim() : 'cronusfarm-01'
      const url = (window.location.origin || '') + '/farm/cronusfarm-sqlite/settings/kv'
      try {
        await fetch(url, {
          method: 'POST',
          credentials: 'same-origin',
          headers: { 'Content-Type': 'application/json; charset=utf-8' },
          body: JSON.stringify({ device_id: deviceId, key: r.topic, value: String(v) })
        })
      } catch (e) { console.warn(e) }
    }""",
    )
    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>CronusFarm 설정 도구 (D1)</title>
  <script src="https://cdn.jsdelivr.net/npm/vue@3/dist/vue.global.prod.js"></script>
  <style>
    :root{{
      --cf-bg0:#070c15;
      --cf-bg:#0b1220;
      --cf-card:#0f1b31;
      --cf-line: rgba(255,255,255,.08);
      --cf-text:#e6edf7;
      --cf-muted:#9db0cc;
      --cf-accent:#4f8cff;
      --cf-title:#FFD54F;
      --cf-good:#34c759;
      --cf-bad:#ff5a4a;
      --cf-radius:14px;
    }}
    html,body{{ height:100%; }}
    body {{
      margin:0;
      padding:12px;
      background: linear-gradient(180deg, var(--cf-bg0) 0%, var(--cf-bg) 60%, var(--cf-bg0) 100%);
      color: var(--cf-text);
      font-family: system-ui,'Malgun Gothic',sans-serif;
    }}
    .cf-d1-tools-wrap {{ max-width:1100px; margin:0 auto; }}
    .cf-d1-note {{ font-size:11px;color:var(--cf-muted);margin-bottom:12px;line-height:1.5; }}
    .cf-card {{
      background: var(--cf-card);
      border-radius: var(--cf-radius);
      border: 1px solid var(--cf-line);
      box-shadow: 0 10px 30px rgba(0,0,0,.35);
    }}
    {sch_css}
    {ctl_css}

    /* ---- 디자인 통일 오버라이드 (D1 iframe) ---- */
    .cf2-schedule{{ background: var(--cf-card) !important; border-color: var(--cf-line) !important; border-radius: var(--cf-radius) !important; }}
    .cf2-sch-hd{{ color: var(--cf-title) !important; }}
    .cf2-sch-sub,.cf2-sch-cap,.cf2-sch-tag,.cf2-sch-foot,.cf2-hint{{ color: var(--cf-muted) !important; }}
    .cf2-sch-devbox,.cf2-sch-topm{{ background: rgba(255,255,255,.03) !important; border-color: var(--cf-line) !important; }}
    .cf2-sch-inp,.cf2-sch-sel,.cf2-sch-time,.cf2-sch-num{{ background: rgba(0,0,0,.22) !important; border-color: rgba(255,255,255,.14) !important; color: var(--cf-text) !important; }}
    .cf2-sch-btn{{ background: rgba(255,255,255,.06) !important; border-color: rgba(255,255,255,.14) !important; }}
    .cf2-sch-prim{{ border-color: rgba(52,199,89,.45) !important; }}
    .cf2-sch-x{{ background: rgba(255,90,74,.20) !important; border-color: rgba(255,90,74,.35) !important; }}
    .cf2-sch-add{{ border-color: rgba(255,255,255,.20) !important; color: var(--cf-muted) !important; }}
    .cf-ctl-hub{{ background: rgba(255,255,255,.03) !important; border-color: var(--cf-line) !important; }}
    .cf-ctl-hub .t{{ color: var(--cf-title) !important; }}
    .cf2-slrow{{ background: rgba(255,255,255,.03) !important; border-color: var(--cf-line) !important; }}
    .cf2-sllab{{ color: var(--cf-text) !important; }}
    .cf2-sl{{ accent-color: var(--cf-accent); }}
  </style>
</head>
<body>
<div class="cf-d1-tools-wrap">
  <p class="cf-d1-note">Dashboard 1 전용: NRDB2 없이 스케줄·관제 UI. 오프라인이면 Vue CDN 미러 또는 로컬 번들을 쓰세요.</p>
  <script type="text/x-template" id="tpl-schedule">
{sch_tpl}
  </script>
  <div id="mount-schedule"></div>
  <hr style="border:none;border-top:1px solid rgba(255,255,255,.1);margin:20px 0"/>
  <script type="text/x-template" id="tpl-ctl">
{ctl_tpl}
  </script>
  <div id="mount-ctl"></div>
</div>
<script>
{sch_js}
ScheduleApp.template = '#tpl-schedule';
Vue.createApp(ScheduleApp).mount('#mount-schedule');
{ctl_js}
CtlApp.template = '#tpl-ctl';
Vue.createApp(CtlApp).mount('#mount-ctl');
</script>
</body>
</html>
"""


def patch_mqtt_kv_proxy(nodes: list) -> bool:
    if any(n.get("id") == "cf_hin_kv_post" for n in nodes):
        return False
    insert_at = next(i for i, n in enumerate(nodes) if n.get("id") == "cf_hres_sch") + 1
    block = [
        {
            "id": "cf_hin_kv_post",
            "type": "http in",
            "z": "b1c5a1f1d7a2a3a1",
            "name": "SQLite KV POST",
            "url": "/farm/cronusfarm-sqlite/settings/kv",
            "method": "post",
            "upload": False,
            "swaggerDoc": "",
            "x": 190,
            "y": 620,
            "wires": [["cf_fn_kv_post"]],
        },
        {
            "id": "cf_fn_kv_post",
            "type": "function",
            "z": "b1c5a1f1d7a2a3a1",
            "name": "→ bridge KV POST",
            "func": "const base = (env.get('CRONUSFARM_SQLITE_BRIDGE_URL') || 'http://127.0.0.1:18766').toString().replace(/\\/$/, '');\nmsg.method = 'POST';\nmsg.url = base + '/settings/kv';\nmsg.headers = { 'Content-Type': 'application/json; charset=utf-8' };\nlet body = msg.payload;\nif (typeof body === 'object' && body !== null) body = JSON.stringify(body);\nelse body = body != null ? String(body) : '{}';\nmsg.payload = body;\nreturn msg;",
            "outputs": 1,
            "noerr": 0,
            "initialize": "",
            "finalize": "",
            "libs": [],
            "x": 440,
            "y": 620,
            "wires": [["cf_hreq_kv"]],
        },
        {
            "id": "cf_hreq_kv",
            "type": "http request",
            "z": "b1c5a1f1d7a2a3a1",
            "name": "bridge KV",
            "method": "use",
            "ret": "txt",
            "paytoqs": "ignore",
            "url": "",
            "tls": "",
            "persist": False,
            "proxy": "",
            "insecureHTTPParser": False,
            "authType": "",
            "senderr": False,
            "headers": [],
            "x": 700,
            "y": 620,
            "wires": [["cf_hres_kv"]],
        },
        {
            "id": "cf_hres_kv",
            "type": "http response",
            "z": "b1c5a1f1d7a2a3a1",
            "name": "KV 응답",
            "statusCode": "",
            "headers": {},
            "x": 930,
            "y": 620,
            "wires": [],
        },
    ]
    for i, n in enumerate(block):
        nodes.insert(insert_at + i, n)
    return True


def main() -> None:
    HTML_OUT.parent.mkdir(parents=True, exist_ok=True)
    HTML_OUT.write_text(build_settings_html(), encoding="utf-8")
    print("wrote", HTML_OUT)

    mq = json.loads(MQTT.read_text(encoding="utf-8-sig"))
    if patch_mqtt_kv_proxy(mq):
        MQTT.write_text(json.dumps(mq, ensure_ascii=False, indent=2), encoding="utf-8")
        print("mqtt: +KV POST proxy")

    dev = json.loads(DEV.read_text(encoding="utf-8-sig"))
    dev = [n for n in dev if n.get("id") not in NR_DEV_IDS]
    DEV.write_text(json.dumps(dev, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print("devflow: removed NRDB2 nodes")

    dash = json.loads(DASH.read_text(encoding="utf-8-sig"))
    dash = [n for n in dash if n.get("id") not in NR_DASH_TEMPLATE_IDS.union(RM_GRP)]

    DASH.write_text(json.dumps(dash, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print("dashboard: NRDB2 템플릿 id 제거(설정 탭은 수동 구성)")


if __name__ == "__main__":
    main()
