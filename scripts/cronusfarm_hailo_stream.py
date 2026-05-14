#!/usr/bin/env python3
"""
Hailo + GStreamer MJPEG 스트림 (YOLOv8 계열).

커스텀 모델:
  - 저장소 CronusFarm/Hailo/best.onnx 는 Pi에서 hailonet 에 직접 넣을 수 없고,
    Hailo Dataflow Compiler 로 컴파일한 best.hef 가 필요합니다.
  - 기본 탐색: ~/CronusFarm/Hailo/best.hef → 있으면 사용.
  - best.onnx 만 있고 best.hef 가 없으면 오류 종료(CRONUSFARM_HAILO_FALLBACK_SYSTEM=1 이면 시스템 HEF 임시 사용).

환경변수:
  CRONUSFARM_HAILO_DIR      기본 ~/CronusFarm/Hailo
  CRONUSFARM_HAILO_HEF     사용할 .hef 절대경로(지정 시 우선)
  CRONUSFARM_HAILO_YOLO_JSON  hailofilter config (기본: Hailo 디렉터리의 yolov8.json 또는 시스템 yolov8.json)
  CRONUSFARM_HAILO_VIDEO_DEVICE  기본 /dev/video0
  CRONUSFARM_HAILO_FALLBACK_SYSTEM  1 이면 best.onnx 만 있을 때 시스템 yolov8s HEF 로 임시 동작
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import gi
import paho.mqtt.client as mqtt

gi.require_version("Gst", "1.0")
from gi.repository import Gst, GLib

try:
    import hailo
except ImportError:
    print(
        "Error: hailo python module not found. Make sure python3-hailo-tappas is installed.",
        file=sys.stderr,
    )
    sys.exit(1)

# MQTT Settings
MQTT_HOST = "127.0.0.1"
MQTT_PORT = 1883
MQTT_TOPIC = "cronusfarm/hailo/count"

DEFAULT_SYS_HEF = Path("/usr/share/hailo-models/yolov8s_h8l.hef")
DEFAULT_SYS_YOLO_JSON = Path("/usr/share/hailo-models/yolov8.json")


def _hailo_dir() -> Path:
    raw = os.environ.get("CRONUSFARM_HAILO_DIR", "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return (Path.home() / "CronusFarm" / "Hailo").resolve()


def resolve_hef_and_yolo_json() -> tuple[Path, Path, str]:
    """(hef_path, yolo_json_path, human_label)"""
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
                f"WARN: {custom_hef.name} 없음 — CRONUSFARM_HAILO_FALLBACK_SYSTEM=1 로 시스템 YOLOv8s HEF 사용",
                file=sys.stderr,
            )
            yj = Path(
                os.environ.get(
                    "CRONUSFARM_HAILO_YOLO_JSON", str(DEFAULT_SYS_YOLO_JSON)
                )
            ).expanduser()
            if not yj.is_file():
                yj = DEFAULT_SYS_YOLO_JSON
            return DEFAULT_SYS_HEF, yj, f"폴백 시스템 HEF(onnx만 존재): {DEFAULT_SYS_HEF}"
        print(
            f"ERROR: {custom_onnx} 는 있으나 Hailo GStreamer hailonet 은 .hef 만 로드합니다.\n"
            f"  동일 폴더에 best.hef 를 생성해 두세요 (예: Hailo Dataflow Compiler 로 ONNX 컴파일).\n"
            f"  디렉터리: {d}",
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

    print(
        "ERROR: 사용할 .hef 를 찾을 수 없습니다. "
        f"~/CronusFarm/Hailo/best.hef 또는 {DEFAULT_SYS_HEF} 를 확인하세요.",
        file=sys.stderr,
    )
    sys.exit(1)


def _resolve_yolo_json_path() -> Path:
    env = os.environ.get("CRONUSFARM_HAILO_YOLO_JSON", "").strip()
    if env:
        p = Path(env).expanduser().resolve()
        if p.is_file():
            return p
        print(f"WARN: CRONUSFARM_HAILO_YOLO_JSON 없음, Hailo 디렉터리 탐색: {p}", file=sys.stderr)
    local = _hailo_dir() / "yolov8.json"
    if local.is_file():
        return local
    if DEFAULT_SYS_YOLO_JSON.is_file():
        return DEFAULT_SYS_YOLO_JSON
    print("ERROR: yolov8.json (hailofilter config) 없음.", file=sys.stderr)
    sys.exit(1)


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

    current_time = time.time()
    if current_time - last_publish_time >= PUBLISH_INTERVAL:
        last_publish_time = current_time
        payload = json.dumps({"count": count, "timestamp": current_time})
        try:
            mqtt_client.publish(MQTT_TOPIC, payload)
        except Exception:
            pass
        print(f"Objects detected: {count}")

    return Gst.PadProbeReturn.OK


def main() -> None:
    Gst.init(None)

    hef_path, yolo_json, label = resolve_hef_and_yolo_json()
    video_dev = os.environ.get("CRONUSFARM_HAILO_VIDEO_DEVICE", "/dev/video0").strip() or "/dev/video0"

    print(f"[hailo] {label}")
    print(f"[hailo] yolov8.json: {yolo_json}")
    print(f"[hailo] video: {video_dev}")

    hef_s = str(hef_path)
    json_s = str(yolo_json)

    pipeline_str = (
        f"v4l2src device={video_dev} ! "
        "videoscale ! "
        "videoconvert ! "
        "video/x-raw, format=RGB, width=640, height=640, framerate=15/1 ! "
        f"hailonet hef-path={hef_s} batch-size=1 ! "
        "hailofilter "
        "so-path=/usr/lib/aarch64-linux-gnu/hailo/tappas/post_processes/libyolo_post.so "
        f"config-path={json_s} qos=false ! "
        "queue ! "
        "hailooverlay ! "
        "videoconvert ! "
        "jpegenc ! "
        "multipartmux ! "
        "tcpserversink host=0.0.0.0 port=8081"
    )

    pipeline = Gst.parse_launch(pipeline_str)

    hailofilter = pipeline.get_by_name("hailofilter0")
    if hailofilter:
        srcpad = hailofilter.get_static_pad("src")
        srcpad.add_probe(Gst.PadProbeType.BUFFER, probe_callback)
    else:
        print("Warning: Could not find hailofilter element in pipeline to attach probe.")

    loop = GLib.MainLoop()
    pipeline.set_state(Gst.State.PLAYING)

    print("Hailo Streamer Started. Video at http://<pi-ip>:8081. Counts published to MQTT.")

    try:
        loop.run()
    except KeyboardInterrupt:
        pass
    finally:
        pipeline.set_state(Gst.State.NULL)
        mqtt_client.loop_stop()


if __name__ == "__main__":
    main()
