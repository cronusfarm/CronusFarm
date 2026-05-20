#!/bin/bash
# pi-influx-seed-mock-april.sh
# InfluxDB(1.x) cronusfarm DB에 4월 한달치 랜덤 테스트 데이터 주입

set -euo pipefail

DB="${DB:-cronusfarm}"
USER="${USER:-cronusfarm}"
PASS="${PASS:-cronusfarm1234}"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8086}"

# 4월 범위(로컬 타임 기준). 필요하면 YEAR만 바꿔서 재사용 가능.
YEAR="${YEAR:-2026}"
START="${START:-${YEAR}-04-01 00:00:00}"
END="${END:-${YEAR}-05-01 00:00:00}"

# 주입 간격(초). 3600=1시간
STEP_SEC="${STEP_SEC:-3600}"

write_lp() {
  local lp="$1"
  # HTTP 4xx/5xx는 실패로 처리해야 조용히 누락되지 않음
  if ! curl -fsS -XPOST "http://${HOST}:${PORT}/write?db=${DB}&u=${USER}&p=${PASS}&precision=s" \
    --data-binary "${lp}" >/dev/null; then
    echo "[ERROR] Influx write 실패(일부 페이로드 미리보기)" >&2
    echo "-----" >&2
    # 앞부분 몇 줄만 출력(너무 길면 터미널이 터짐)
    printf '%s' "${lp}" | head -n 20 >&2
    echo "-----" >&2
    return 1
  fi
}

randf() {
  local min="$1"; local max="$2"
  awk -v min="$min" -v max="$max" 'BEGIN{srand(); print min + (max-min)*rand()}'
}

clampf() {
  local v="$1"; local min="$2"; local max="$3"
  awk -v v="$v" -v min="$min" -v max="$max" 'BEGIN{ if(v<min)v=min; if(v>max)v=max; print v }'
}

to_epoch() {
  # Debian date 기준
  date -d "$1" +%s
}

log() { echo "[INFO] $*"; }

start_ts="$(to_epoch "$START")"
end_ts="$(to_epoch "$END")"

log "InfluxDB 랜덤 데이터 주입 시작"
log "- DB=${DB}, HOST=${HOST}:${PORT}"
log "- 기간: ${START} ~ ${END} (epoch ${start_ts}..${end_ts})"
log "- 간격: ${STEP_SEC}s"

# 센서 키( Grafana 변수: SHOW TAG VALUES FROM "sensor" WITH KEY="key" )
sensor_keys=("temp" "hum" "ec" "ph" "tds" "orp")

# 액추에이터 키( Grafana 패널: key =~ /^(led|pump)_/ )
act_keys=("led_a1" "led_a2" "led_b1" "pump_a1" "pump_a2" "pump_b1" "pump_b2")

# 초기값(부드러운 변화 만들기)
temp=22.0
hum=60.0
ec=1.4
ph=6.0
tds=800.0
orp=300.0

lp_buf=""
count=0

append_line() {
  # command substitution의 개행 제거 문제를 피하려고, 라인 단위로 직접 누적
  local line="$1"
  printf -v lp_buf '%s%s\n' "$lp_buf" "$line"
}

flush() {
  if [ -n "${lp_buf}" ]; then
    write_lp "${lp_buf}"
    lp_buf=""
  fi
}

for ((ts=start_ts; ts<end_ts; ts+=STEP_SEC)); do
  # 일주기 변동(대충) + 랜덤 노이즈
  # (ts 기준 시각)
  hour="$(date -d "@${ts}" +%H)"
  day_sine="$(awk -v h="$hour" 'BEGIN{pi=3.1415926535; print sin((h/24.0)*2*pi)}')"

  temp="$(awk -v v="$temp" -v s="$day_sine" 'BEGIN{srand(); print v + 0.15*s + (rand()-0.5)*0.35 }')"
  hum="$(awk -v v="$hum" -v s="$day_sine" 'BEGIN{srand(); print v - 0.3*s + (rand()-0.5)*1.2 }')"
  ec="$(awk -v v="$ec" 'BEGIN{srand(); print v + (rand()-0.5)*0.06 }')"
  ph="$(awk -v v="$ph" 'BEGIN{srand(); print v + (rand()-0.5)*0.03 }')"
  tds="$(awk -v v="$tds" 'BEGIN{srand(); print v + (rand()-0.5)*25 }')"
  orp="$(awk -v v="$orp" 'BEGIN{srand(); print v + (rand()-0.5)*8 }')"

  temp="$(clampf "$temp" 18 28)"
  hum="$(clampf "$hum" 40 85)"
  ec="$(clampf "$ec" 0.6 2.6)"
  ph="$(clampf "$ph" 5.4 6.8)"
  tds="$(clampf "$tds" 350 1400)"
  orp="$(clampf "$orp" 180 420)"

  # 센서 쓰기 (measurement=sensor, tag=key, field=value)
  append_line "sensor,key=temp value=${temp} ${ts}"
  append_line "sensor,key=hum value=${hum} ${ts}"
  append_line "sensor,key=ec value=${ec} ${ts}"
  append_line "sensor,key=ph value=${ph} ${ts}"
  append_line "sensor,key=tds value=${tds} ${ts}"
  append_line "sensor,key=orp value=${orp} ${ts}"

  # 액추에이터 상태는 “가끔” 바뀌는 형태로 (0/1)
  # 펌프는 주기적으로, LED는 비교적 고정
  # (STEP_SEC=3600이면 6시간 주기로 토글)
  if (( ((ts-start_ts) % (6*3600)) == 0 )); then
    pump_a1=$((RANDOM % 2))
    pump_a2=$((RANDOM % 2))
    pump_b1=$((RANDOM % 2))
    pump_b2=$((RANDOM % 2))
  fi
  if (( ((ts-start_ts) % (24*3600)) == 0 )); then
    led_a1=$((RANDOM % 2))
    led_a2=$((RANDOM % 2))
    led_b1=$((RANDOM % 2))
  fi

  append_line "actuator,key=led_a1 value=${led_a1:-1} ${ts}"
  append_line "actuator,key=led_a2 value=${led_a2:-1} ${ts}"
  append_line "actuator,key=led_b1 value=${led_b1:-1} ${ts}"
  append_line "actuator,key=pump_a1 value=${pump_a1:-0} ${ts}"
  append_line "actuator,key=pump_a2 value=${pump_a2:-0} ${ts}"
  append_line "actuator,key=pump_b1 value=${pump_b1:-0} ${ts}"
  append_line "actuator,key=pump_b2 value=${pump_b2:-0} ${ts}"

  count=$((count+1))
  # 너무 큰 버퍼 방지(대략 12시간마다 flush)
  if (( (count % 12) == 0 )); then
    flush
  fi
done

flush
log "완료: ${YEAR}-04 랜덤 데이터 주입"

