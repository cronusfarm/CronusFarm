# -*- coding: utf-8 -*-
"""
Farm 환경(KMA+온실) 카드: 템플릿·merge·MQTT 배선 일괄 보정.

- KMA는 cache → merge → ui_tpl 만 통과 (cache가 ui_tpl에 직접 가면 라벨 누락·갱신 꼬임)
- 온실 온도/습도: PHW snapshot(temp_c, humidity_pct) 표시
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DASH = ROOT / "nodered" / "flows_cronusfarm_dashboard.json"

FLOW_FILES = [
    DASH,
    ROOT / "nodered" / "flows_cronusfarm_mqtt.json",
    ROOT / "nodered" / "merged-deploy.json",
    ROOT / "nodered" / "CronusFarm_NodeRED_flow.json",
]

_FMT_FILE = Path(__file__).resolve().parent / "_farm_env_fmt.txt"
KMA_FMT = _FMT_FILE.read_text(encoding="utf-8").strip() if _FMT_FILE.is_file() else ""

FN_KMA_CACHE = r"""function fmtKmaObsLabel(o) {
  if (!o || typeof o !== 'object') return '';
  const d = String(o.base_date || '').trim();
  let t = String(o.base_time != null ? o.base_time : '').trim();
  if (d.length < 8) return '';
  if (!t) t = '0000';
  t = t.padStart(4, '0');
  return d.slice(0, 4) + '.' + d.slice(4, 6) + '.' + d.slice(6, 8) + ' ' + t.slice(0, 2) + ':' + t.slice(2, 4) + ' KST';
}
function kmaPtyLabel(v, rn1) {
  const m = { '0': '없음', '1': '비', '2': '비/눈', '3': '눈', '4': '소나기', '5': '빗방울', '6': '빗방울·눈날림', '7': '눈날림' };
  let s = (v === null || v === undefined || v === '') ? '—' : (m[String(v)] || String(v));
  const rn = Number(rn1);
  if ((s === '없음' || s === '—') && Number.isFinite(rn) && rn > 0) s = '강우';
  return s;
}
function windCompass(deg) {
  const n = Number(deg);
  if (!Number.isFinite(n)) return '';
  const dirs = ['북', '북동', '동', '남동', '남', '남서', '서', '북서'];
  return dirs[Math.round(((n % 360) / 45)) % 8];
}
function fmtPrecipDisplay(rn1) {
  const n = Number(rn1);
  if (!Number.isFinite(n)) return '';
  return (n <= 0 ? '0' : String(n)) + ' mm';
}
function uvLevelInfo(n) {
  if (n >= 11) return { level: '위험', key: 'danger' };
  if (n >= 8) return { level: '매우높음', key: 'vhigh' };
  if (n >= 6) return { level: '높음', key: 'high' };
  if (n >= 3) return { level: '보통', key: 'normal' };
  return { level: '낮음', key: 'low' };
}
function fmtUvFields(uv) {
  const n = Number(uv);
  if (!Number.isFinite(n)) return { mw: '', idx: '', level: '', levelKey: '' };
  const mwN = n * 0.25;
  const mw = mwN < 0.01 ? mwN.toFixed(3) : mwN.toFixed(2);
  const idx = Math.abs(n - Math.round(n)) < 0.05 ? String(Math.round(n)) : n.toFixed(1);
  const info = uvLevelInfo(n);
  return { mw: mw, idx: idx, level: info.level, levelKey: info.key };
}
function pmLevelInfo(grade, pm) {
  const gm = { '1': ['좋음', 'good'], '2': ['보통', 'normal'], '3': ['나쁨', 'bad'], '4': ['매우나쁨', 'vbad'] };
  if (gm[String(grade)]) return { level: gm[String(grade)][0], key: gm[String(grade)][1] };
  const n = Number(pm);
  if (!Number.isFinite(n)) return { level: '', key: '' };
  if (n <= 30) return { level: '좋음', key: 'good' };
  if (n <= 80) return { level: '보통', key: 'normal' };
  if (n <= 150) return { level: '나쁨', key: 'bad' };
  return { level: '매우나쁨', key: 'vbad' };
}
function fmtPmFields(pm10, grade) {
  const n = Number(pm10);
  if (!Number.isFinite(n)) return { val: '', level: '', levelKey: '' };
  const info = pmLevelInfo(grade, n);
  return { val: n + ' ㎍/m³', level: info.level, levelKey: info.key };
}
function enrichKmaAir(p) {
  const uv = fmtUvFields(p.kma_uv_index);
  p.kma_uv_mw = uv.mw;
  p.kma_uv_idx = uv.idx;
  p.kma_uv_level = uv.level;
  p.kma_uv_level_key = uv.levelKey;
  const pm = fmtPmFields(p.kma_pm10, p.kma_pm10_grade);
  p.kma_pm_val = pm.val;
  p.kma_pm_level = pm.level;
  p.kma_pm_level_key = pm.levelKey;
}
function enrichKma(p) {
  if (!p || typeof p !== 'object') return p;
  p.kma_obs_label = fmtKmaObsLabel(p);
  p.kma_precip_label = kmaPtyLabel(p.kma_precip_type ?? p.kma_pty, p.kma_precip_1h);
  p.kma_wind_compass = windCompass(p.kma_wind_dir);
  p.kma_precip_display = fmtPrecipDisplay(p.kma_precip_1h);
  enrichKmaAir(p);
  return p;
}
let p = msg.payload;
if (typeof p === 'string') {
  try { p = JSON.parse(p); } catch (e) { return null; }
}
if (p && typeof p === 'object') {
  p = enrichKma(p);
  flow.set('kmaSnapshot', p);
  global.set('kmaSnapshot', p);
  flow.set('kmaSnapshotTs', Date.now());
  global.set('kmaSnapshotTs', Date.now());
}
return msg;"""

FN_FARM_ENV_MERGE = r"""function fmtKmaObsLabel(o) {
  if (!o || typeof o !== 'object') return '';
  const d = String(o.base_date || '').trim();
  let t = String(o.base_time != null ? o.base_time : '').trim();
  if (d.length < 8) return '';
  if (!t) t = '0000';
  t = t.padStart(4, '0');
  return d.slice(0, 4) + '.' + d.slice(4, 6) + '.' + d.slice(6, 8) + ' ' + t.slice(0, 2) + ':' + t.slice(2, 4) + ' KST';
}
function kmaPtyLabel(v, rn1) {
  const m = { '0': '없음', '1': '비', '2': '비/눈', '3': '눈', '4': '소나기', '5': '빗방울', '6': '빗방울·눈날림', '7': '눈날림' };
  let s = (v === null || v === undefined || v === '') ? '—' : (m[String(v)] || String(v));
  const rn = Number(rn1);
  if ((s === '없음' || s === '—') && Number.isFinite(rn) && rn > 0) s = '강우';
  return s;
}
function windCompass(deg) {
  const n = Number(deg);
  if (!Number.isFinite(n)) return '';
  const dirs = ['북', '북동', '동', '남동', '남', '남서', '서', '북서'];
  return dirs[Math.round(((n % 360) / 45)) % 8];
}
function fmtPrecipDisplay(rn1) {
  const n = Number(rn1);
  if (!Number.isFinite(n)) return '';
  return (n <= 0 ? '0' : String(n)) + ' mm';
}
function uvLevelInfo(n) {
  if (n >= 11) return { level: '위험', key: 'danger' };
  if (n >= 8) return { level: '매우높음', key: 'vhigh' };
  if (n >= 6) return { level: '높음', key: 'high' };
  if (n >= 3) return { level: '보통', key: 'normal' };
  return { level: '낮음', key: 'low' };
}
function fmtUvFields(uv) {
  const n = Number(uv);
  if (!Number.isFinite(n)) return { mw: '', idx: '', level: '', levelKey: '' };
  const mwN = n * 0.25;
  const mw = mwN < 0.01 ? mwN.toFixed(3) : mwN.toFixed(2);
  const idx = Math.abs(n - Math.round(n)) < 0.05 ? String(Math.round(n)) : n.toFixed(1);
  const info = uvLevelInfo(n);
  return { mw: mw, idx: idx, level: info.level, levelKey: info.key };
}
function pmLevelInfo(grade, pm) {
  const gm = { '1': ['좋음', 'good'], '2': ['보통', 'normal'], '3': ['나쁨', 'bad'], '4': ['매우나쁨', 'vbad'] };
  if (gm[String(grade)]) return { level: gm[String(grade)][0], key: gm[String(grade)][1] };
  const n = Number(pm);
  if (!Number.isFinite(n)) return { level: '', key: '' };
  if (n <= 30) return { level: '좋음', key: 'good' };
  if (n <= 80) return { level: '보통', key: 'normal' };
  if (n <= 150) return { level: '나쁨', key: 'bad' };
  return { level: '매우나쁨', key: 'vbad' };
}
function fmtPmFields(pm10, grade) {
  const n = Number(pm10);
  if (!Number.isFinite(n)) return { val: '', level: '', levelKey: '' };
  const info = pmLevelInfo(grade, n);
  return { val: n + ' ㎍/m³', level: info.level, levelKey: info.key };
}
function enrichKmaAir(p) {
  const uv = fmtUvFields(p.kma_uv_index);
  p.kma_uv_mw = uv.mw;
  p.kma_uv_idx = uv.idx;
  p.kma_uv_level = uv.level;
  p.kma_uv_level_key = uv.levelKey;
  const pm = fmtPmFields(p.kma_pm10, p.kma_pm10_grade);
  p.kma_pm_val = pm.val;
  p.kma_pm_level = pm.level;
  p.kma_pm_level_key = pm.levelKey;
}
const kma = flow.get('kmaSnapshot') || global.get('kmaSnapshot') || {};
const phw = flow.get('phwSnapshot') || global.get('phwSnapshot') || {};
const ai = flow.get('cameraAiSnapshot') || global.get('cameraAiSnapshot') || {};
const ghTemp = phw.temp_c != null ? phw.temp_c : phw.temp;
const ghHum = phw.humidity_pct != null ? phw.humidity_pct : phw.humidity;
msg.payload = Object.assign({}, kma, {
  kma_obs_label: fmtKmaObsLabel(kma),
  kma_precip_label: kmaPtyLabel(kma.kma_precip_type ?? kma.kma_pty, kma.kma_precip_1h),
  kma_wind_compass: windCompass(kma.kma_wind_dir),
  kma_precip_display: fmtPrecipDisplay(kma.kma_precip_1h),
  gh_temp: ghTemp,
  gh_humidity: ghHum,
  ph: phw.ph,
  ec: phw.ec,
  temp_c: ghTemp,
  ai_count: ai.count,
  ai_caption: ai.caption
});
enrichKmaAir(msg.payload);
return msg;"""


def _ensure_inject(flows: list, ids: set) -> None:
    if "inj_farm_env_merge" in ids:
        return
    flows.append(
        {
            "id": "inj_farm_env_merge",
            "type": "inject",
            "z": "tab_cronus_dash",
            "name": "farm env merge 15s",
            "props": [{"p": "payload"}],
            "repeat": "15",
            "crontab": "",
            "once": True,
            "onceDelay": 1,
            "topic": "",
            "payload": "",
            "payloadType": "date",
            "x": 140,
            "y": 1260,
            "wires": [["cf_fn_farm_env_merge"]],
        }
    )


def patch_file(path: Path) -> list[str]:
    if not path.is_file():
        return []
    flows = json.loads(path.read_text(encoding="utf-8-sig"))
    ids = {n.get("id") for n in flows if isinstance(n, dict)}
    changed: list[str] = []

    _ensure_inject(flows, ids)

    for n in flows:
        if not isinstance(n, dict):
            continue
        nid = n.get("id")
        if nid == "ui_tpl_farm_env":
            n["format"] = KMA_FMT
            n["width"] = "12"
            n["height"] = 5
            n["group"] = n.get("group") or "ui_grp_farm"
            n["resendOnRefresh"] = True
            changed.append("ui_tpl_farm_env")
        elif nid == "cf_fn_kma_cache":
            n["func"] = FN_KMA_CACHE
            n["wires"] = [["cf_fn_farm_env_merge"]]
            changed.append("cf_fn_kma_cache")
        elif nid == "cf_fn_farm_env_merge":
            n["func"] = FN_FARM_ENV_MERGE
            n["wires"] = [["ui_tpl_farm_env"]]
            changed.append("cf_fn_farm_env_merge")
        elif nid == "mqtt_in_kma_snap":
            n["wires"] = [["cf_fn_kma_cache"]]
            changed.append("mqtt_in_kma_snap")

    if changed:
        path.write_text(
            json.dumps(flows, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
    return [f"{path.name}:{c}" for c in changed]


def main() -> int:
    if not KMA_FMT or "기상청 KMA" not in KMA_FMT:
        raise SystemExit("missing scripts/_farm_env_fmt.txt")
    all_changed: list[str] = []
    for fp in FLOW_FILES:
        all_changed.extend(patch_file(fp))
    if not all_changed:
        print("WARN patch_farm_env_fix: no changes")
        return 1
    print("OK patch_farm_env_fix:", ", ".join(sorted(set(all_changed))[:12]), "...")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
