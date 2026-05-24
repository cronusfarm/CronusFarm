#!/usr/bin/env python3
"""Pi 카메라 프레임 + best.onnx 바질 검출 스모크 테스트."""
import sys

import cv2
import numpy as np

URL = "http://127.0.0.1:8080/stream"
ONNX = "/home/dooly/CronusFarm/Hailo/best.onnx"


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


def main() -> int:
    cap = cv2.VideoCapture(URL)
    ok, frame = cap.read()
    cap.release()
    print("frame", ok, frame.shape if ok else None)
    if not ok:
        return 1
    cv2.imwrite("/tmp/cf_cam.jpg", frame)
    lb = letterbox(frame)
    cv2.imwrite("/tmp/cf_cam_lb.jpg", lb)
    print("saved /tmp/cf_cam.jpg mean", float(frame.mean()))

    try:
        from ultralytics import YOLO

        model = YOLO(ONNX)
        for conf in (0.12, 0.10, 0.08, 0.06, 0.05):
            results = model.predict("/tmp/cf_cam_lb.jpg", conf=conf, verbose=False)
            det = results[0]
            names = det.names
            boxes = det.boxes
            n = len(boxes) if boxes is not None else 0
            print(f"onConfirm lb conf={conf} detections", n)
            if boxes is not None and n:
                for b in boxes[:20]:
                    cls = int(b.cls[0])
                    print(" ", names.get(cls, cls), float(b.conf[0]))
    except Exception as e:
        print("onnx test err", e)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
