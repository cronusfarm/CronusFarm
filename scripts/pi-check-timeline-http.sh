#!/usr/bin/env bash
curl -s -o /dev/null -w "batch_local=%{http_code}\n" "http://127.0.0.1:18766/api/channel/timeline/batch?device_id=cronusfarm-01&channels=led_a1&hours=48"
curl -s -o /dev/null -w "batch_farm=%{http_code}\n" "http://127.0.0.1/farm/cronusfarm-sqlite/api/channel/timeline/batch?device_id=cronusfarm-01&channels=led_a1&hours=48" 2>/dev/null || echo "batch_farm=fail"
