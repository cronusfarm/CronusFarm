# -*- coding: utf-8 -*-
"""모니터: Arduino 행 순서·R4 MQTT/USB 구분·KMA·누적광량 색."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DASH = ROOT / "nodered" / "flows_cronusfarm_dashboard.json"

FN_CALC = "fn_calc_online"
FN_WIFI = "fn_cf_arduino_wifi_tele"
FN_SEEN = "fn_seen_tele"
TPL_SSID = "ui_txt_arduino_wifi_ssid"
TPL_IP = "ui_txt_arduino_wifi_ip"
TPL_CONN = "ui_tpl_conn_line"
TPL_MQTT = "ui_tpl_status_line"
TPL_R3 = "ui_tpl_r3_panel_line"
TPL_USB = "ui_tpl_r4_usb_line"
TPL_FARM = "ui_tpl_farm_env"
TPL_DLI = "ui_tpl_led_dli_24h"

FN_WIFI_CODE = r"""const s = (msg.payload || '').toString();
const parts = s.split('|').map(x => x.trim());
const w = parts.find(x => x.startsWith('W:'));
let ssid = '—';
let ip = '—';
if (w) {
  const rest = w.slice(2).trim();
  const k = rest.lastIndexOf(' ip=');
  if (k >= 0 && rest.startsWith('ssid=')) {
    ssid = rest.slice(5, k).trim() || '—';
    ip = rest.slice(k + 4).trim() || '—';
    if (ip === '0.0.0.0') ip = '—';
  }
}
return [[{ payload: ssid }], [{ payload: ip }]];"""

FN_CALC_CODE = r"""const now=Date.now();
const ls=flow.get('arduinoLastStatusMs')||0;
const lt=flow.get('arduinoLastTeleMs')||0;
const TELE_MS=90000;
const teleOk = lt > 0 && (now - lt) < TELE_MS;
const pl=msg.payload;
let raw='';
if(typeof pl==='string'&&pl.length){ raw=pl; }
else { raw=(flow.get('lastTeleStr')||'').toString(); }
function wifiFromTele(s) {
  const m = String(s||'').match(/\|\s*W:([^|]+)/);
  if (!m) {
    const c = (flow.get('lastWifiIp')||'').toString();
    return { ok: !!c && c !== '0.0.0.0', ip: c, hint: 'W: 없음' };
  }
  const w = m[1].trim();
  const ipM = w.match(/ip[=](\d+\.\d+\.\d+\.\d+)/);
  const ip = ipM ? ipM[1] : '';
  const ok = !!(ip && ip !== '0.0.0.0');
  if (ok) flow.set('lastWifiIp', ip);
  const useIp = ok ? ip : ((flow.get('lastWifiIp')||'').toString() || ip);
  return { ok, ip: useIp, hint: w.length > 48 ? w.slice(0, 48) + '…' : w };
}
function panelR3FromTele(s) {
  const m = String(s||'').match(/\|\s*P:([^|]+)/);
  if (!m) return { ok: null, hint: 'tele P: 없음' };
  const p = m[1].trim();
  const ready = /ready=1/.test(p);
  const rcM = p.match(/i2c_rc=(\d+)/);
  const rc = rcM ? parseInt(rcM[1], 10) : 255;
  return { ok: ready && rc === 0, hint: p.length > 40 ? p.slice(0, 40) + '…' : p };
}
const wifi = wifiFromTele(raw);
const r3 = panelR3FromTele(raw);
const usbMs = flow.get('arduinoLastUsbMs') || 0;
const USB_MS = 90000;
const usbOk = usbMs > 0 && (now - usbMs) < USB_MS;
const wifiOk = teleOk || wifi.ok;
msg._ok = teleOk;
msg._wifiOk = wifiOk;
msg._wifiIp = wifi.ip || '';
msg._wifiHint = wifiOk ? (wifi.hint || 'tele 수신') : wifi.hint;
msg._r3ok = r3.ok;
msg._r3hint = r3.hint;
msg._usbOk = usbOk;
msg._usbAge = usbMs ? Math.floor((now - usbMs) / 1000) : null;
msg.teleAge = lt ? Math.floor((now - lt) / 1000) : null;
msg.payload = raw;
return [msg, msg, msg, msg];"""

_FMT_FILE = Path(__file__).resolve().parent / "_farm_env_fmt.txt"
KMA_FMT = _FMT_FILE.read_text(encoding="utf-8").strip() if _FMT_FILE.is_file() else ""

def main() -> int:
    data = json.loads(DASH.read_text(encoding="utf-8-sig"))
    by = {n["id"]: n for n in data if isinstance(n, dict) and n.get("id")}

    wifi = by.get(FN_WIFI)
    if not wifi:
        wifi = {
            "id": FN_WIFI,
            "type": "function",
            "z": "tab_cronus_dash",
            "name": "tele W: SSID/IP",
            "func": FN_WIFI_CODE,
            "outputs": 2,
            "wires": [[TPL_SSID], [TPL_IP]],
        }
        by[FN_WIFI] = wifi
    else:
        wifi["func"] = FN_WIFI_CODE
        wifi["outputs"] = 2
        wifi["wires"] = [[TPL_SSID], [TPL_IP]]

    seen = by.get(FN_SEEN)
    if seen:
        w = seen.get("wires") or [[]]
        outs = list(w[0]) if w else []
        for x in [FN_WIFI, FN_CALC]:
            if x not in outs:
                outs.append(x)
        seen["wires"] = [outs]

    calc = by.get(FN_CALC)
    if calc:
        calc["func"] = FN_CALC_CODE
        calc["outputs"] = 4
        calc["wires"] = [[TPL_CONN], [TPL_MQTT], [TPL_R3], [TPL_USB]]

    orders = [
        (TPL_SSID, "Arduino WiFi SSID", 1, "ui_text"),
        (TPL_IP, "Arduino IP", 2, "ui_text"),
        (TPL_CONN, "R4 연결 (WiFi)", 3, "ui_template"),
        (TPL_MQTT, "R4 MQTT (WiFi)", 4, "ui_template"),
        (TPL_R3, "R3 패널 (I2C)", 5, "ui_template"),
        (TPL_USB, "MQTT USB (시리얼)", 6, "ui_template"),
    ]
    for nid, name, order, typ in orders:
        n = by.get(nid)
        if not n:
            continue
        n["name"] = name
        n["order"] = order
        n["group"] = "ui_grp_arduino"
        n["width"] = "12" if typ == "ui_template" else "6"
        if typ == "ui_template":
            n["height"] = 1

    ag = by.get("ui_grp_arduino")
    if ag:
        ag["name"] = "Arduino (R4 · R3)"

    farm = by.get(TPL_FARM)
    if farm:
        farm["format"] = KMA_FMT
        farm["height"] = 9
        farm["width"] = "12"

    DASH.write_text(
        json.dumps(data, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    print("OK patch_dashboard_monitor_layout")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
