# -*- coding: utf-8 -*-
"""모니터 Farm 환경: KMA 카드에 강수·풍향(16방) 등 추가 표시."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FMT_PATH = ROOT / "scripts" / "_farm_env_fmt.txt"

FLOW_FILES = [
    ROOT / "nodered" / "flows_cronusfarm_dashboard.json",
    ROOT / "nodered" / "flows_cronusfarm_mqtt.json",
    ROOT / "nodered" / "flows_pi_editor_latest.json",
    ROOT / "nodered" / "merged-deploy.json",
    ROOT / "nodered" / "CronusFarm_NodeRED_flow.json",
]

OLD_KV = (
    '<div class="cf-fe-kv">\n'
    '          <span class="k">기온</span><span class="v">{{(msg.payload.kma_temp != null && msg.payload.kma_temp !== \'\') ? (msg.payload.kma_temp + \' °C\') : \'—\'}}</span>\n'
    '          <span class="k">습도</span><span class="v">{{(msg.payload.kma_humidity != null && msg.payload.kma_humidity !== \'\') ? (msg.payload.kma_humidity + \' %\') : \'—\'}}</span>\n'
    '          <span class="k">풍향</span><span class="v">{{(msg.payload.kma_wind_dir != null && msg.payload.kma_wind_dir !== \'\') ? (msg.payload.kma_wind_dir + \' °\') : \'—\'}}</span>\n'
    '          <span class="k">풍속</span><span class="v">{{(msg.payload.kma_wind_speed != null && msg.payload.kma_wind_speed !== \'\') ? (msg.payload.kma_wind_speed + \' m/s\') : \'—\'}}</span>\n'
    '        </div>'
)

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
const kma = flow.get('kmaSnapshot') || global.get('kmaSnapshot') || {};
const phw = flow.get('phwSnapshot') || global.get('phwSnapshot') || {};
const ai = flow.get('cameraAiSnapshot') || global.get('cameraAiSnapshot') || {};
msg.payload = Object.assign({}, kma, {
  kma_obs_label: fmtKmaObsLabel(kma),
  kma_precip_label: kmaPtyLabel(kma.kma_precip_type ?? kma.kma_pty, kma.kma_precip_1h),
  kma_wind_compass: windCompass(kma.kma_wind_dir),
  ph: phw.ph,
  ec: phw.ec,
  temp_c: phw.temp_c,
  ai_count: ai.count,
  ai_caption: ai.caption
});
return msg;"""

FN_KMA_CACHE = r"""function fmtKmaObsLabel(o) {
  if (!o || typeof o !== 'object') return '';
  const d = String(o.base_date || '').trim();
  let t = String(o.base_time != null ? o.base_time : '').trim();
  if (d.length < 8) return '';
  if (!t) t = '0000';
  t = t.padStart(4, '0');
  const y = d.slice(0, 4);
  const mo = d.slice(4, 6);
  const da = d.slice(6, 8);
  const hh = t.slice(0, 2);
  const mm = t.slice(2, 4);
  return y + '.' + mo + '.' + da + ' ' + hh + ':' + mm + ' KST';
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
let p = msg.payload;
if (typeof p === 'string') {
  try { p = JSON.parse(p); } catch (e) { return msg; }
}
if (p && typeof p === 'object') {
  p.kma_obs_label = fmtKmaObsLabel(p);
  p.kma_precip_label = kmaPtyLabel(p.kma_precip_type ?? p.kma_pty, p.kma_precip_1h);
  p.kma_wind_compass = windCompass(p.kma_wind_dir);
  flow.set('kmaSnapshot', p);
  global.set('kmaSnapshot', p);
  flow.set('kmaSnapshotTs', Date.now());
  global.set('kmaSnapshotTs', Date.now());
}
msg.payload = p;
return msg;"""


def load_new_fmt() -> str:
    return FMT_PATH.read_text(encoding="utf-8")


def patch_flow_file(path: Path, new_fmt: str) -> list[str]:
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    changed: list[str] = []
    for n in data:
        if not isinstance(n, dict):
            continue
        nid = n.get("id")
        if nid == "ui_tpl_farm_env":
            old = n.get("format") or ""
            if OLD_KV in old:
                n["format"] = old.replace(OLD_KV, _new_kv_block())
            elif "kma_precip_label" in old:
                pass
            else:
                # 전체 교체(백업 형식 상이)
                start = old.find('<div class="cf-fe cf-fe-wide">')
                if start >= 0:
                    end = old.find("</div>\n\n  <style>", start)
                    if end < 0:
                        end = old.find('  <style>', start)
                    if end >= 0:
                        n["format"] = new_fmt.strip() + old[end:]
                    else:
                        n["format"] = new_fmt.strip()
                else:
                    n["format"] = new_fmt.strip()
            changed.append(f"{path.name}:ui_tpl_farm_env")
        elif nid == "cf_fn_farm_env_merge":
            n["func"] = FN_FARM_ENV_MERGE
            changed.append(f"{path.name}:cf_fn_farm_env_merge")
        elif nid in ("cf_fn_kma_cache", "fn_kma_snap_cache"):
            n["func"] = FN_KMA_CACHE
            changed.append(f"{path.name}:{nid}")
    if changed:
        path.write_text(
            json.dumps(data, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
    return changed


def _new_kv_block() -> str:
    return (
        '<div class="cf-fe-kv">\n'
        '          <span class="k">기온</span><span class="v">{{(msg.payload.kma_temp != null && msg.payload.kma_temp !== \'\') ? (msg.payload.kma_temp + \' °C\') : \'—\'}}</span>\n'
        '          <span class="k">습도</span><span class="v">{{(msg.payload.kma_humidity != null && msg.payload.kma_humidity !== \'\') ? (msg.payload.kma_humidity + \' %\') : \'—\'}}</span>\n'
        '          <span class="k">강수형태</span><span class="v">{{msg.payload.kma_precip_label || \'—\'}}</span>\n'
        '          <span class="k">1h 강수</span><span class="v">{{(msg.payload.kma_precip_1h != null && msg.payload.kma_precip_1h !== \'\') ? (msg.payload.kma_precip_1h + \' mm\') : \'—\'}}</span>\n'
        '          <span class="k">풍향</span><span class="v">{{msg.payload.kma_wind_compass ? (msg.payload.kma_wind_compass + \' · \' + msg.payload.kma_wind_dir + \'°\') : ((msg.payload.kma_wind_dir != null && msg.payload.kma_wind_dir !== \'\') ? (msg.payload.kma_wind_dir + \' °\') : \'—\')}}</span>\n'
        '          <span class="k">풍속</span><span class="v">{{(msg.payload.kma_wind_speed != null && msg.payload.kma_wind_speed !== \'\') ? (msg.payload.kma_wind_speed + \' m/s\') : \'—\'}}</span>\n'
        '        </div>'
    )


def main() -> None:
    new_fmt = load_new_fmt()
    # _farm_env_fmt.txt KMA kv 동기화
    if OLD_KV.split("\n")[1].strip() in new_fmt:
        updated = new_fmt.replace(OLD_KV, _new_kv_block())
        FMT_PATH.write_text(updated, encoding="utf-8")

    all_changed: list[str] = []
    for fp in FLOW_FILES:
        all_changed.extend(patch_flow_file(fp, new_fmt))
    if not all_changed:
        raise SystemExit("no nodes patched — ui_tpl_farm_env id 확인")
    print("OK:", ", ".join(all_changed))


if __name__ == "__main__":
    main()
