#!/bin/bash
set -e
echo "nginx user: $(ps aux | grep 'nginx: worker' | head -1)"
ls -ld /home/dooly /home/dooly/CronusFarm /home/dooly/CronusFarm/farm-ui /home/dooly/CronusFarm/farm-ui/dist /home/dooly/CronusFarm/farm-ui/dist/assets
JS=$(grep -oE 'assets/index-[^"]+\.js' /home/dooly/CronusFarm/farm-ui/dist/index.html | head -1)
echo "bundle: $JS"
curl -sI "http://127.0.0.1/farm/ui/" | head -1
curl -sI "http://127.0.0.1/farm/ui/$JS" | head -1
sudo -u www-data test -r "/home/dooly/CronusFarm/farm-ui/dist/index.html" && echo "www-data can read index" || echo "www-data CANNOT read index"
sudo -u www-data test -r "/home/dooly/CronusFarm/farm-ui/dist/${JS#assets/}" 2>/dev/null && echo "www-data can read js" || echo "www-data CANNOT read js"
