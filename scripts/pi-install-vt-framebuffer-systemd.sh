#!/bin/bash
# ida(Pi)에서 실행: VT7→fb0, VT1→fb1 복구 + systemd 유닛 설치(재부팅 후 유지) + LightDM 재시작
# 사전: 저장소에서 복사 후 sudo bash pi-install-vt-framebuffer-systemd.sh
set -euo pipefail
if [[ $EUID -ne 0 ]]; then exec sudo bash "$0" "$@"; fi

con2fbmap 7 0
con2fbmap 1 1

install -d -m0755 /etc/systemd/system

cat >/etc/systemd/system/vt-framebuffer-map.service <<'UNIT1'
# SPI TFT(fb1) ↔ VT1, HDMI/KMS(fb0) ↔ VT7
[Unit]
Description=Map VT1 to SPI TFT (fb1), VT7 to HDMI/KMS (fb0)
DefaultDependencies=yes
After=multi-user.target
Before=display-manager.service

[Service]
Type=oneshot
ExecStart=/bin/bash -c '/usr/bin/con2fbmap 7 0 && /usr/bin/con2fbmap 1 1'
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
UNIT1

cat >/etc/systemd/system/vt-framebuffer-map-late.service <<'UNIT2'
[Unit]
Description=Re-map VT7 to HDMI (fb0) after display manager
After=display-manager.service
PartOf=graphical.target

[Service]
Type=oneshot
ExecStart=/bin/bash -c 'sleep 4; /usr/bin/con2fbmap 7 0 && /usr/bin/con2fbmap 1 1'
RemainAfterExit=yes

[Install]
WantedBy=graphical.target
UNIT2

systemctl daemon-reload
systemctl enable vt-framebuffer-map.service vt-framebuffer-map-late.service

# 즉시 보정 후 LightDM 재시작 → labwc가 VT를 다시 건드리면 5초 뒤 한 번 더
systemctl start vt-framebuffer-map.service
systemctl restart lightdm.service
sleep 5
con2fbmap 7 0
con2fbmap 1 1
systemctl start vt-framebuffer-map-late.service || true

echo "--- con2fbmap 확인 (VT7=fb0 이어야 VNC/회색 빈 화면 해소) ---"
con2fbmap 1
con2fbmap 7
echo "tft-dashboard: journalctl 비어 있음=정상(TTY로만 출력). TFT 보려면: sudo chvt 1"
