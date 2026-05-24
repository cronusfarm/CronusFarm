#!/usr/bin/env bash
set -uo pipefail
cat > /tmp/_node_probe.js <<'JS'
const https = require('https');
const url = process.argv[2] || 'https://api.telegram.org';
const t = setTimeout(() => { console.log('TIMEOUT', url); process.exit(2); }, 15000);
https.get(url, (r) => {
  console.log('OK', url, r.statusCode);
  clearTimeout(t);
  process.exit(0);
}).on('error', (e) => {
  console.log('ERR', url, e.code || '', e.message);
  clearTimeout(t);
  process.exit(1);
});
JS
for u in 'https://www.google.com' 'https://api.telegram.org'; do
  echo "--- $u ---"
  node /tmp/_node_probe.js "$u" || true
  env NODE_OPTIONS=--dns-result-order=ipv4first node /tmp/_node_probe.js "$u" || true
done
curl -s -m 8 -o /dev/null -w "curl telegram %{http_code}\n" https://api.telegram.org/
