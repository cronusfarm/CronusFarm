#!/usr/bin/env python3
"""
CronusFarm CCTV 캡처 데몬

- 사진은 파일로 저장: /mnt/usb/CCTV/cam01/YYYY/MM/DD/... (USB 미마운트 시 ~/CronusFarm/CCTV)
- SQLite에는 메타데이터/경로만 저장: cctv_photo
- 촬영 주기는 SQLite settings_kv에서 읽음:
    key: cctv_cam01_interval_min  (정수 분, 예: 60)

환경변수:
  CRONUSFARM_SQLITE_PATH          DB 경로 (기본: ~/.node-red/cronusfarm.sqlite)
  CRONUSFARM_DEVICE_ID            device_id (기본: cronusfarm-01)
  CRONUSFARM_CCTV_BASE_DIR        기본 저장 폴더 (기본: /mnt/usb/CCTV, 없으면 ~/CronusFarm/CCTV)
  CRONUSFARM_CCTV_CAM01_SRC       캡처 소스 (예: RTSP URL). 비어있으면 cam01 캡처는 건너뜀.
  CRONUSFARM_CCTV_INTERVAL_MIN_DEFAULT  settings_kv가 없을 때 기본 분 (기본: 60)

캡처 엔진:
  - ffmpeg가 있으면 ffmpeg로 1프레임 JPEG 저장(권장)
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path


# 브리지/초기화 스크립트 없이 DB 파일만 있을 때도 동작하도록 최소 스키마 보강
_CORE_DDL = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS device (
  device_id TEXT PRIMARY KEY,
  label TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS settings_kv (
  device_id TEXT NOT NULL,
  key TEXT NOT NULL,
  value TEXT NOT NULL,
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  PRIMARY KEY (device_id, key),
  FOREIGN KEY (device_id) REFERENCES device(device_id)
);
"""

_CCTV_DDL = """
CREATE TABLE IF NOT EXISTS cctv_photo (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  device_id TEXT NOT NULL,
  camera_key TEXT NOT NULL,
  captured_at_ms INTEGER NOT NULL,
  rel_path TEXT NOT NULL,
  bytes INTEGER,
  sha256 TEXT,
  width INTEGER,
  height INTEGER,
  meta_json TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_cctv_photo_dev_cam_ts ON cctv_photo(device_id, camera_key, captured_at_ms DESC);
CREATE UNIQUE INDEX IF NOT EXISTS uq_cctv_photo_rel_path ON cctv_photo(rel_path);
"""


def _home_expand(p: str) -> Path:
    return Path(p).expanduser().resolve()


def _default_cctv_base_dir() -> Path:
    """USB 마운트 우선, 없으면 홈 폴백."""
    for candidate in ("/mnt/usb/CCTV", "~/CronusFarm/CCTV"):
        p = _home_expand(candidate)
        try:
            p.mkdir(parents=True, exist_ok=True)
            return p
        except OSError:
            continue
    return _home_expand("~/CronusFarm/CCTV")


def _env_int(name: str, default: int) -> int:
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            b = f.read(1024 * 1024)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def _mkdirs(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _now_kst_tuple(ts_ms: int) -> tuple[str, str, str, str, str]:
    # KST 고정(UTC+9). Pi timezone이 바뀌어도 “정각” UI 기대가 흔들리지 않게 고정.
    # (원하면 향후 설정으로 timezone 반영 가능)
    sec = ts_ms // 1000
    kst = time.gmtime(sec + 9 * 60 * 60)
    y = f"{kst.tm_year:04d}"
    mo = f"{kst.tm_mon:02d}"
    d = f"{kst.tm_mday:02d}"
    hh = f"{kst.tm_hour:02d}"
    mm = f"{kst.tm_min:02d}"
    ss = f"{kst.tm_sec:02d}"
    return y, mo, d, f"{y}{mo}{d}_{hh}{mm}{ss}", f"{hh}{mm}{ss}"


@dataclass(frozen=True)
class CamCfg:
    camera_key: str
    src: str
    interval_min_key: str


def _read_kv_int(conn: sqlite3.Connection, *, device_id: str, key: str) -> int | None:
    cur = conn.cursor()
    cur.execute(
        "SELECT value FROM settings_kv WHERE device_id=? AND key=?",
        (device_id, key),
    )
    row = cur.fetchone()
    if not row:
        return None
    v = str(row[0]).strip()
    try:
        return int(float(v))
    except ValueError:
        return None


def _ffmpeg_capture_jpeg(*, src: str, out_path: Path, timeout_s: int = 20) -> bool:
    exe = shutil.which("ffmpeg")
    if not exe:
        return False
    src = (src or "").strip()
    # -y: overwrite, -frames:v 1: 1 frame
    # 입력은 2종 지원:
    # - RTSP: rtsp://...
    # - USB 카메라(V4L2): /dev/video0 같은 디바이스 경로
    if src.startswith("/dev/video"):
        args = [
            exe,
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "v4l2",
            "-i",
            src,
            "-frames:v",
            "1",
            "-q:v",
            "3",
            "-y",
            str(out_path),
        ]
    else:
        # RTSP 안정성: tcp 우선
        args = [
            exe,
            "-hide_banner",
            "-loglevel",
            "error",
            "-rtsp_transport",
            "tcp",
            "-i",
            src,
            "-frames:v",
            "1",
            "-q:v",
            "3",
            "-y",
            str(out_path),
        ]
    try:
        r = subprocess.run(args, capture_output=True, timeout=timeout_s, check=False)
        ok = r.returncode == 0 and out_path.exists() and out_path.stat().st_size > 0
        if not ok:
            # 서비스(journalctl)에서 원인 확인 가능하도록 stderr 일부를 남긴다.
            err = (r.stderr or b"").decode("utf-8", errors="replace").strip()
            msg = f"[cctv] ffmpeg failed rc={r.returncode} src={src} err={err[:400]}"
            print(msg, flush=True)
        return ok
    except (OSError, subprocess.TimeoutExpired):
        print(f"[cctv] ffmpeg timeout/error src={src}", flush=True)
        return False


def _curl_capture_jpeg(*, url: str, out_path: Path, timeout_s: int = 10) -> bool:
    exe = shutil.which("curl")
    if not exe:
        return False
    args = [
        exe,
        "-fsSL",
        "--max-time",
        str(int(timeout_s)),
        "-o",
        str(out_path),
        url,
    ]
    try:
        r = subprocess.run(args, capture_output=True, timeout=timeout_s + 2, check=False)
        ok = r.returncode == 0 and out_path.exists() and out_path.stat().st_size > 0
        if not ok:
            err = (r.stderr or b"").decode("utf-8", errors="replace").strip()
            print(f"[cctv] curl failed rc={r.returncode} url={url} err={err[:400]}", flush=True)
        return ok
    except (OSError, subprocess.TimeoutExpired):
        print(f"[cctv] curl timeout/error url={url}", flush=True)
        return False


def _ensure_db(conn: sqlite3.Connection, *, device_id: str) -> None:
    conn.executescript(_CORE_DDL + _CCTV_DDL)
    conn.execute(
        "INSERT OR IGNORE INTO device (device_id, label) VALUES (?, ?)",
        (device_id, device_id),
    )
    conn.commit()


def _insert_photo(
    conn: sqlite3.Connection,
    *,
    device_id: str,
    camera_key: str,
    captured_at_ms: int,
    rel_path: str,
    bytes_size: int | None,
    sha256: str | None,
    width: int | None = None,
    height: int | None = None,
    meta: dict | None = None,
) -> None:
    conn.execute(
        """
        INSERT OR IGNORE INTO cctv_photo
          (device_id, camera_key, captured_at_ms, rel_path, bytes, sha256, width, height, meta_json)
        VALUES
          (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            device_id,
            camera_key,
            int(captured_at_ms),
            rel_path,
            bytes_size,
            sha256,
            width,
            height,
            (json.dumps(meta, ensure_ascii=False) if meta else None),
        ),
    )
    conn.commit()


def _capture_once(
    conn: sqlite3.Connection,
    *,
    device_id: str,
    base_dir: Path,
    cam: CamCfg,
) -> None:
    if not cam.src.strip():
        return

    ts_ms = int(time.time() * 1000)
    y, mo, d, stamp, _ = _now_kst_tuple(ts_ms)

    # 경로: {base}/cam01/YYYY/MM/DD/YYYYMMDD_HHMMSS.jpg (base 기본 /mnt/usb/CCTV)
    rel_dir = Path(cam.camera_key) / y / mo / d
    out_dir = base_dir / rel_dir
    _mkdirs(out_dir)
    fname = f"{stamp}.jpg"
    out_path = out_dir / fname
    rel_path = str((rel_dir / fname).as_posix())

    src = (cam.src or "").strip()
    if src.startswith("http://") or src.startswith("https://"):
        ok = _curl_capture_jpeg(url=src, out_path=out_path)
    else:
        ok = _ffmpeg_capture_jpeg(src=src, out_path=out_path)
    if not ok:
        # 캡처 실패 시 파일이 남아있으면 제거(반쪽 파일 방지)
        try:
            if out_path.exists() and out_path.stat().st_size == 0:
                out_path.unlink()
        except OSError:
            pass
        return

    st = out_path.stat()
    sha = _sha256_file(out_path)
    print(f"[cctv] captured {rel_path} bytes={st.st_size}", flush=True)

    # 최신 파일: 고정 URL 용(/cctv/cam01/latest.jpg). exFAT USB는 symlink 불가 → 파일 복사.
    try:
        latest_dir = base_dir / cam.camera_key
        _mkdirs(latest_dir)
        latest_path = latest_dir / "latest.jpg"
        tmp_path = latest_dir / ".latest.jpg.tmp"
        try:
            if tmp_path.exists():
                tmp_path.unlink()
        except OSError:
            pass
        try:
            os.symlink(out_path, tmp_path)
            os.replace(tmp_path, latest_path)
        except OSError:
            shutil.copy2(out_path, tmp_path)
            os.replace(tmp_path, latest_path)
    except OSError as e:
        print(f"[cctv] latest.jpg update failed: {e}", flush=True)

    _insert_photo(
        conn,
        device_id=device_id,
        camera_key=cam.camera_key,
        captured_at_ms=ts_ms,
        rel_path=rel_path,
        bytes_size=int(st.st_size),
        sha256=sha,
        meta={"engine": "ffmpeg", "src": cam.src},
    )


def _sleep_until(ts_target: float) -> None:
    while True:
        now = time.time()
        dt = ts_target - now
        if dt <= 0:
            return
        time.sleep(min(dt, 1.0))


def _main_loop() -> int:
    db_path = _home_expand(os.environ.get("CRONUSFARM_SQLITE_PATH", "~/.node-red/cronusfarm.sqlite"))
    device_id = (os.environ.get("CRONUSFARM_DEVICE_ID") or "cronusfarm-01").strip() or "cronusfarm-01"
    raw_base = (os.environ.get("CRONUSFARM_CCTV_BASE_DIR") or "").strip()
    base_dir = _home_expand(raw_base) if raw_base else _default_cctv_base_dir()
    default_min = _env_int("CRONUSFARM_CCTV_INTERVAL_MIN_DEFAULT", 60)

    cams = [
        CamCfg(
            camera_key="cam01",
            src=os.environ.get("CRONUSFARM_CCTV_CAM01_SRC", "") or "",
            interval_min_key="cctv_cam01_interval_min",
        ),
    ]

    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    try:
        _ensure_db(conn, device_id=device_id)
        # 루프: 각 cam의 interval을 읽고, 다음 촬영 시각을 계산해서 sleep
        next_due: dict[str, float] = {}
        while True:
            now = time.time()
            soonest = now + 3600.0

            for cam in cams:
                # interval 분 읽기(없으면 default)
                v = _read_kv_int(conn, device_id=device_id, key=cam.interval_min_key)
                interval_min = v if (v is not None and v > 0) else default_min
                interval_s = max(60, int(interval_min) * 60)  # 너무 짧은 쓰기 폭주 방지(최소 60초)

                due = next_due.get(cam.camera_key)
                if due is None:
                    # 첫 실행: 즉시 1회 캡처 후 interval 기반으로 반복
                    due = now
                    next_due[cam.camera_key] = due

                # due 도달 시 촬영 후 다음 due 갱신
                if now >= due:
                    _capture_once(conn, device_id=device_id, base_dir=base_dir, cam=cam)
                    next_due[cam.camera_key] = now + interval_s
                    due = next_due[cam.camera_key]

                soonest = min(soonest, float(due))

            _sleep_until(soonest)
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(_main_loop())

