#!/bin/bash
# 8080/8081·/dev/video0 점유 정리 후 ustreamer + hailo 재기동 (고아 ustreamer 방지)
set -eu
sudo systemctl stop cronusfarm-camera-ai cronusfarm-ustreamer cronusfarm-hailo-stream 2>/dev/null || true
sudo pkill -f cronusfarm_camera_ai 2>/dev/null || true
sudo pkill -f cronusfarm_hailo_stream 2>/dev/null || true
sudo pkill -x ustreamer 2>/dev/null || true
sudo fuser -k 8080/tcp 8081/tcp 2>/dev/null || true
sudo fuser -k /dev/video0 2>/dev/null || true
sleep 2
sudo systemctl reset-failed cronusfarm-ustreamer cronusfarm-hailo-stream 2>/dev/null || true
sudo systemctl start cronusfarm-ustreamer
sleep 2
sudo systemctl start cronusfarm-hailo-stream
sleep 6
echo "ustreamer=$(systemctl is-active cronusfarm-ustreamer)"
echo "hailo=$(systemctl is-active cronusfarm-hailo-stream)"
sudo systemctl restart cronusfarm-csi-mjpeg 2>/dev/null || true
sleep 2
echo "csi-mjpeg=$(systemctl is-active cronusfarm-csi-mjpeg 2>/dev/null || echo inactive)"
curl -s -o /dev/null -w "8080:%{http_code} 8081:%{http_code} 8082:%{http_code} hailo_ngx:%{http_code} csi_ngx:%{http_code}\n" \
  --max-time 4 http://127.0.0.1:8080/stream \
  http://127.0.0.1:8081/video_feed \
  http://127.0.0.1:8082/video_feed \
  http://127.0.0.1/farm/hailo-mjpeg/video_feed \
  http://127.0.0.1/farm/csi-mjpeg/video_feed
