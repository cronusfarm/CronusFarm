#!/usr/bin/env python3
"""
Hailo + GStreamer MJPEG 스트림 (YOLOv8 계열).

커스텀 모델:
  - best.hef → ~/CronusFarm/Hailo/best.hef
  - yolov8.json → libyolo_post 형식(anchors·labels)

입력(기본 ustreamer):
  - ustreamer가 /dev/video0 점유 시 v4l2src 대신 http://127.0.0.1:8080/stream 사용
  - CRONUSFARM_HAILO_SOURCE=v4l2 로 직접 UVC(MJPG 1280x720)

출력:
  - Flask HTTP MJPEG http://<pi>:8081/video_feed  (tcpserversink 대신 브라우저 호환)
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time
from pathlib import Path

import cv2
import gi
import numpy as np
import paho.mqtt.client as mqtt
from flask import Flask, Response

gi.require_version("Gst", "1.0")
gi.require_version("GstApp", "1.0")
from gi.repository import Gst, GLib, GstApp

try:
    import hailo
except ImportError:
    print(
        "Error: hailo python module not found. Make sure python3-hailo-tappas is installed.",
        file=sys.stderr,
    )
    sys.exit(1)

MQTT_HOST = "127.0.0.1"
MQTT_PORT = 1883
# 대시보드·Node-RED(nr_node_mqtt_ai_count)와 동일 토픽
MQTT_TOPIC = os.environ.get(
    "CRONUSFARM_AI_MQTT_TOPIC", "cronusfarm/camera/ai_count"
)

DEFAULT_SYS_HEF = Path("/usr/share/hailo-models/yolov8s_h8l.hef")
DEFAULT_SYS_YOLO_JSON = Path("/usr/share/hailo-models/yolov8.json")

HTTP_PORT = int(os.environ.get("CRONUSFARM_HAILO_HTTP_PORT", "8081"))
USTREAMER_URL = os.environ.get(
    "CRONUSFARM_HAILO_USTREAMER_URL", "http://127.0.0.1:8080/stream"
).strip()
HAILO_SOURCE = os.environ.get("CRONUSFARM_HAILO_SOURCE", "ustreamer").strip().lower()

app = Flask(__name__)
_latest_jpeg: bytes | None = None
_jpeg_lock = threading.Lock()
_running = True
_FRAME_DUR = None  # Gst.SECOND // 15, init in main


def _hailo_dir() -> Path:
    raw = os.environ.get("CRONUSFARM_HAILO_DIR", "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return (Path.home() / "CronusFarm" / "Hailo").resolve()


def resolve_hef_and_yolo_json() -> tuple[Path, Path, str]:
    explicit = os.environ.get("CRONUSFARM_HAILO_HEF", "").strip()
    if explicit:
        p = Path(explicit).expanduser().resolve()
        if not p.is_file():
            print(f"ERROR: CRONUSFARM_HAILO_HEF 파일 없음: {p}", file=sys.stderr)
            sys.exit(1)
        yj = _resolve_yolo_json_path()
        return p, yj, f"환경변수 HEF: {p}"

    d = _hailo_dir()
    custom_hef = d / "best.hef"
    custom_onnx = d / "best.onnx"

    if custom_hef.is_file():
        yj = _resolve_yolo_json_path()
        return custom_hef, yj, f"커스텀 HEF: {custom_hef}"

    if custom_onnx.is_file():
        if (
            os.environ.get("CRONUSFARM_HAILO_FALLBACK_SYSTEM", "").strip() == "1"
            and DEFAULT_SYS_HEF.is_file()
        ):
            print(
                f"WARN: {custom_hef.name} 없음 — 시스템 YOLOv8s HEF 폴백",
                file=sys.stderr,
            )
            yj = Path(
                os.environ.get(
                    "CRONUSFARM_HAILO_YOLO_JSON", str(DEFAULT_SYS_YOLO_JSON)
                )
            ).expanduser()
            if not yj.is_file():
                yj = DEFAULT_SYS_YOLO_JSON
            return DEFAULT_SYS_HEF, yj, f"폴백 시스템 HEF: {DEFAULT_SYS_HEF}"
        print(
            f"ERROR: {custom_onnx} 만 있고 {custom_hef.name} 없음. HEF 컴파일 후 배포하세요.",
            file=sys.stderr,
        )
        sys.exit(1)

    if DEFAULT_SYS_HEF.is_file():
        yj = Path(
            os.environ.get(
                "CRONUSFARM_HAILO_YOLO_JSON", str(DEFAULT_SYS_YOLO_JSON)
            )
        ).expanduser()
        if not yj.is_file():
            yj = DEFAULT_SYS_YOLO_JSON
        return DEFAULT_SYS_HEF, yj, f"시스템 기본 HEF: {DEFAULT_SYS_HEF}"

    print("ERROR: 사용할 .hef 없음.", file=sys.stderr)
    sys.exit(1)


def _postprocess_paths(yolo_json: Path) -> tuple[str, str]:
    """HEF에 NMS 포함(yolov8_crops.alls) → libyolo_hailortpp + labels JSON."""
    explicit_so = os.environ.get("CRONUSFARM_HAILO_POST_SO", "").strip()
    if explicit_so:
        return explicit_so, str(yolo_json)
    try:
        data = json.loads(yolo_json.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        data = {}
    if "anchors" in data:
        so = (
            "/usr/lib/aarch64-linux-gnu/hailo/tappas/post_processes/libyolo_post.so"
        )
    else:
        so = (
            "/usr/lib/aarch64-linux-gnu/hailo/tappas/post_processes/"
            "libyolo_hailortpp_post.so"
        )
    return so, str(yolo_json)


def _ko_caption_from_detections(detections) -> str:
    """검출 라벨 → MQTT·대시보드용 한글 캡션."""
    if not detections:
        return "포착: 없음 (검출된 작물·객체 없음)"
    labels: list[str] = []
    for d in detections:
        try:
            labels.append(str(d.get_label()))
        except Exception:
            pass
    if not labels:
        return f"포착: {len(detections)}개"
    from collections import Counter

    ctr = Counter(labels)
    parts = []
    ko_map = {
        "tomato": "토마토",
        "fig": "무화과",
        "butterhead": "버터헤드",
        "basil": "바질",
        "cherry_tomato": "방울토마토",
        "unlabeled": "미분류",
    }
    for k in sorted(ctr.keys()):
        v = ctr[k]
        name = ko_map.get(k, k)
        parts.append(f"{name}×{v}" if v > 1 else name)
    return "포착: " + " · ".join(parts)


def _resolve_yolo_json_path() -> Path:
    env = os.environ.get("CRONUSFARM_HAILO_YOLO_JSON", "").strip()
    if env:
        p = Path(env).expanduser().resolve()
        if p.is_file():
            return p
    local = _hailo_dir() / "yolov8.json"
    if local.is_file():
        return local
    if DEFAULT_SYS_YOLO_JSON.is_file():
        return DEFAULT_SYS_YOLO_JSON
    print("ERROR: yolov8.json (hailofilter config) 없음.", file=sys.stderr)
    sys.exit(1)


def _build_v4l2_source() -> str:
    dev = os.environ.get("CRONUSFARM_HAILO_VIDEO_DEVICE", "/dev/video0").strip()
    return (
        f"v4l2src device={dev} ! "
        "image/jpeg,width=1280,height=720,framerate=15/1 ! jpegdec ! "
        "videoscale ! videoconvert ! "
    )


def _opencv_feed_loop(appsrc: Gst.Element) -> None:
    """ustreamer MJPEG는 souphttpsrc와 협상 실패 → OpenCV로 8080/stream 수신."""
    cap = cv2.VideoCapture(USTREAMER_URL)
    if not cap.isOpened():
        print(f"ERROR: ustreamer URL 열기 실패: {USTREAMER_URL}", file=sys.stderr)
        return
    ts = 0
    while _running:
        ret, bgr = cap.read()
        if not ret:
            time.sleep(0.02)
            continue
        bgr = cv2.resize(bgr, (640, 640))
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        data = rgb.tobytes()
        buf = Gst.Buffer.new_allocate(None, len(data), None)
        buf.fill(0, data)
        buf.pts = ts
        buf.duration = _FRAME_DUR
        ts += _FRAME_DUR
        if appsrc.emit("push-buffer", buf) != Gst.FlowReturn.OK:
            break
        time.sleep(1.0 / 15.0)
    cap.release()


try:
    mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
except AttributeError:
    mqtt_client = mqtt.Client()
try:
    mqtt_client.connect(MQTT_HOST, MQTT_PORT, 60)
    mqtt_client.loop_start()
except Exception as e:
    print(f"Warning: Could not connect to MQTT broker: {e}")

last_publish_time = 0.0
PUBLISH_INTERVAL = 1.0


def probe_callback(pad, info):
    global last_publish_time
    buffer = info.get_buffer()
    if not buffer:
        return Gst.PadProbeReturn.OK

    roi = hailo.get_roi_from_buffer(buffer)
    detections = roi.get_objects_typed(hailo.HAILO_DETECTION)
    count = len(detections)
    caption = _ko_caption_from_detections(detections)

    current_time = time.time()
    if current_time - last_publish_time >= PUBLISH_INTERVAL:
        last_publish_time = current_time
        payload = json.dumps(
            {
                "count": count,
                "caption": caption,
                "timestamp": current_time,
            },
            ensure_ascii=False,
        )
        try:
            mqtt_client.publish(MQTT_TOPIC, payload)
        except Exception:
            pass
        print(f"Objects detected: {count} — {caption}")

    return Gst.PadProbeReturn.OK


def _caps_wh(structure) -> tuple[int, int]:
    """Gst.Structure / StructureWrapper 호환 (Pi Tappas는 get_value)."""
    try:
        if hasattr(structure, "get_value"):
            return int(structure.get_value("width")), int(structure.get_value("height"))
    except (TypeError, ValueError, AttributeError):
        pass
    try:
        if hasattr(structure, "get_int"):
            ok, w = structure.get_int("width")
            ok2, h = structure.get_int("height")
            if ok and ok2:
                return int(w), int(h)
    except (TypeError, ValueError, AttributeError):
        pass
    return 640, 640


def _on_new_sample(sink: GstApp.AppSink) -> Gst.FlowReturn:
    global _latest_jpeg
    sample = sink.emit("pull-sample")
    if sample is None:
        return Gst.FlowReturn.ERROR

    buffer = sample.get_buffer()
    caps = sample.get_caps()
    if not buffer or not caps:
        return Gst.FlowReturn.ERROR

    width, height = _caps_wh(caps.get_structure(0))

    success, map_info = buffer.map(Gst.MapFlags.READ)
    if not success:
        return Gst.FlowReturn.ERROR
    try:
        arr = np.frombuffer(map_info.data, dtype=np.uint8).reshape((height, width, 3))
        ret, enc = cv2.imencode(".jpg", arr, [int(cv2.IMWRITE_JPEG_QUALITY), 82])
        if ret:
            with _jpeg_lock:
                _latest_jpeg = enc.tobytes()
    finally:
        buffer.unmap(map_info)
    return Gst.FlowReturn.OK


def _generate_mjpeg():
    while True:
        with _jpeg_lock:
            frame = _latest_jpeg
        if frame:
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
            )
        time.sleep(0.05)


@app.route("/video_feed")
def video_feed():
    return Response(
        _generate_mjpeg(),
        mimetype="multipart/x-mixed-replace; boundary=frame",
    )


@app.route("/")
def index():
    return (
        "<h1>CronusFarm Hailo Stream</h1>"
        "<img src='/video_feed' alt='Hailo overlay'/>"
    )


def _run_flask():
    print(f"[hailo] HTTP MJPEG http://0.0.0.0:{HTTP_PORT}/video_feed")
    app.run(host="0.0.0.0", port=HTTP_PORT, threaded=True, use_reloader=False)


def main() -> None:
    global _FRAME_DUR
    Gst.init(None)
    _FRAME_DUR = Gst.SECOND // 15

    hef_path, yolo_json, label = resolve_hef_and_yolo_json()
    print(f"[hailo] {label}")
    print(f"[hailo] yolov8.json: {yolo_json}")
    print(f"[hailo] source: {HAILO_SOURCE} ({USTREAMER_URL if HAILO_SOURCE != 'v4l2' else 'v4l2'})")

    hef_s = str(hef_path)
    json_s = str(yolo_json)
    post_so, post_cfg = _postprocess_paths(yolo_json)
    print(f"[hailo] postprocess: {post_so}")

    hailo_tail = (
        f"hailonet hef-path={hef_s} batch-size=1 force-writable=true ! "
        "hailofilter function-name=filter "
        f"so-path={post_so} "
        f"config-path={post_cfg} qos=false ! "
        "queue ! hailooverlay ! videoconvert ! "
        "video/x-raw, format=BGR ! "
        "appsink name=cf_appsink emit-signals=true max-buffers=1 drop=true sync=false"
    )

    if HAILO_SOURCE == "v4l2":
        pipeline_str = (
            f"{_build_v4l2_source()}"
            "video/x-raw, format=RGB, width=640, height=640, framerate=15/1 ! "
            f"{hailo_tail}"
        )
    else:
        pipeline_str = (
            "appsrc name=cf_appsrc is-live=true do-timestamp=true format=GST_FORMAT_TIME "
            "caps=video/x-raw,format=RGB,width=640,height=640,framerate=15/1 ! "
            "queue max-size-buffers=2 leaky=downstream ! "
            f"{hailo_tail}"
        )

    pipeline = Gst.parse_launch(pipeline_str)

    appsrc_elem = pipeline.get_by_name("cf_appsrc")
    if appsrc_elem and HAILO_SOURCE != "v4l2":
        threading.Thread(target=_opencv_feed_loop, args=(appsrc_elem,), daemon=True).start()

    appsink = pipeline.get_by_name("cf_appsink")
    if appsink:
        appsink.set_property("emit-signals", True)
        appsink.connect("new-sample", _on_new_sample)
    else:
        print("ERROR: cf_appsink 없음", file=sys.stderr)
        sys.exit(1)

    hailofilter = pipeline.get_by_name("hailofilter0")
    if hailofilter:
        srcpad = hailofilter.get_static_pad("src")
        srcpad.add_probe(Gst.PadProbeType.BUFFER, probe_callback)

    threading.Thread(target=_run_flask, daemon=True).start()

    loop = GLib.MainLoop()
    pipeline.set_state(Gst.State.PLAYING)
    print("[hailo] GStreamer pipeline PLAYING")

    try:
        loop.run()
    except KeyboardInterrupt:
        pass
    finally:
        global _running
        _running = False
        pipeline.set_state(Gst.State.NULL)
        mqtt_client.loop_stop()


if __name__ == "__main__":
    main()
