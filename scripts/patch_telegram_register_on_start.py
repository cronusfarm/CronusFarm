# -*- coding: utf-8 -*-
"""텔레그램 /start·/help 시 SQLite 브리지에 알림 신청(pending) 등록."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REGISTER_BLOCK = r"""
  if (text === '/start' || text === '/help' || low === '시작' || low === '도움' || low === 'help') {
    out1.push(mkSend(cid, WELCOME));
    const dis = (env.get('CRONUSFARM_SQLITE_DISABLE') || '').toString().trim();
    if (dis !== '1' && dis.toLowerCase() !== 'true') {
      try {
        const base = (env.get('CRONUSFARM_SQLITE_BRIDGE_URL') || 'http://127.0.0.1:18766').toString().replace(/\/$/, '');
        const http = require('http');
        const from = m.from || {};
        const dn = [from.first_name, from.last_name].filter(Boolean).join(' ').trim();
        const body = JSON.stringify({
          chat_id: cid,
          display_name: dn || (from.username || cid),
          telegram_username: (from.username || '').toString()
        });
        const u = new URL(base + '/ingest/telegram-register');
        const req = http.request({
          hostname: u.hostname,
          port: u.port || 80,
          path: u.pathname,
          method: 'POST',
          headers: { 'Content-Type': 'application/json; charset=utf-8', 'Content-Length': Buffer.byteLength(body) }
        }, () => {});
        req.on('error', () => {});
        req.write(body);
        req.end();
      } catch (e) { /* 신청 실패해도 환영 메시지는 전송 */ }
    }
    continue;
  }
"""

OLD_START = r"""  if (text === '/start' || text === '/help' || low === '시작' || low === '도움' || low === 'help') {
    out1.push(mkSend(cid, WELCOME));
    continue;
  }"""


def patch_flows(path: Path) -> bool:
    data = json.loads(path.read_text(encoding="utf-8"))
    changed = False
    for node in data if isinstance(data, list) else data.get("nodes", data):
        if not isinstance(node, dict):
            continue
        if node.get("id") != "cf_fn_tg_dispatch" and node.get("name") != "cf_fn_tg_dispatch":
            continue
        func = node.get("func") or ""
        if "/ingest/telegram-register" in func:
            return False
        if OLD_START not in func:
            raise SystemExit(f"{path}: /start 블록 패턴 불일치 — 수동 확인")
        node["func"] = func.replace(OLD_START, REGISTER_BLOCK.strip() + "\n")
        changed = True
    if not changed:
        raise SystemExit(f"{path}: cf_fn_tg_dispatch 없음")
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return True


def main() -> None:
    targets = [
        ROOT / "nodered" / "merged-deploy.json",
        ROOT / "nodered" / "flows_cronusfarm_mqtt.json",
    ]
    for p in targets:
        if p.is_file():
            if patch_flows(p):
                print("patched", p)


if __name__ == "__main__":
    main()
