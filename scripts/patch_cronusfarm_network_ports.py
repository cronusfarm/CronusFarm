# -*- coding: utf-8 -*-
"""MQTT 51883·호스트 env·대시보드 브라우저 Pi 호스트 자동 선택 패치."""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NET = json.loads((ROOT / "scripts" / "cronusfarm-network.json").read_text(encoding="utf-8"))
HOSTS = NET["hosts"]
PORTS = NET["ports"]

MQTT_JSON = ROOT / "nodered" / "flows_cronusfarm_mqtt.json"
DASH = ROOT / "nodered" / "flows_cronusfarm_dashboard.json"
MOSQ_CONF = ROOT / "deploy" / "mosquitto" / "conf.d" / "cronusfarm.conf"

CF_PI_HOST_JS = f"""const h = (env.get('CRONUSFARM_PI_HOST') || '{HOSTS["tailscale"]}').toString().trim();
msg.payload = h || '{HOSTS["tailscale"]}';
return msg;"""

# 브라우저: 로컬 NR(1881)은 Tailscale 고정, 그 외 LAN→TS→DuckDNS (CCTV 8080 프로브)
CF_RESOLVE_BOOT = f"""
<script type="text/javascript">
(function(){{
  if(window.__cfPiNetBoot)return;
  window.__cfPiNetBoot=1;
  var LAN='{HOSTS["lan"]}';
  var TS='{HOSTS["tailscale"]}';
  var DUCK='{HOSTS["duckdns"]}';
  var CCTV={PORTS["cctvStream"]};
  function cfPiHost(){{
    try{{var s=localStorage.getItem('cfPiHost');if(s&&String(s).trim())return String(s).trim();}}catch(e){{}}
    return window.__cfResolvedPiHost||TS;
  }}
  window.cfPiHost=cfPiHost;
  function probe(host){{
    return new Promise(function(resolve){{
      var img=new Image();
      var t=setTimeout(function(){{img.src='';resolve(false);}},2800);
      img.onload=function(){{clearTimeout(t);resolve(true);}};
      img.onerror=function(){{clearTimeout(t);resolve(false);}};
      img.src='http://'+host+':'+CCTV+'/stream?cfprobe='+Date.now();
    }});
  }}
  async function resolve(){{
    var p=String(location.port||'');
    var h=location.hostname||'';
    if(p==='1881'||h==='127.0.0.1'||h==='localhost'){{
      window.__cfResolvedPiHost=TS;
      window.dispatchEvent(new CustomEvent('cf-pi-host',{{detail:TS}}));
      return;
    }}
    if(await probe(LAN)){{window.__cfResolvedPiHost=LAN;return;}}
    if(await probe(TS)){{window.__cfResolvedPiHost=TS;return;}}
    if(await probe(DUCK)){{window.__cfResolvedPiHost=DUCK;return;}}
    window.__cfResolvedPiHost=TS;
    window.dispatchEvent(new CustomEvent('cf-pi-host',{{detail:window.__cfResolvedPiHost}}));
  }}
  resolve().catch(function(){{window.__cfResolvedPiHost=TS;}});
}})();
</script>
"""

MARK = "/* cf-pi-host-resolve-boot */"


def _patch_mqtt(data: list) -> int:
    n = 0
    for node in data:
        if node.get("type") != "mqtt-broker":
            continue
        if str(node.get("port")) != str(PORTS["mqtt"]):
            node["port"] = str(PORTS["mqtt"])
            n += 1
        name = (node.get("name") or "").lower()
        if "127.0.0.1" in str(node.get("broker", "")):
            continue
        if node.get("broker") in (HOSTS["lan"], HOSTS["tailscale"], HOSTS["duckdns"]):
            continue
        node["broker"] = HOSTS["tailscale"]
        n += 1
    return n


def _patch_dashboard(data: list) -> int:
    n = 0
    for node in data:
        if node.get("id") == "fn_pi_host":
            node["func"] = CF_PI_HOST_JS
            n += 1
        if node.get("id") == "ui_tpl_css_cronus":
            fmt = node.get("format", "")
            if MARK in fmt:
                fmt = re.sub(
                    re.escape(MARK) + r"[\s\S]*?</script>\s*",
                    MARK + CF_RESOLVE_BOOT + "\n",
                    fmt,
                    count=1,
                )
            elif "window.cfPiHost" not in fmt:
                ins = fmt.find("</style>")
                if ins >= 0:
                    fmt = fmt[:ins] + "\n" + MARK + CF_RESOLVE_BOOT + "\n" + fmt[ins:]
            node["format"] = fmt
            n += 1
    # AI 카메라·원격 프로브: cfPiHost() 사용 (전역)
    cam_src = f"return pr+'//'+cfPiHost()+':{PORTS['cctvStream']}/stream';"
    for node in data:
        fid = node.get("id") or ""
        if fid == "nr_node_ui_ai_stream" or "cf-ai-mjpeg" in (node.get("format") or ""):
            fmt = node.get("format", "")
            fmt = re.sub(
                r"return pr\+\"//\"\+cfPiHost\(\)\+\":8080/stream\";",
                cam_src,
                fmt,
            )
            fmt = re.sub(
                r"return pr\+'//'\+cfPiHost\(\)+':8080/stream';",
                cam_src,
                fmt,
            )
            if "ida.mango-larch.ts.net" in fmt and "cfPiHost()" not in fmt:
                fmt = fmt.replace(
                    "ida.mango-larch.ts.net",
                    "'+cfPiHost()+'",
                    1,
                )
            node["format"] = fmt
            n += 1
    return n


def _patch_pi_status_probe() -> None:
    p = ROOT / "scripts" / "patch_dashboard_pi_status_local.py"
    if not p.is_file():
        return
    txt = p.read_text(encoding="utf-8")
    txt = txt.replace("await tcpOk(1883)", f"await tcpOk({PORTS['mqtt']})")
    txt = txt.replace("await httpOk(1880, '/')", f"await httpOk({PORTS['nginx']}, '/')")
    txt = txt.replace("await httpOk(1882, '/')", f"await httpOk({PORTS['nrLatest']}, '/')")
    txt = txt.replace(
        "await httpOk(18766,",
        f"await httpOk({PORTS['sqliteBridge']},",
    )
    txt = txt.replace(
        "'ida.mango-larch.ts.net'",
        f"'{HOSTS['tailscale']}'",
    )
    p.write_text(txt, encoding="utf-8")


def _patch_mosquitto_conf() -> None:
    txt = MOSQ_CONF.read_text(encoding="utf-8")
    # Pi Mosquitto listen: LAN 1883 (외부 51883 은 라우터 포워딩)
    txt2 = re.sub(
        r"listener\s+\d+\s+0\.0\.0\.0",
        "listener 1883 0.0.0.0",
        txt,
        count=1,
    )
    if txt2 != txt:
        MOSQ_CONF.write_text(txt2, encoding="utf-8")


def main() -> None:
    mqtt = json.loads(MQTT_JSON.read_text(encoding="utf-8-sig"))
    c1 = _patch_mqtt(mqtt)
    MQTT_JSON.write_text(
        json.dumps(mqtt, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )

    dash = json.loads(DASH.read_text(encoding="utf-8-sig"))
    c2 = _patch_dashboard(dash)
    DASH.write_text(
        json.dumps(dash, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )

    _patch_pi_status_probe()
    _patch_mosquitto_conf()

  # secrets example
    sec = ROOT / "arduino" / "CronusFarm" / "secrets.h.example"
    if sec.is_file():
        st = sec.read_text(encoding="utf-8")
        st = re.sub(r"#define MQTT_PORT\s+\d+", f"#define MQTT_PORT {PORTS['mqtt']}", st)
        sec.write_text(st, encoding="utf-8")

    for py in [
        ROOT / "scripts" / "cronusfarm_hailo_stream.py",
        ROOT / "scripts" / "cronusfarm_camera_ai.py",
    ]:
        if not py.is_file():
            continue
        t = py.read_text(encoding="utf-8")
        t2 = re.sub(
            r"MQTT_PORT\s*=\s*\d+",
            f"MQTT_PORT = int(os.environ.get('CRONUSFARM_MQTT_PORT', '{PORTS['mqtt']}'))",
            t,
            count=1,
        )
        if "int(os.environ.get('CRONUSFARM_MQTT_PORT'" not in t and t2 == t:
            t2 = t.replace("MQTT_PORT = 1883", f"MQTT_PORT = {PORTS['mqtt']}")
        if t2 != t:
            py.write_text(t2, encoding="utf-8")

    merge = ROOT / "scripts" / "merge_nodered_deploy.py"
    if merge.is_file():
        subprocess.run([sys.executable, str(merge), "--use-split"], cwd=str(ROOT), check=True)

    print(f"OK network ports: mqtt={c1} dash={c2} mqtt_port={PORTS['mqtt']}")


if __name__ == "__main__":
    main()
