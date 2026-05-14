#!/usr/bin/env bash
#
# Pi에서 /ui(nginx :1880 / :80 → NR 업스트림) 동작 점검
#
# 이 파일은 PATH에 없음 — 아래처럼 전체 경로로 실행:
#   bash ~/CronusFarm/scripts/pi-diagnose-ui.sh
#   bash "$HOME/CronusFarm/scripts/pi-diagnose-ui.sh"
#
# "그런 파일이나 디렉터리가 없습니다" 이면:
#   1) 레포 루트에서: bash scripts/pi-install-diagnose-to-home.sh
#   2) 또는 git pull 후 다시 (스크립트가 원격 저장소에 있어야 함)
#   3) 개발 PC: powershell -File scripts/run-pi-diagnose-ui.ps1  → Pi /tmp 로 복사 후 실행
#
# 전역 명령처럼 쓰려면(한 번):
#   chmod +x ~/CronusFarm/scripts/pi-diagnose-ui.sh
#   sudo ln -sf "$HOME/CronusFarm/scripts/pi-diagnose-ui.sh" /usr/local/bin/pi-diagnose-ui
#   pi-diagnose-ui
#
set -u
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:${PATH:-}"

UP="${CRONUSFARM_NR_UPSTREAM_PORT:-1882}"

echo "=== 1) nginx ==="
if command -v nginx >/dev/null 2>&1 || [[ -x /usr/sbin/nginx ]]; then
  systemctl is-active nginx 2>/dev/null && echo "nginx: active" || echo "nginx: NOT active"
else
  echo "nginx: not installed"
fi

echo "=== 2) :1880 Server: (nginx 이면 프록시 전제) ==="
curl -sSI --max-time 3 "http://127.0.0.1:1880/" 2>/dev/null | grep -i '^Server:' | tr -d '\r' || echo "(no response)"

echo "=== 3) listen :1880 :${UP} ==="
ss -tlnp 2>/dev/null | grep -E ":1880|:${UP}" || echo "(ss empty or no match)"

echo "=== 4) HTTP 코드 ==="
for url in "http://127.0.0.1:1880/ui/" "http://127.0.0.1:${UP}/ui/"; do
  code="$(curl -sS -o /dev/null -w "%{http_code}" --max-time 5 "$url" 2>/dev/null || echo 000)"
  echo "  GET $url -> $code"
done

echo "=== 5) nodered.service ==="
systemctl is-active nodered.service 2>/dev/null && echo "nodered: active" || echo "nodered: NOT active"
systemctl show nodered.service -p Environment --no-pager 2>/dev/null | tr ' ' '\n' | grep -E '^PORT=|^Environment=' || true

echo "=== 6) nodered 최근 로그 (40줄) ==="
journalctl -u nodered.service -n 40 --no-pager 2>/dev/null || echo "(journalctl failed)"

echo "=== 요약 ==="
echo "1880이 nginx이고 /ui 가 502면: NR이 :${UP} 에서 떠 있어야 함."
echo "  sudo bash ~/CronusFarm/scripts/pi-nodered-ensure-upstream-for-nginx.sh"
echo "  sudo nginx -t && sudo systemctl reload nginx"
echo "직접 :${UP}/ui 도 실패하면: 플로우 오류·NR 기동 실패 — 위 로그 확인 후 Deploy/플로우 롤백."

# --- nginx:1880 인데 NR 업스트림(:1882) 미청취 → 비대화 sudo 가능하면 자동 보정 ---
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENSURE="${SCRIPT_DIR}/pi-nodered-ensure-upstream-for-nginx.sh"
is_nginx_1880() {
  curl -sSI --max-time 2 "http://127.0.0.1:1880/" 2>/dev/null | grep -i '^Server:' | grep -qi nginx
}
upstream_listening() {
  ss -tlnp 2>/dev/null | grep -E ":${UP}" | grep -q .
}
code80() { curl -sS -o /dev/null -w "%{http_code}" --max-time 5 "http://127.0.0.1:1880/ui/" 2>/dev/null || echo 000; }
codeUp() { curl -sS -o /dev/null -w "%{http_code}" --max-time 5 "http://127.0.0.1:${UP}/ui/" 2>/dev/null || echo 000; }

echo "=== 7) 자동 조치(비밀번호 없는 sudo 가능할 때만) ==="
if is_nginx_1880 && ! upstream_listening && [[ -f "$ENSURE" ]]; then
  if sudo -n true 2>/dev/null; then
    echo "조건: nginx@1880 + :${UP} 미청취 → $ENSURE 실행"
    sudo -n bash "$ENSURE" || true
    sleep 2
    echo "  재확인 GET :1880/ui/ -> $(code80)"
  else
    echo "sudo -n 불가 — Pi에서 직접: sudo bash $ENSURE"
  fi
else
  if is_nginx_1880 && upstream_listening; then
    echo "(자동 보정 불필요: nginx@1880 + :${UP} Node-RED 청취 중)"
  elif ! is_nginx_1880; then
    echo "(자동 보정 스킵: :1880이 nginx가 아님 — 프록시 구성이 다를 수 있음)"
  elif [[ ! -f "$ENSURE" ]]; then
    echo "(자동 보정 스킵: $ENSURE 없음)"
  else
    echo "(자동 보정 스킵: 기타)"
  fi
fi

c_up="$(codeUp)"
if [[ "$c_up" == "000" || "$c_up" == "502" || "$c_up" == "503" ]]; then
  if sudo -n true 2>/dev/null; then
    echo ":${UP}/ui 가 $c_up → nodered 재시작 시도"
    sudo -n systemctl restart nodered.service || true
    sleep 4
    echo "  재확인 GET :${UP}/ui/ -> $(codeUp)  GET :1880/ui/ -> $(code80)"
  fi
fi

if is_nginx_1880 && sudo -n true 2>/dev/null; then
  c80="$(code80)"
  if [[ "$c80" == "502" ]]; then
    echo "여전히 502 → nginx reload"
    sudo -n nginx -t 2>/dev/null && sudo -n systemctl reload nginx 2>/dev/null || true
    sleep 1
    echo "  재확인 GET :1880/ui/ -> $(code80)"
  fi
fi
