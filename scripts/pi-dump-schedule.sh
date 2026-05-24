#!/usr/bin/env bash
sqlite3 -header -column /home/dooly/.node-red/cronusfarm.sqlite \
  "SELECT channel_key, rule_kind, slot_index,
          printf('%02d:%02d', on_min/60, on_min%60) on_at,
          printf('%02d:%02d', off_min/60, off_min%60) off_at,
          on_sec, off_sec, dow_mask, enabled, updated_at
   FROM schedule_rule WHERE device_id='cronusfarm-01'
   ORDER BY channel_key, slot_index;"
