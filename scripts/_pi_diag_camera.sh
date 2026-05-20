#!/usr/bin/env bash
echo "=== services ==="
systemctl is-active cronusfarm-camera-ai.service 2>/dev/null || echo camera-ai inactive
systemctl is-active cronusfarm-hailo-stream.service 2>/dev/null || echo hailo inactive
echo "=== port 8081 ==="
ss -ltnp 2>/dev/null | grep 8081 || true
echo "=== video devices ==="
ls -la /dev/video* 2>/dev/null || echo no video
echo "=== ustreamer 8080 ==="
curl -sS -o /dev/null -w "http8080:%{http_code}\n" --max-time 3 http://127.0.0.1:8080/stream || echo fail
echo "=== mjpeg 8081 ==="
curl -sS -o /dev/null -w "http8081:%{http_code}\n" --max-time 3 http://127.0.0.1:8081/video_feed || echo fail
echo "=== hailo dir ==="
ls -la ~/CronusFarm/Hailo/ 2>/dev/null | head -8
echo "=== yolo model ==="
ls -la ~/CronusFarm/YOLO/*.pt 2>/dev/null || echo no pt
echo "=== mqtt recent ==="
timeout 3 mosquitto_sub -h 127.0.0.1 -t 'cronusfarm/camera/ai_count' -C 1 -W 2 2>/dev/null || echo no camera/ai_count
timeout 3 mosquitto_sub -h 127.0.0.1 -t 'cronusfarm/hailo/count' -C 1 -W 2 2>/dev/null || echo no hailo/count
echo "=== journal camera-ai (last 15) ==="
journalctl -u cronusfarm-camera-ai.service -n 15 --no-pager 2>/dev/null || true
echo "=== journal hailo (last 15) ==="
journalctl -u cronusfarm-hailo-stream.service -n 15 --no-pager 2>/dev/null || true
