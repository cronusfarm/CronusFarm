#!/usr/bin/env python3
import cv2

URL = "http://127.0.0.1:8080/stream"
OUT = "/tmp/ustreamer_snap.jpg"
cap = cv2.VideoCapture(URL)
ok, frame = cap.read()
cap.release()
print("ok", ok, "shape", None if not ok else frame.shape)
if ok:
    cv2.imwrite(OUT, frame)
    print("saved", OUT)
