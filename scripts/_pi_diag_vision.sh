#!/usr/bin/env bash
set -euo pipefail
echo "=== env ==="
grep -E '^CRONUSFARM_(VISION|GEMINI|OLLAMA)' /etc/cronusfarm/nodered-telegram.env 2>/dev/null | sed 's/=.*/=***/' || true
echo "=== ollama models ==="
curl -sS http://127.0.0.1:11434/api/tags 2>/dev/null | python3 -c "import sys,json;d=json.load(sys.stdin);print([m.get('name') for m in d.get('models',[])])" || echo "ollama down"
echo "=== recent vision tmp ==="
ls -lt /tmp/cf_tg_vision 2>/dev/null | head -3 || echo "no tmp"
