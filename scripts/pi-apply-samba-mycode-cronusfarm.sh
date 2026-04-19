#!/bin/bash
# ida(Pi)에서 실행: [MyCode] 공유 path 를 /home/dooly/CronusFarm 으로 변경 후 Samba 재시작
set -eu
CONF="/etc/samba/smb.conf"
NEW_PATH="/home/dooly/CronusFarm"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "root 로 실행하세요: sudo bash $0" >&2
  exit 1
fi

test -f "$CONF"

BK="${CONF}.bak.$(date +%Y%m%d%H%M%S)"
cp -a "$CONF" "$BK"
echo "백업: $BK"

TMP="$(mktemp)"
chmod 600 "$TMP"

awk -v newpath="$NEW_PATH" '
  /^\[MyCode\]/ { in_mycode=1; print; next }
  in_mycode && /^[[:space:]]*path[[:space:]]*=/ {
    sub(/^[[:space:]]*path[[:space:]]*=.*/, "   path = " newpath)
    print
    next
  }
  in_mycode && /^\[/ { in_mycode=0 }
  { print }
' "$CONF" > "$TMP"

if ! testparm -s "$TMP" >/dev/null 2>&1; then
  echo "testparm 검증 실패. 백업으로 복구하지 않았으니 $TMP 를 확인하세요." >&2
  exit 1
fi

install -m 0644 -o root -g root "$TMP" "$CONF"
rm -f "$TMP"

systemctl restart smbd 2>/dev/null || true
systemctl restart nmbd 2>/dev/null || true

echo "완료: [MyCode] path -> $NEW_PATH , smbd/nmbd 재시작 시도함."
grep -A6 '^\[MyCode\]' "$CONF" || true
