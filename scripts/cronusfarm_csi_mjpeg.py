#!/usr/bin/env python3
"""
CronusFarm CSI 카메라(imx219 cam0) MJPEG HTTP 스트림.

USB ustreamer(:8080) + Hailo(:8081)와 병행. CSI는 libcamera/Picamera2 전용.
환경변수:
  CRONUSFARM_CSI_HTTP_PORT  기본 8082
  CRONUSFARM_CSI_WIDTH      기본 640
  CRONUSFARM_CSI_HEIGHT     기본 480
  CRONUSFARM_CSI_FPS        기본 15
"""

from __future__ import annotations

import os
import threading
from http import server
from io import BufferedIOBase
from socketserver import ThreadingMixIn
from threading import Condition

from picamera2 import Picamera2
from picamera2.encoders import JpegEncoder
from picamera2.outputs import FileOutput

PORT = int(os.environ.get("CRONUSFARM_CSI_HTTP_PORT", "8082"))
WIDTH = int(os.environ.get("CRONUSFARM_CSI_WIDTH", "640"))
HEIGHT = int(os.environ.get("CRONUSFARM_CSI_HEIGHT", "480"))
FPS = int(os.environ.get("CRONUSFARM_CSI_FPS", "15"))


class StreamingOutput(BufferedIOBase):
    """JPEG 프레임 버퍼 — 인코더가 쓰고 HTTP 핸들러가 읽음."""

    def __init__(self) -> None:
        self._frame: bytes | None = None
        self._condition = Condition()

    def write(self, buf: bytes) -> int:
        with self._condition:
            self._frame = buf
            self._condition.notify_all()
        return len(buf)

    def read_frame(self) -> bytes:
        with self._condition:
            while self._frame is None:
                self._condition.wait()
            return self._frame


class MjpegHandler(server.BaseHTTPRequestHandler):
    output: StreamingOutput

    def _path_ok(self) -> bool:
        p = (self.path or "").split("?", 1)[0]
        return p in ("/", "/video_feed", "/stream")

    def do_HEAD(self) -> None:
        if not self._path_ok():
            self.send_error(404)
            return
        self.send_response(200)
        if (self.path or "").split("?", 1)[0] == "/":
            self.send_header("Content-Type", "text/html; charset=utf-8")
        else:
            self.send_header("Age", "0")
            self.send_header("Cache-Control", "no-cache, private")
            self.send_header("Pragma", "no-cache")
            self.send_header(
                "Content-Type", "multipart/x-mixed-replace; boundary=FRAME"
            )
        self.end_headers()

    def do_GET(self) -> None:
        if not self._path_ok():
            self.send_error(404)
            return
        if (self.path or "").split("?", 1)[0] == "/":
            body = b"<h1>CronusFarm CSI (imx219)</h1><img src='/video_feed'>"
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        self.send_response(200)
        self.send_header("Age", "0")
        self.send_header("Cache-Control", "no-cache, private")
        self.send_header("Pragma", "no-cache")
        self.send_header(
            "Content-Type", "multipart/x-mixed-replace; boundary=FRAME"
        )
        self.end_headers()
        try:
            while True:
                frame = self.output.read_frame()
                self.wfile.write(b"--FRAME\r\n")
                self.wfile.write(b"Content-Type: image/jpeg\r\n")
                self.wfile.write(
                    b"Content-Length: " + str(len(frame)).encode() + b"\r\n\r\n"
                )
                self.wfile.write(frame)
                self.wfile.write(b"\r\n")
        except (BrokenPipeError, ConnectionResetError):
            pass

    def log_message(self, fmt: str, *args) -> None:
        print(f"[csi-mjpeg] {self.address_string()} {fmt % args}", flush=True)


class ThreadedHTTPServer(ThreadingMixIn, server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def _run_camera(output: StreamingOutput) -> None:
    picam2 = Picamera2()
    cfg = picam2.create_video_configuration(
        main={"size": (WIDTH, HEIGHT), "format": "RGB888"},
        controls={"FrameRate": FPS},
    )
    picam2.configure(cfg)
    picam2.start_recording(JpegEncoder(), FileOutput(output))
    print(
        f"[csi-mjpeg] Picamera2 시작 {WIDTH}x{HEIGHT}@{FPS}fps",
        flush=True,
    )
    threading.Event().wait()


def main() -> None:
    output = StreamingOutput()
    MjpegHandler.output = output

    cam_thread = threading.Thread(target=_run_camera, args=(output,), daemon=True)
    cam_thread.start()

    httpd = ThreadedHTTPServer(("0.0.0.0", PORT), MjpegHandler)
    print(f"[csi-mjpeg] HTTP :{PORT}/video_feed", flush=True)
    httpd.serve_forever()


if __name__ == "__main__":
    main()
