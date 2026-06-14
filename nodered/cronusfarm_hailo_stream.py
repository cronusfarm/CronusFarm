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

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

import cv2
import gi
import numpy as np
import paho.mqtt.client as mqtt
from flask import Flask, Response, jsonify

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
_FLIP_VERTICAL = os.environ.get(
    "CRONUSFARM_CAMERA_FLIP_VERTICAL", "1"
).strip().lower() in ("1", "true", "yes")


def _flip_bgr_if_needed(bgr: np.ndarray) -> np.ndarray:
    """카메라 상하 반전(ustreamer V4L flip 미지원 시 OpenCV)."""
    if _FLIP_VERTICAL:
        return cv2.flip(bgr, 0)
    return bgr


app = Flask(__name__)
_latest_jpeg: bytes | None = None
_jpeg_lock = threading.Lock()
_latest_lb_bgr: np.ndarray | None = None
_lb_lock = threading.Lock()
_latest_crop_dets: list[CropDet] = []
_dets_lock = threading.Lock()
_last_hailo_count = 0
_onnx_model = None
_onnx_conf = float(os.environ.get("CRONUSFARM_ONNX_CONF", "0.12"))
from cronusfarm_crop_caption import (  # noqa: E402
    CropDet,
    CROP_MIN_CONF,
    DEFAULT_CROP_MIN_CONF,
    caption_with_source_tag,
    filter_crop_dets_for_display,
    gemini_crop_prompt,
    KO_CROP_MAP as _KO_CROP_MAP,
    analysis_from_gemini_crop_json,
    analyze_crop_detections,
    draw_detection_boxes_on_bgr,
    draw_subtitle_on_bgr,
    hailo_det_to_crop_det,
    ultralytics_boxes_to_crop_dets,
)

_GEMINI_CACHE_SOURCES = frozenset(
    {"gemini_caption", "cache", "manual_push", "manual_set"}
)

_latest_caption: str = ""
# CROP_MIN_CONF 와 동기 — raw 후보 수집용(표시는 filter_crop_dets_for_display)
_CLASS_MIN_CONF = dict(CROP_MIN_CONF)
_running = True
_FRAME_DUR = None  # Gst.SECOND // 15, init in main
# 기본 0 = YOLO/Hailo 검출만 자막·MQTT (Gemini 보조는 1로 켬)
_CAPTION_GEMINI = os.environ.get("CRONUSFARM_CAPTION_GEMINI", "0").strip() == "1"
_CAPTION_GEMINI_INTERVAL = float(
    os.environ.get("CRONUSFARM_CAPTION_GEMINI_INTERVAL", "45")
)
_CAPTION_CACHE_PATH = Path(
    os.environ.get(
        "CRONUSFARM_CAPTION_CACHE",
        str(Path.home() / "CronusFarm" / "data" / "crop_caption_cache.json"),
    )
)
_last_gemini_caption_time = 0.0
_last_gemini_attempt_time = 0.0
_gemini_backoff_until = 0.0
_last_positive_caption_time = 0.0
_GEMINI_RETRY_SEC = float(os.environ.get("CRONUSFARM_CAPTION_GEMINI_RETRY", "20"))
_SUPPRESS_ZERO_MQTT = _CAPTION_GEMINI


def _load_caption_cache() -> dict[str, object] | None:
    try:
        if not _CAPTION_CACHE_PATH.is_file():
            return None
        data = json.loads(_CAPTION_CACHE_PATH.read_text(encoding="utf-8"))
        if int(data.get("count") or 0) <= 0:
            return None
        src = str(data.get("source") or "").strip()
        if not _CAPTION_GEMINI:
            if not src or src in _GEMINI_CACHE_SOURCES:
                return None
        return data
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return None


def _save_caption_cache(analysis: dict[str, object], *, source: str = "") -> None:
    if int(analysis.get("count") or 0) <= 0:
        return
    try:
        body = dict(analysis)
        if source:
            body["source"] = source
        _CAPTION_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        _CAPTION_CACHE_PATH.write_text(
            json.dumps(body, ensure_ascii=False),
            encoding="utf-8",
        )
    except OSError:
        pass


def _gemini_analyze_crop(image_path: Path) -> str:
    """429 시 모델·재시도 (telegram_vision과 동일 전략)."""
    import urllib.error

    from cronusfarm_telegram_vision import _gemini_models_to_try, analyze_gemini

    last_err: BaseException | None = None
    for model in _gemini_models_to_try():
        try:
            return analyze_gemini(image_path, gemini_crop_prompt(), model=model)
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code == 429:
                time.sleep(35)
                continue
            raise
        except Exception as e:
            last_err = e
            if "429" in str(e):
                time.sleep(35)
                continue
            raise
    if last_err:
        raise last_err
    raise RuntimeError("Gemini 작물 분석 실패")


def _load_optional_env_file() -> None:
    """Gemini API 키 등 — nodered-telegram.env (이미 설정된 키는 덮어쓰지 않음)."""
    for path in (
        Path("/etc/cronusfarm/nodered-telegram.env"),
        Path.home() / "CronusFarm" / "deploy" / "env" / "nodered-telegram.env",
    ):
        if not path.is_file():
            continue
        try:
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
        except OSError:
            pass


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


def _normalize_crop_label(raw: str, conf: float) -> str | None:
    """검출 라벨 보정·클래스별 최소 conf 필터."""
    label = (raw or "").strip().lower()
    if not label:
        return None
    min_conf = _CLASS_MIN_CONF.get(label, DEFAULT_CROP_MIN_CONF)
    if conf < min_conf:
        return None
    return label


def _set_latest_crop_dets(items: list[CropDet]) -> None:
    with _dets_lock:
        global _latest_crop_dets
        _latest_crop_dets = list(items)


def _get_latest_crop_dets() -> list[CropDet]:
    with _dets_lock:
        return list(_latest_crop_dets)


def _crop_dets_from_hailo(detections) -> list[CropDet]:
    items: list[CropDet] = []
    for d in detections:
        cd = hailo_det_to_crop_det(d, _normalize_crop_label)
        if cd:
            items.append(cd)
    return items


def _finalize_crop_items(raw: list[CropDet]) -> list[CropDet]:
    return filter_crop_dets_for_display(raw)


def _analysis_from_hailo_detections(detections) -> dict[str, object]:
    items = _finalize_crop_items(_crop_dets_from_hailo(detections))
    if items:
        _set_latest_crop_dets(items)
    return analyze_crop_detections(items, ko_map=_KO_CROP_MAP)


def _detect_on_bgr(bgr: np.ndarray) -> tuple[dict[str, object], list[CropDet]]:
    """단일 프레임 ONNX 검출(클릭 재검출·폴백)."""
    global _onnx_model
    onnx_path = _hailo_dir() / "best.onnx"
    if not onnx_path.is_file():
        return analyze_crop_detections([], ko_map=_KO_CROP_MAP), []
    manual_conf = float(os.environ.get("CRONUSFARM_MANUAL_ONNX_CONF", "0.05"))
    try:
        if _onnx_model is None:
            from ultralytics import YOLO

            _onnx_model = YOLO(str(onnx_path))
        results = _onnx_model.predict(bgr, conf=manual_conf, verbose=False)
        boxes = getattr(results[0], "boxes", None)
        names = getattr(results[0], "names", None) or {}
        items = _finalize_crop_items(
            ultralytics_boxes_to_crop_dets(boxes, names, _normalize_crop_label)
        )
        return analyze_crop_detections(items, ko_map=_KO_CROP_MAP), items
    except Exception as e:
        print(f"[detect_now] warn: {e}", file=sys.stderr)
        return analyze_crop_detections([], ko_map=_KO_CROP_MAP), []


def _publish_crop_analysis(analysis: dict[str, object], *, source: str = "") -> None:
    global last_publish_time, _latest_caption, _last_positive_caption_time
    count = int(analysis.get("count") or 0)
    current_time = time.time()
    if count <= 0 and _SUPPRESS_ZERO_MQTT and source not in ("gemini_caption", "cache"):
        return
    if count <= 0 and source != "gemini_caption":
        hold = float(
            os.environ.get(
                "CRONUSFARM_CAPTION_HOLD_SEC",
                str(max(_CAPTION_GEMINI_INTERVAL, 30.0)),
            )
        )
        if (
            _last_positive_caption_time > 0
            and current_time - _last_positive_caption_time < hold
        ):
            return
    force_pub = source in ("gemini_caption", "manual_click", "manual_detect")
    if not force_pub and current_time - last_publish_time < PUBLISH_INTERVAL:
        return
    last_publish_time = current_time
    if count > 0:
        _last_positive_caption_time = current_time
        _save_caption_cache(analysis, source=source or "hailo")
    cap_raw = str(analysis.get("caption") or "")
    _latest_caption = caption_with_source_tag(cap_raw, source)
    analysis = {**analysis, "caption": _latest_caption}
    body: dict[str, object] = {
        "count": count,
        "caption": _latest_caption,
        "crop_name": analysis.get("crop_name"),
        "crop_count": analysis.get("crop_count"),
        "leaf_count": analysis.get("leaf_count"),
        "timestamp": current_time,
    }
    if source:
        body["source"] = source
    payload = json.dumps(body, ensure_ascii=False)
    try:
        info = mqtt_client.publish(MQTT_TOPIC, payload)
        if hasattr(info, "wait_for_publish"):
            info.wait_for_publish(timeout=3.0)
    except Exception:
        pass
    print(f"Objects detected: {count} — {_latest_caption}")


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


def _letterbox_bgr(bgr: np.ndarray, size: int = 640) -> np.ndarray:
    """YOLO 학습과 동일 비율 유지(letterbox)."""
    h, w = bgr.shape[:2]
    scale = min(size / h, size / w)
    nh, nw = int(round(h * scale)), int(round(w * scale))
    resized = cv2.resize(bgr, (nw, nh), interpolation=cv2.INTER_LINEAR)
    out = np.zeros((size, size, 3), dtype=bgr.dtype)
    top = (size - nh) // 2
    left = (size - nw) // 2
    out[top : top + nh, left : left + nw] = resized
    return out


def _crop_black_border(bgr: np.ndarray, thresh: int = 12) -> np.ndarray:
    """MJPEG UI용: letterbox/pillarbox 검정 띠 제거(YOLO 640² 입력은 그대로)."""
    if bgr is None or bgr.size == 0:
        return bgr
    h, w = bgr.shape[:2]
    if h < 8 or w < 8:
        return bgr
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    mask = gray > thresh
    if not np.any(mask):
        return bgr
    ys, xs = np.where(mask)
    y0, y1 = int(ys.min()), int(ys.max()) + 1
    x0, x1 = int(xs.min()), int(xs.max()) + 1
    if (y1 - y0) < h * 0.3 or (x1 - x0) < w * 0.3:
        return bgr
    return bgr[y0:y1, x0:x1]


def _opencv_feed_loop(appsrc: Gst.Element) -> None:
    """ustreamer MJPEG는 souphttpsrc와 협상 실패 → OpenCV로 8080/stream 수신."""
    cap: cv2.VideoCapture | None = None
    fail_streak = 0
    ts = 0

    def _open_cap() -> cv2.VideoCapture | None:
        c = cv2.VideoCapture(USTREAMER_URL)
        if not c.isOpened():
            print(
                f"WARN: ustreamer URL 열기 실패(재시도): {USTREAMER_URL}",
                file=sys.stderr,
            )
            c.release()
            return None
        return c

    while _running:
        if cap is None or not cap.isOpened():
            if cap is not None:
                cap.release()
            cap = _open_cap()
            if cap is None:
                time.sleep(2.0)
                continue
            fail_streak = 0
        ret, bgr = cap.read()
        if not ret:
            fail_streak += 1
            if fail_streak > 45:
                print(
                    "WARN: ustreamer 프레임 끊김 — 캡처 재연결",
                    file=sys.stderr,
                )
                cap.release()
                cap = None
                fail_streak = 0
            time.sleep(0.05)
            continue
        fail_streak = 0
        bgr = _letterbox_bgr(bgr, 640)
        with _lb_lock:
            global _latest_lb_bgr
            _latest_lb_bgr = bgr.copy()
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
    if cap is not None:
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


def _analysis_from_ultralytics(result) -> dict[str, object]:
    """Ultralytics ONNX 폴백 → 분석 dict."""
    boxes = getattr(result, "boxes", None)
    names = getattr(result, "names", None) or {}
    items = _finalize_crop_items(
        ultralytics_boxes_to_crop_dets(boxes, names, _normalize_crop_label)
    )
    return analyze_crop_detections(items, ko_map=_KO_CROP_MAP)


def _gemini_caption_loop() -> None:
    """YOLO/Hailo 미검출 시 Gemini로 자막 보완 (현장 조명·각도와 학습 데이터 괴리)."""
    global _last_gemini_caption_time, _last_gemini_attempt_time, _gemini_backoff_until, _last_hailo_count
    if not _CAPTION_GEMINI:
        return
    _load_optional_env_file()
    if not (os.environ.get("CRONUSFARM_GEMINI_API_KEY") or "").strip():
        print("[gemini-caption] CRONUSFARM_GEMINI_API_KEY 없음 — 비활성", file=sys.stderr)
        return
    print("[gemini-caption] loop start", flush=True)
    tmp_jpg = Path("/tmp/cf_hailo_gemini_cap.jpg")
    boot = time.time()
    while _running:
        time.sleep(2.0)
        if _last_hailo_count > 0:
            continue
        now = time.time()
        if now < _gemini_backoff_until:
            continue
        if _last_gemini_attempt_time > 0 and now - _last_gemini_attempt_time < _GEMINI_RETRY_SEC:
            continue
        if _last_gemini_caption_time > 0:
            if now - _last_gemini_caption_time < _CAPTION_GEMINI_INTERVAL:
                continue
        elif now - boot < 8.0:
            continue
        with _lb_lock:
            bgr = None if _latest_lb_bgr is None else _latest_lb_bgr.copy()
        if bgr is None:
            continue
        try:
            _last_gemini_attempt_time = now
            if not cv2.imwrite(str(tmp_jpg), bgr):
                print("[gemini-caption] imwrite 실패", file=sys.stderr)
                continue
            text = _gemini_analyze_crop(tmp_jpg)
            analysis = analysis_from_gemini_crop_json(text)
            if not analysis:
                print("[gemini-caption] JSON 파싱 실패", file=sys.stderr)
                continue
            cnt = int(analysis.get("count") or 0)
            if cnt <= 0:
                print(
                    f"[gemini-caption] 작물 없음 응답: {text[:120]}",
                    file=sys.stderr,
                )
                continue
            _publish_crop_analysis(analysis, source="gemini_caption")
            _last_gemini_caption_time = now
            print(
                f"Objects detected: {cnt} — {analysis.get('caption')} (gemini)",
                flush=True,
            )
        except Exception as e:
            err = str(e)
            print(f"[gemini-caption] warn: {e}", file=sys.stderr)
            if "429" in err:
                _gemini_backoff_until = now + 180.0
                cached = _load_caption_cache()
                if cached:
                    src = str(cached.get("source") or "cache")
                    _publish_crop_analysis(cached, source=src)
                    _last_positive_caption_time = time.time()
                    print(
                        f"Objects detected: {cached.get('count')} — "
                        f"{cached.get('caption')} ({src})",
                        flush=True,
                    )


def _onnx_fallback_loop() -> None:
    """Hailo NMS 임계값이 높을 때 CPU ONNX로 작물 검출 보완."""
    global _onnx_model, last_publish_time, _last_hailo_count
    onnx_path = _hailo_dir() / "best.onnx"
    if not onnx_path.is_file():
        return
    while _running:
        time.sleep(1.2)
        if _last_hailo_count > 0:
            continue
        with _lb_lock:
            bgr = None if _latest_lb_bgr is None else _latest_lb_bgr.copy()
        if bgr is None:
            continue
        try:
            if _onnx_model is None:
                from ultralytics import YOLO

                _onnx_model = YOLO(str(onnx_path))
            results = _onnx_model.predict(bgr, conf=_onnx_conf, verbose=False)
            analysis = _analysis_from_ultralytics(results[0])
            boxes = getattr(results[0], "boxes", None)
            names = getattr(results[0], "names", None) or {}
            items = _finalize_crop_items(
                ultralytics_boxes_to_crop_dets(boxes, names, _normalize_crop_label)
            )
            if items:
                _set_latest_crop_dets(items)
            if int(analysis.get("count") or 0) <= 0:
                continue
            _publish_crop_analysis(analysis, source="onnx_fallback")
        except Exception as e:
            print(f"[onnx-fallback] warn: {e}", file=sys.stderr)


def probe_callback(pad, info):
    global last_publish_time, _last_hailo_count
    buffer = info.get_buffer()
    if not buffer:
        return Gst.PadProbeReturn.OK

    roi = hailo.get_roi_from_buffer(buffer)
    detections = roi.get_objects_typed(hailo.HAILO_DETECTION)
    analysis = _analysis_from_hailo_detections(detections)
    count = int(analysis.get("count") or 0)
    _last_hailo_count = count
    global _latest_caption
    if count <= 0:
        # 0프레임만 와도 박스는 직전 검출 유지(깜빡임 방지). 자막만 갱신.
        hold = float(
            os.environ.get(
                "CRONUSFARM_CAPTION_HOLD_SEC",
                str(max(_CAPTION_GEMINI_INTERVAL, 30.0)),
            )
        )
        if (
            _last_positive_caption_time > 0
            and time.time() - _last_positive_caption_time < hold
        ):
            return Gst.PadProbeReturn.OK
        _latest_caption = str(analysis.get("caption") or "작물: 없음 | 개수: 0 | 잎: 0")
        _publish_crop_analysis(analysis, source="hailo")
        return Gst.PadProbeReturn.OK
    _publish_crop_analysis(analysis, source="hailo")

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
        bgr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
        buffer = sample.get_buffer()
        if buffer:
            try:
                roi = hailo.get_roi_from_buffer(buffer)
                detections = roi.get_objects_typed(hailo.HAILO_DETECTION)
                items = _finalize_crop_items(_crop_dets_from_hailo(detections))
                if items:
                    _set_latest_crop_dets(items)
            except Exception:
                pass
        dets = _get_latest_crop_dets()
        if dets:
            bgr = draw_detection_boxes_on_bgr(bgr, dets, ko_map=_KO_CROP_MAP)
        # 자막은 대시보드 cf-ai-cap-txt(HTML)만 사용 — 번인 시 이중·뒤집힘 방지
        if os.environ.get("CRONUSFARM_BURN_CAPTION", "").strip().lower() in (
            "1",
            "true",
            "yes",
        ):
            cap = _latest_caption.strip()
            if cap:
                bgr = draw_subtitle_on_bgr(bgr, cap)
        # MJPEG 출력 직전 1회만 상하 반전(입력+출력 이중 flip 방지)
        bgr = _flip_bgr_if_needed(bgr)
        bgr = _crop_black_border(bgr)
        ret, enc = cv2.imencode(".jpg", bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 82])
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
        else:
            # 빈 청크는 <img> onerror·검정 화면 유발 — 프레임 대기만
            time.sleep(0.12)
            continue
        time.sleep(0.05)


@app.route("/detect_now", methods=["GET", "POST"])
def detect_now():
    """UI 클릭 시 현재 프레임으로 즉시 재검출."""
    global last_publish_time, _last_hailo_count
    with _lb_lock:
        bgr = None if _latest_lb_bgr is None else _latest_lb_bgr.copy()
    if bgr is None:
        return jsonify(ok=False, error="no_frame"), 503
    analysis, items = _detect_on_bgr(bgr)
    if not items:
        prev = _get_latest_crop_dets()
        if prev:
            items = prev
            analysis = analyze_crop_detections(items, ko_map=_KO_CROP_MAP)
    if items:
        _set_latest_crop_dets(items)
    _last_hailo_count = int(analysis.get("count") or 0)
    last_publish_time = 0.0
    if int(analysis.get("count") or 0) > 0 or items:
        _publish_crop_analysis(analysis, source="manual_click")
    return jsonify(
        ok=True,
        count=int(analysis.get("count") or 0),
        caption=str(analysis.get("caption") or ""),
        crop_name=analysis.get("crop_name"),
        crop_count=analysis.get("crop_count"),
        leaf_count=analysis.get("leaf_count"),
        boxes=len(items),
    )


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
        "queue ! videoconvert ! "
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

    threading.Thread(target=_onnx_fallback_loop, daemon=True).start()
    if _CAPTION_GEMINI:
        threading.Thread(target=_gemini_caption_loop, daemon=True).start()
        _load_optional_env_file()
        cached_boot = _load_caption_cache()
        if cached_boot:
            global _latest_caption, _last_positive_caption_time
            src = str(cached_boot.get("source") or "cache")
            _latest_caption = caption_with_source_tag(
                str(cached_boot.get("caption") or ""), src
            )
            cached_boot["caption"] = _latest_caption
            _last_positive_caption_time = time.time()
            _publish_crop_analysis(cached_boot, source=src)
            print(f"[hailo] caption cache: {_latest_caption}", flush=True)

        def _cache_heartbeat_loop() -> None:
            while _running:
                time.sleep(45.0)
                if _last_hailo_count > 0:
                    continue
                if time.time() - _last_positive_caption_time < 40.0:
                    continue
                cached = _load_caption_cache()
                if cached:
                    _publish_crop_analysis(
                        cached, source=str(cached.get("source") or "cache")
                    )

        threading.Thread(target=_cache_heartbeat_loop, daemon=True).start()
    else:
        print("[hailo] CAPTION_GEMINI=0 — YOLO/Hailo 검출만 자막·MQTT", flush=True)

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
