#!/bin/bash
# pi-initial-setup.sh
# ida (Raspberry Pi) 초기 환경 구성
# - SSH 서버, Samba, Node-RED, Mosquitto, arduino-cli 설치
# - CronusFarm 디렉터리 구조 생성
# 최초 1회 Pi에서 직접 실행: bash pi-initial-setup.sh

set -euo pipefail

CRONUSFARM_ROOT="/home/dooly/CronusFarm"
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
log()  { echo -e "${GREEN}[setup]${NC} $*"; }
warn() { echo -e "${YELLOW}[warn]${NC} $*"; }
err()  { echo -e "${RED}[error]${NC} $*"; exit 1; }

[[ $EUID -ne 0 ]] && err "sudo 로 실행하세요: sudo bash $0"

log "시스템 업데이트..."
apt-get update -qq && apt-get upgrade -y -qq

log "SSH 서버 설치..."
apt-get install -y openssh-server
systemctl enable --now ssh
log "SSH 활성화 완료 (포트 22)"

log "Samba 설치..."
apt-get install -y samba samba-common-bin
SAMBA_CONF="/etc/samba/smb.conf"
if ! grep -q "\[dooly\]" "$SAMBA_CONF"; then
    cat >> "$SAMBA_CONF" << 'SAMBA_EOF'

[dooly]
   comment = CronusFarm Workspace
   path = /home/dooly
   browseable = yes
   read only = no
   create mask = 0664
   directory mask = 0775
   valid users = dooly
   force user = dooly
SAMBA_EOF
    systemctl restart smbd nmbd
    log "Samba 공유 설정 완료 (\\\\ida\\dooly)"
    warn "Samba 비밀번호 설정 필요: sudo smbpasswd -a dooly"
else
    warn "Samba 공유 이미 설정됨"
fi

log "Mosquitto 설치..."
apt-get install -y mosquitto mosquitto-clients
MOSQUITTO_CONF="/etc/mosquitto/conf.d/cronusfarm.conf"
if [[ ! -f "$MOSQUITTO_CONF" ]]; then
    cat > "$MOSQUITTO_CONF" << 'MQTT_EOF'
listener 1883
allow_anonymous true
log_dest file /var/log/mosquitto/mosquitto.log
log_type error
log_type warning
log_type notice
MQTT_EOF
    systemctl enable --now mosquitto
    log "Mosquitto 설치 완료 (포트 1883)"
else
    warn "Mosquitto 설정 이미 존재"
fi

log "Node-RED 설치..."
if ! command -v node-red &>/dev/null; then
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
    apt-get install -y nodejs
    sudo -u dooly bash -c "bash <(curl -sL https://raw.githubusercontent.com/node-red/linux-installers/master/deb/update-nodejs-and-nodered) --confirm-install --confirm-pi"
    systemctl enable --now nodered
    log "Node-RED 설치 완료 (포트 1880)"
else
    warn "Node-RED 이미 설치됨"
    systemctl enable --now nodered
fi

log "node-red-contrib-influxdb 설치..."
NR_DIR="/home/dooly/.node-red"
sudo -u dooly bash -c "cd '$NR_DIR' && npm install --save node-red-contrib-influxdb 2>/dev/null" \
    && log "node-red-contrib-influxdb 설치 완료" \
    || warn "설치 실패 - Node-RED 재시작 후 재시도"

log "arduino-cli 설치..."
if ! command -v arduino-cli &>/dev/null; then
    curl -fsSL https://raw.githubusercontent.com/arduino/arduino-cli/master/install.sh \
        | BINDIR=/usr/local/bin sh
    log "arduino-cli 설치 완료"
else
    warn "arduino-cli 이미 설치됨"
fi
usermod -aG dialout dooly
log "dooly -> dialout 그룹 추가 완료"

log "CronusFarm 디렉터리 구조 생성..."
sudo -u dooly mkdir -p \
    "$CRONUSFARM_ROOT/arduino/CronusFarm" \
    "$CRONUSFARM_ROOT/arduino/CronusFarmPanel" \
    "$CRONUSFARM_ROOT/nodered" \
    "$CRONUSFARM_ROOT/grafana" \
    "$CRONUSFARM_ROOT/scripts"

if command -v ufw &>/dev/null; then
    ufw allow 22/tcp   comment "SSH"      2>/dev/null || true
    ufw allow 1880/tcp comment "Node-RED" 2>/dev/null || true
    ufw allow 1883/tcp comment "MQTT"     2>/dev/null || true
    ufw allow 3000/tcp comment "Grafana"  2>/dev/null || true
    ufw allow 8086/tcp comment "InfluxDB" 2>/dev/null || true
    ufw allow 445/tcp  comment "Samba"    2>/dev/null || true
    ufw allow 137/udp  comment "Samba-NetBIOS" 2>/dev/null || true
fi

PI_IP=$(hostname -I | awk '{print $1}')
echo ""
echo -e "${GREEN}================================================${NC}"
echo -e "${GREEN}  ida 초기 설정 완료!${NC}"
echo -e "${GREEN}================================================${NC}"
echo -e "  SSH      : ssh dooly@${PI_IP}"
echo -e "  Samba    : \\\\\\\\${PI_IP}\\\\dooly"
echo -e "  Node-RED : http://${PI_IP}:1880"
echo -e "  MQTT     : ${PI_IP}:1883"
echo ""
echo -e "${YELLOW}다음 작업 필요:${NC}"
echo -e "  1. Samba 비밀번호: sudo smbpasswd -a dooly"
echo -e "  2. arduino-cli 보드 설치: bash $CRONUSFARM_ROOT/scripts/pi-setup-arduino-cli.sh"
echo -e "  3. Grafana 스택 설치: bash $CRONUSFARM_ROOT/scripts/pi-install-grafana-stack.sh"
echo -e "  4. 재로그인 (dialout 그룹 반영)"