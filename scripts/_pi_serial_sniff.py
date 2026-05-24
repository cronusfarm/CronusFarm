#!/usr/bin/env python3
import serial
import sys
import time

port = sys.argv[1] if len(sys.argv) > 1 else "/dev/ttyACM1"
sec = float(sys.argv[2]) if len(sys.argv) > 2 else 35.0
ser = serial.Serial(port, 115200, timeout=0.3)
t0 = time.time()
while time.time() - t0 < sec:
    raw = ser.readline()
    if raw:
        print(raw.decode("utf-8", errors="replace").rstrip())
ser.close()
