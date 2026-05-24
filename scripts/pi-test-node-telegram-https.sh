#!/usr/bin/env bash
set -uo pipefail
run_one() {
  local label="$1"
  shift
  echo "=== $label ==="
  "$@" /home/dooly/CronusFarm/scripts/_node_https_probe.js
}
cat > /home/dooly/CronusFarm/scripts/_node_https_probe.js <<'JS'
const https = require('https');
const t = setTimeout(() => { console.log('TIMEOUT'); process.exit(2); }, 12000);
https.get('https://api.telegram.org', (r) => {
  console.log('ok', r.statusCode);
  clearTimeout(t);
  process.exit(0);
}).on('error', (e) => {
  console.log('err', e.code || '', e.message);
  clearTimeout(t);
  process.exit(1);
});
JS
run_one "default node" node
run_one "ipv4first" env NODE_OPTIONS=--dns-result-order=ipv4first node
