#!/usr/bin/env python3
import cv2

url = "http://127.0.0.1:8080/stream"
cap = cv2.VideoCapture(url)
print("open", cap.isOpened())
ok, frame = cap.read()
print("read", ok, frame.shape if ok else None)
