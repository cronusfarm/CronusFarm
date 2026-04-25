## Raspberry Pi 5: HDMI + SPI TFT(tft35a) + VNC 구성 정리

### 목표
- **HDMI 연결 시**: HDMI 모니터에 **로컬 GUI(LightDM/Xorg)** 출력
- **HDMI 미연결 시**: VNC로 접속해도 **고해상도(예: 1920x1080)** 유지
- **SPI TFT(ILI9486, `dtoverlay=tft35a`)**: **콘솔/상태표시(텍스트)** 용도로 사용

---

### 배경(왜 이런 구성이 필요한가)
- 현재 TFT는 `tft35a`(SPI, ILI9486) + fbtft 계열로 올라오며, 보통 **DRM/KMS “모니터”가 아니라 fbdev 프레임버퍼(`/dev/fbX`)** 로 잡힙니다.
- LightDM/Xorg(=GUI)는 **DRM/KMS HDMI 커넥터(EDID 기반)** 를 우선 사용합니다.
- 그래서 **HDMI가 물리적으로 미연결(disconnected)** 이면 `DISPLAY=:0 xrandr` 기준으로 안전 해상도(예: 800x600)가 잡히고, RealVNC(서비스 모드)가 **그 해상도를 그대로 공유**합니다.
- Debian 13(trixie) + Pi5 환경에서는 구형 userland/DispmanX 기반(`bcm_host.h`) 미러링 도구들이 패키지/호환 문제로 쉽게 막혀서,
  - **SPI TFT에 “GUI 확장 모니터”처럼 출력**하거나
  - **HDMI 화면을 TFT로 안정적으로 미러링**
  하는 구성이 어렵습니다.

결론적으로 **역할 분리(HDMI=GUI / TFT=콘솔 / HDMI 미연결 시 VNC=가상 데스크탑)** 가 가장 안정적입니다.

---

### 최종 구성 요약
- **HDMI GUI**: LightDM + Xorg(:0, 보통 VT7)
- **TFT 콘솔**: `/dev/fb1`에 VT1 매핑 (`con2fbmap`)
- **VNC 고해상도**: RealVNC(X 공유) 대신 **TigerVNC 가상 데스크탑(:1, 5901)** 사용

---

## 1) `/boot/firmware/config.txt` 핵심 설정
아래 키 값들이 활성화되어 있어야 합니다(주석 X).

```ini
dtparam=spi=on
dtoverlay=tft35a:rotate=270

dtoverlay=vc4-kms-v3d
max_framebuffers=2

hdmi_force_hotplug=1
hdmi_group=2
hdmi_mode=82

# SPI와 충돌 가능성이 있어 문제 시 주석 처리
#dtoverlay=uart3
```

### 확인 방법
```bash
grep -nE "dtparam=spi=on|dtoverlay=tft35a|dtoverlay=vc4-kms-v3d|max_framebuffers|hdmi_force_hotplug|hdmi_group|hdmi_mode|dtoverlay=uart3" /boot/firmware/config.txt
```

---

## 2) TFT가 정상으로 올라오는지 확인
```bash
ls -l /dev/fb*
dmesg -T | egrep -i "fb_ili9486|fbtft|ads7846|spi0\." | tail -n 80
```

정상 예시:
- `/dev/fb0`, `/dev/fb1` 생성
- `graphics fb1: fb_ili9486 frame buffer ...` 로그

---

## 3) TFT에 콘솔(tty1) 고정
HDMI 연결 상태에서 TFT가 `fb1`로 잡히는 경우:
```bash
sudo con2fbmap 1 1
sudo chvt 1
```

HDMI GUI로 돌아가기:
```bash
sudo chvt 7
```

### 부팅 시 자동 적용(systemd)
```bash
sudo tee /etc/systemd/system/con2fbmap-vt1.service >/dev/null <<'EOF'
[Unit]
Description=Map VT1 console to TFT framebuffer
After=multi-user.target

[Service]
Type=oneshot
ExecStart=/usr/bin/con2fbmap 1 1
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now con2fbmap-vt1.service
```

> 참고: 부팅/연결 상태에 따라 TFT가 `fb0`로 바뀌면 `ExecStart=/usr/bin/con2fbmap 1 0`로 변경합니다.

---

## 4) HDMI 미연결 시 VNC 해상도 문제와 해결
### 증상
HDMI 없이 부팅 후:
```bash
DISPLAY=:0 xrandr --current
cat /sys/class/drm/card1-HDMI-A-1/status
```
- `current 800 x 600`
- HDMI status가 `disconnected`

이때 RealVNC(서비스 모드)는 X(:0) 화면을 공유하므로 해상도가 낮게 나옵니다.

### 해결: TigerVNC 가상 데스크탑(:1, 5901)
RealVNC 서비스 모드를 끄고, TigerVNC로 **HDMI와 무관한 고정 해상도 가상 데스크탑**을 제공합니다.

#### (1) RealVNC 서비스 모드 중지(충돌 방지)
```bash
sudo systemctl disable --now vncserver-x11-serviced.service
```

#### (2) TigerVNC 설치
```bash
sudo apt update
sudo apt install -y tigervnc-standalone-server tigervnc-common
```

#### (3) TigerVNC 비밀번호 생성
```bash
mkdir -p ~/.vnc
tigervncpasswd
```

#### (4) VNC 세션 시작 스크립트(LXDE)
```bash
tee ~/.vnc/xstartup >/dev/null <<'EOF'
#!/bin/sh
unset SESSION_MANAGER
unset DBUS_SESSION_BUS_ADDRESS
exec startlxde
EOF
chmod +x ~/.vnc/xstartup
```

`startlxde`가 없다면:
```bash
sudo apt install -y lxde-core
```

#### (5) TigerVNC를 외부 접속 가능하게(중요)
TigerVNC가 기본값으로 `127.0.0.1`만 리슨하면 외부 PC에서 접속이 안 됩니다.

```bash
mkdir -p ~/.config/tigervnc
tee ~/.config/tigervnc/config >/dev/null <<'EOF'
localhost no
geometry 1920x1080
depth 24
EOF
```

#### (6) systemd(유저) 서비스 등록
```bash
mkdir -p ~/.config/systemd/user

tee ~/.config/systemd/user/tigervnc.service >/dev/null <<'EOF'
[Unit]
Description=TigerVNC virtual desktop (:1)

[Service]
Type=forking
ExecStart=/usr/bin/tigervncserver :1 -geometry 1920x1080 -depth 24 -localhost no
ExecStop=/usr/bin/tigervncserver -kill :1
Restart=on-failure
RestartSec=2

[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reload
systemctl --user enable --now tigervnc.service
```

#### (7) 포트 확인
```bash
ss -lntp | grep 5901 || true
systemctl --user status tigervnc.service --no-pager
```

#### (8) 접속 방법(PC)
- RealVNC Viewer에서: **`192.168.0.222:5901`**
- 비밀번호: `tigervncpasswd`로 설정한 비밀번호

#### (9) 재부팅 후에도 유저 서비스 자동 기동(linger)
```bash
sudo loginctl enable-linger dooly
```

---

## 5) (선택) TFT에 “서비스 상태/로그” 텍스트 대시보드 출력
TFT는 GUI가 아니라 콘솔이므로, 아래처럼 “서비스 상태 + 최근 로그”를 VT1에 출력하는 형태가 안정적입니다.

### 서비스 유닛명 예시(실제 확인)
```bash
systemctl list-units --type=service | egrep -i "nodered|influxdb|grafana-server|tailscaled"
```

### 대시보드 스크립트/서비스
- 스크립트: `/usr/local/bin/tft-dashboard.sh`
- 서비스: `tft-dashboard.service` (TTY1에 출력)

> 설치/운영 정책에 따라 스크립트 내용은 현장 맞춤(표시 항목/로그 줄 수/갱신 주기)으로 조정합니다.

---

## 트러블슈팅 메모
### A) TFT가 아예 안 뜰 때
- `dtoverlay=uart3` 등으로 **SPI 핀 충돌**이 나면 TFT가 안 올라올 수 있습니다.
- `dmesg`에서 `spi`/`pinctrl` 충돌 로그를 확인하고 충돌 overlay를 주석 처리합니다.

### B) “HDMI GUI가 안 나오는 것처럼 보임”
- 실제로는 GUI가 VT7에 있고, TFT 콘솔이 VT1이라 **현재 활성 VT가 1이면 HDMI가 ‘빈 것처럼’ 보일 수** 있습니다.
- 해결: `sudo chvt 7`

### C) VNC가 빈 화면
- `~/.vnc/xstartup`에서 데스크탑 세션을 실행하지 않으면 빈 화면이 정상입니다.
- `startlxde`(또는 사용 DE) 실행을 `xstartup`에 넣습니다.

