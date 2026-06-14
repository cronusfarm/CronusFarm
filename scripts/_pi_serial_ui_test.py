#!/usr/bin/env python3
"""R4 USB 직접 ui_ cmd 테스트 (serial 데몬 중지 후 실행)."""
import sys
import time

import serial

port = sys.argv[1] if len(sys.argv) > 1 else "/dev/ttyACM2"
cmd = sys.argv[2] if len(sys.argv) > 2 else "ui_led_a1=1"

ser = serial.Serial(port, 115200, timeout=3)
time.sleep(0.5)
ser.reset_input_buffer()
ser.write((cmd.strip() + "\n").encode())
ser.flush()
time.sleep(2.5)
while ser.in_waiting:
    line = ser.readline().decode(errors="replace").rstrip()
    if line:
        print(line)
ser.close()
