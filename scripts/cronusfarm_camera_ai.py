#!/usr/bin/env python3
import json
import os
import re
import sys
import threading
import time
from collections import Counter
from pathlib import Path

import cv2

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))
from cronusfarm_crop_caption import (  # noqa: E402
    CropDet,
    analyze_crop_detections,
    draw_subtitle_on_bgr,
    ultralytics_boxes_to_crop_dets,
)
import numpy as np
import paho.mqtt.client as mqtt
from flask import Flask, Response
from ultralytics import YOLO

# 설정
MQTT_HOST = "127.0.0.1"
MQTT_PORT = 1883
MQTT_TOPIC = "cronusfarm/camera/ai_count"
# YOLO 클래스명(영문) → 대시보드용 한글 캡션
_KO_CLASS_HINTS = (
    (re.compile(r"tomato|cherry", re.I), "방울토마토"),
    (re.compile(r"potted\s*plant|houseplant|plant", re.I), "화분 식물"),
    (re.compile(r"broccoli", re.I), "브로콜리"),
    (re.compile(r"carrot", re.I), "당근"),
    (re.compile(r"orange", re.I), "오렌지"),
    (re.compile(r"apple", re.I), "사과"),
    (re.compile(r"banana", re.I), "바나나"),
    (re.compile(r"vase", re.I), "화병"),
    (re.compile(r"person", re.I), "사람"),
)
MODEL_PATH = os.path.expanduser("~/CronusFarm/YOLO/cherry_tomato_best.pt")
# 콤마로 여러 인덱스 시도: CRONUSFARM_CAMERA_IDS=0,1,2
CAMERA_IDS = os.environ.get("CRONUSFARM_CAMERA_IDS", "0,1,2,3")
PORT = 8081

app = Flask(__name__)
camera = None
model = None
try:
    mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
except AttributeError:
    mqtt_client = mqtt.Client()

latest_frame = None
latest_count = 0
lock = threading.Lock()


def setup_mqtt():
    try:
        mqtt_client.connect(MQTT_HOST, MQTT_PORT, 60)
        mqtt_client.loop_start()
        print(f"MQTT Connected to {MQTT_HOST}:{MQTT_PORT}")
    except Exception as e:
        print(f"MQTT Connection Error: {e}")


def _placeholder_bgr(msg: str) -> np.ndarray:
    """카메라 없을 때 MJPEG에 넣을 고정 프레임."""
    img = np.zeros((480, 640, 3), dtype=np.uint8)
    y = 200
    for line in msg.split("\n")[:4]:
        cv2.putText(
            img,
            line[:48],
            (24, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (180, 180, 200),
            1,
            cv2.LINE_AA,
        )
        y += 36
    return img


def _load_yolo():
    """YOLO-World는 CLIP 의존으로 Pi(PEP668)에서 자주 실패 → 로컬 가중치 또는 경량 yolov8n."""
    mp = os.path.expanduser(MODEL_PATH)
    if os.path.isfile(mp):
        print(f"YOLO 가중치 로드: {mp}")
        return YOLO(mp)
    print("로컬 가중치 없음 → yolov8n.pt (최초 1회 다운로드 가능)")
    return YOLO("yolov8n.pt")


def _try_open_capture(idx: int) -> cv2.VideoCapture | None:
    for backend in (cv2.CAP_V4L2, cv2.CAP_ANY):
        cap = cv2.VideoCapture(idx, backend) if backend == cv2.CAP_V4L2 else cv2.VideoCapture(idx)
        if not cap.isOpened():
            cap.release()
            continue
        try:
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        except Exception:
            pass
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        ok, fr = cap.read()
        if ok and fr is not None and fr.size > 0:
            return cap
        cap.release()
    return None


def _ko_label_for_class(raw: str) -> str:
    """검출 클래스 문자열을 짧은 한글 식물/객체 캡션으로."""
    s = (raw or "").strip()
    if not s:
        return "알 수 없음"
    for rx, ko in _KO_CLASS_HINTS:
        if rx.search(s):
            return ko
    return s


def _normalize_yolo_label(raw: str, conf: float) -> str | None:
    del conf
    ko = _ko_label_for_class(raw)
    return ko if ko and ko != "알 수 없음" else None


def _analysis_from_result(result, model) -> dict:
    """MQTT·자막용 — 작물명·개수·잎 수."""
    try:
        boxes = result.boxes
        if boxes is None or len(boxes) == 0:
            return analyze_crop_detections([])
        names = getattr(result, "names", None) or getattr(model, "names", None) or {}
        if not isinstance(names, dict):
            try:
                names = dict(names)
            except Exception:
                names = {}
        items = ultralytics_boxes_to_crop_dets(boxes, names, _normalize_yolo_label)
        if not items:
            for i, c in enumerate(boxes.cls):
                ci = int(c.item())
                ko = _ko_label_for_class(str(names.get(ci, str(ci))))
                cx = cy = None
                xywhn = getattr(boxes, "xywhn", None)
                if xywhn is not None and len(xywhn) > i:
                    cx = float(xywhn[i][0].item())
                    cy = float(xywhn[i][1].item())
                items.append(CropDet(label=ko, conf=1.0, cx=cx, cy=cy))
        ko_map = {d.label: d.label for d in items}
        return analyze_crop_detections(items, ko_map=ko_map)
    except Exception:
        return {
            "count": 0,
            "crop_name": "없음",
            "crop_count": 0,
            "leaf_count": 0,
            "caption": "작물: 없음 | 개수: 0 | 잎: 0",
        }


def _open_first_working_camera() -> tuple[cv2.VideoCapture | None, int]:
    for part in CAMERA_IDS.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            idx = int(part)
        except ValueError:
            continue
        cap = _try_open_capture(idx)
        if cap is not None:
            print(f"카메라 열림: index={idx}")
            return cap, idx
    return None, -1


def camera_loop():
    global latest_frame, latest_count, camera, model

    model = None
    try:
        model = _load_yolo()
        print("YOLO 로드 완료")
    except Exception as e:
        print(f"모델 로드 실패 — 원본 영상만 스트림: {e}")

    camera, cam_idx = _open_first_working_camera()
    if camera is None:
        print("카메라 장치 없음 — 플레이스홀더 MJPEG만 송출 (CRONUSFARM_CAMERA_IDS 확인)")
        ph = _placeholder_bgr("NO CAMERA\n/dev/video* 열기 실패\nCRONUSFARM_CAMERA_IDS=0,1,...")
        last_ph_mqtt = 0.0
        while True:
            with lock:
                latest_frame = ph.copy()
                latest_count = 0
            now = time.time()
            if now - last_ph_mqtt >= 1.5:
                last_ph_mqtt = now
                try:
                    mqtt_client.publish(
                        MQTT_TOPIC,
                        json.dumps(
                            {
                                "count": 0,
                                "caption": "포착 불가: USB 카메라를 열 수 없음(ustreamer 등 다른 점유·권한 확인)",
                                "timestamp": now,
                            },
                            ensure_ascii=False,
                        ),
                    )
                except Exception:
                    pass
            time.sleep(0.5)

    print(f"카메라 {cam_idx} 스트림 루프 시작")

    last_publish_time = time.time()

    while True:
        success, frame = camera.read()
        if not success:
            time.sleep(0.1)
            continue

        analysis = {
            "count": 0,
            "caption": "작물: 없음 | 개수: 0 | 잎: 0",
            "crop_name": "없음",
            "crop_count": 0,
            "leaf_count": 0,
        }
        if model is not None:
            try:
                results = model.predict(frame, conf=0.5, verbose=False)
                result = results[0]
                annotated_frame = result.plot()
                analysis = _analysis_from_result(result, model)
            except Exception as e:
                print(f"추론 스킵(원본): {e}")
                annotated_frame = frame
        else:
            annotated_frame = frame

        caption = str(analysis.get("caption") or "")
        count = int(analysis.get("count") or 0)
        if caption.strip():
            annotated_frame = draw_subtitle_on_bgr(annotated_frame, caption)

        with lock:
            latest_frame = annotated_frame.copy()
            latest_count = count

        current_time = time.time()
        if current_time - last_publish_time >= 1.0:
            payload = json.dumps(
                {
                    "count": count,
                    "caption": caption,
                    "crop_name": analysis.get("crop_name"),
                    "crop_count": analysis.get("crop_count"),
                    "leaf_count": analysis.get("leaf_count"),
                    "timestamp": current_time,
                },
                ensure_ascii=False,
            )
            last_publish_time = current_time
            try:
                mqtt_client.publish(MQTT_TOPIC, payload)
            except Exception:
                pass


def generate_mjpeg():
    global latest_frame
    idle = 0
    while True:
        with lock:
            if latest_frame is None:
                frame = None
            else:
                frame = latest_frame.copy()

        if frame is None:
            idle += 1
            # 카메라 스레드 기동 전 짧은 공백
            if idle > 100:
                frame = _placeholder_bgr("WAITING…")
            else:
                time.sleep(0.05)
                continue

        idle = 0
        ret, buffer = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 82])
        if not ret:
            continue

        frame_bytes = buffer.tobytes()
        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n"
        )
        time.sleep(0.05)


@app.route("/video_feed")
def video_feed():
    return Response(
        generate_mjpeg(),
        mimetype="multipart/x-mixed-replace; boundary=frame",
    )


@app.route("/")
def index():
    return "<h1>CronusFarm AI Camera Stream</h1><img src='/video_feed'>"


if __name__ == "__main__":
    setup_mqtt()

    cam_thread = threading.Thread(target=camera_loop, daemon=True)
    cam_thread.start()

    print(f"Starting Video Stream at http://0.0.0.0:{PORT}/video_feed")
    app.run(host="0.0.0.0", port=PORT, threaded=True, use_reloader=False)
