#!/usr/bin/env python3
"""ustreamer 프레임에서 바질 검출 테스트."""
import cv2
import numpy as np
from ultralytics import YOLO

URL = "http://127.0.0.1:8080/stream"
ONNX = "/home/dooly/CronusFarm/Hailo/best.onnx"
LABELS = ["tomato", "fig", "butterhead", "basil"]


def letterbox(bgr: np.ndarray, size: int = 640) -> np.ndarray:
    h, w = bgr.shape[:2]
    scale = min(size / h, size / w)
    nh, nw = int(round(h * scale)), int(round(w * scale))
    resized = cv2.resize(bgr, (nw, nh), interpolation=cv2.INTER_LINEAR)
    out = np.zeros((size, size, 3), dtype=bgr.dtype)
    top = (size - nh) // 2
    left = (size - nw) // 2
    out[top : top + nh, left : left + nw] = resized
    return out


def main() -> None:
    cap = cv2.VideoCapture(URL)
    ok, frame = cap.read()
    cap.release()
    print("frame_ok", ok, "shape", None if not ok else frame.shape)
    if not ok:
        return
    model = YOLO(ONNX)
    for conf in (0.25, 0.1, 0.05, 0.02, 0.01):
        for tag, img in [("raw", frame), ("lb", letterbox(frame))]:
            r = model.predict(img, conf=conf, verbose=False)[0]
            boxes = r.boxes
            n = 0 if boxes is None else len(boxes)
            parts: list[str] = []
            if boxes is not None:
                for b in boxes:
                    cls = int(b.cls[0])
                    name = LABELS[cls] if cls < len(LABELS) else str(cls)
                    parts.append("%s=%.3f" % (name, float(b.conf[0])))
            print("conf=%.2f %s n=%d %s" % (conf, tag, n, ", ".join(parts[:10]) or "-"))


if __name__ == "__main__":
    main()
