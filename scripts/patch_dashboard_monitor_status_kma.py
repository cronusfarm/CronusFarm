"""
모니터: KMA 스냅샷 캐시/표시만 보정.

주의:
- 이 스크립트는 KMA 관련 노드만 수정합니다.
- `fn_calc_online`/Arduino 상태줄(ui_tpl_conn_line 등)에는 손대지 않습니다.
  (다른 패치가 outputs=4/wires=4 를 전제로 하므로, 여기서 덮어쓰면 전체가 offline처럼 보이는 고질병이 재발합니다.)
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
p = ROOT / "nodered" / "flows_cronusfarm_dashboard.json"

FN_KMA = """function fmtKmaObsLabel(o) {
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
let p = msg.payload;
if (typeof p === 'string') {
  try { p = JSON.parse(p); } catch (e) { return msg; }
}
if (p && typeof p === 'object') {
  p.kma_obs_label = fmtKmaObsLabel(p);
  flow.set('kmaSnapshot', p);
  global.set('kmaSnapshot', p);
  flow.set('kmaSnapshotTs', Date.now());
  global.set('kmaSnapshotTs', Date.now());
}
msg.payload = p;
return msg;"""


def main() -> None:
    data = json.loads(p.read_text(encoding="utf-8-sig"))
    for n in data:
        if not isinstance(n, dict):
            continue
        nid = n.get("id")
        if nid == "cf_fn_kma_cache":
            n["func"] = FN_KMA
        elif nid == "ui_tpl_farm_env":
            fmt = n.get("format") or ""
            # 다른 패치가 이미 kma_obs_label을 넣었을 수 있으므로, 있으면 그대로 통과합니다.
            if "kma_obs_label" in fmt:
                continue
            old_sub = '<span class="cf-fe-box-sub">{{msg.payload.base_date ? (\'관측 \' + msg.payload.base_date + \' \' + (msg.payload.base_time||\'\') + \' KST\') : \'\'}}</span>'
            new_sub = '<span class="cf-fe-box-sub">{{msg.payload.kma_obs_label ? (\'관측 \' + msg.payload.kma_obs_label) : \'\'}}</span>'
            if old_sub in fmt:
                n["format"] = fmt.replace(old_sub, new_sub)

    p.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print("OK patch_dashboard_monitor_status_kma (KMA only)")


if __name__ == "__main__":
    main()
