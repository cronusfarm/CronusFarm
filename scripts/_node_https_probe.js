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
