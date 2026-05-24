#!/usr/bin/env python3
"""모든 클래스 conf 점수 덤프 — fig/basil 오분류 진단."""
import cv2
import numpy as np

URL = "http://127.0.0.1:8080/stream"
ONNX = "/home/dooly/CronusFarm/Hailo/best.onnx"
LABELS = ["tomato", "fig", "butterhead", "basil"]


def letterbox(bgr, size=640):
    h, w = bgr.shape[:2]
    scale = min(size / h, size / w)
    nh, nw = int(round(h * scale)), int(round(w * scale))
    resized = cv2.resize(bgr, (nw, nh), interpolation=cv2.INTER_LINEAR)
    out = np.zeros((size, size, 3), dtype=bgr.dtype)
    top, left = (size - nh) // 2, (size - nw) // 2
    out[top : top + nh, left : left + nw] = resized
    return out


def main():
    from ultralytics import YOLO

    model = YOLO(ONNX)
    cap = cv2.VideoCapture(URL)
    for i in range(10):
        ok, frame = cap.read()
        if not ok:
            print(i, "no frame")
            continue
        lb = letterbox(frame)
        r = model.predict(lb, conf=0.04, verbose=False)[0]
        boxes = r.boxes
        if boxes is None or len(boxes) == 0:
            print(i, "none")
            continue
        parts = []
        for b in boxes:
            cls = int(b.cls[0])
            name = LABELS[cls] if cls < len(LABELS) else str(cls)
            parts.append(f"{name}={float(b.conf[0]):.3f}")
        print(i, ", ".join(parts))
    cap.release()


if __name__ == "__main__":
    main()
