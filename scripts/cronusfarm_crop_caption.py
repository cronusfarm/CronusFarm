#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""카메라 검출 → 자막(작물명·식물 수·잎 수) 공통 포맷."""
from __future__ import annotations

import json
import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any

# Hailo/YOLO 클래스 키 → 한글 작물명
KO_CROP_MAP: dict[str, str] = {
    "tomato": "토마토",
    "fig": "무화과",
    "butterhead": "버터헤드",
    "basil": "바질",
    "cherry_tomato": "방울토마토",
    "unlabeled": "미분류",
}

# Gemini 한글 응답 → 내부 라벨
_KO_NAME_TO_LABEL: dict[str, str] = {
    "토마토": "tomato",
    "방울토마토": "tomato",
    "무화과": "fig",
    "버터헤드": "butterhead",
    "바질": "basil",
    "tomato": "tomato",
    "fig": "fig",
    "butterhead": "butterhead",
    "basil": "basil",
}

GEMINI_CROP_PROMPT = (
    "온실 카메라 사진만 보고 JSON 한 줄만 출력하세요. 다른 설명 금지.\n"
    '{"crop_name":"토마토|무화과|버터헤드|바질|없음","crop_count":정수,"leaf_count":정수}\n'
    "crop_count=식물/화분(포트) 수.\n"
    "leaf_count=해당 작물의 잎 **매수**(큰 잎·작은 잎·어린 잎·새순까지, "
    "잎 윤곽·잎맥이 구분되면 1매로 센다. 군락·덩어리 수가 아님).\n"
    "여러 작물이 함께 보이면 crop_name에 「토마토·무화과」처럼 · 로 구분.\n"
    "화분·토양·배경은 작물로 세지 말 것. 잎이 보이는 작물만.\n"
    "과소 추정하지 말 것 — 작은 잎을 빼먹지 말 것."
)


def caption_with_source_tag(caption: str, source: str = "") -> str:
    """자막 출처 표시 — Gemini만 (AI추정), YOLO/Hailo는 접미사 없음."""
    cap = (caption or "").strip()
    if not cap or "(AI추정)" in cap or "(YOLO" in cap:
        return cap
    if source in ("gemini_caption", "cache", "manual_push", "manual_set"):
        return f"{cap} (AI추정)"
    return cap


def gemini_crop_prompt() -> str:
    """환경변수 힌트(주 작물)를 프롬프트에 추가."""
    import os

    hint = (os.environ.get("CRONUSFARM_CAPTION_CROP_HINT") or "").strip()
    if not hint:
        return GEMINI_CROP_PROMPT
    return (
        GEMINI_CROP_PROMPT
        + f"\n[현장 힌트] 이 침대/화면의 주 작물은 「{hint}」. "
        f"유사 엽채(상추·버터헤드 등)와 혼동 시 crop_name={hint} 우선."
    )


# 클래스별 최소 conf — 표시·MQTT·필터 공통
CROP_MIN_CONF: dict[str, float] = {
    "basil": 0.42,
    "tomato": 0.20,
    "cherry_tomato": 0.20,
    "butterhead": 0.22,
    "fig": 0.22,
}
DEFAULT_CROP_MIN_CONF = 0.18

# BGR — 클래스별 박스 색
CROP_BOX_COLORS_BGR: dict[str, tuple[int, int, int]] = {
    "tomato": (60, 80, 255),
    "cherry_tomato": (40, 120, 255),
    "basil": (80, 200, 40),
    "fig": (220, 100, 255),
    "butterhead": (80, 220, 255),
    "unlabeled": (160, 160, 160),
}


@dataclass
class CropDet:
    """검출 1건 — 정규화 라벨·신뢰도·박스(0~1, xmin/ymin/w/h)."""

    label: str
    conf: float = 1.0
    cx: float | None = None
    cy: float | None = None
    xmin: float | None = None
    ymin: float | None = None
    w: float | None = None
    h: float | None = None


def _box_area_ratio(d: CropDet) -> float:
    if d.w is not None and d.h is not None and d.w > 0 and d.h > 0:
        return float(d.w * d.h)
    return 0.0


def filter_crop_dets_for_display(items: list[CropDet]) -> list[CropDet]:
    """잎 단위 박스만 — 화분·거대 오탐·저신뢰 단독 검출 제거."""
    out: list[CropDet] = []
    for d in items:
        if not d.label:
            continue
        min_c = CROP_MIN_CONF.get(d.label, DEFAULT_CROP_MIN_CONF)
        if d.conf < min_c:
            continue
        area = _box_area_ratio(d)
        if area > 0.045:
            continue
        if 0 < area < 0.0015:
            continue
        out.append(d)
    if len(out) == 1 and out[0].conf < 0.28:
        return []
    return out


def _estimate_plant_count(centers: list[tuple[float, float]], thresh: float = 0.14) -> int:
    """박스 중심 거리로 식물(포트/군) 수 추정."""
    if not centers:
        return 0
    groups: list[list[float]] = []
    for cx, cy in centers:
        placed = False
        for g in groups:
            if math.hypot(cx - g[0], cy - g[1]) < thresh:
                g[0] = (g[0] + cx) / 2.0
                g[1] = (g[1] + cy) / 2.0
                placed = True
                break
        if not placed:
            groups.append([cx, cy])
    return len(groups)


def _label_from_ko_name(name: str) -> str | None:
    key = (name or "").strip()
    if not key or key in ("없음", "none", "unknown"):
        return None
    low = key.lower()
    if low in KO_CROP_MAP:
        return low
    return _KO_NAME_TO_LABEL.get(key) or _KO_NAME_TO_LABEL.get(key.replace(" ", ""))


def analysis_from_gemini_crop_json(text: str) -> dict[str, Any] | None:
    """Gemini JSON 응답 → MQTT/자막용 dict (파싱 실패 시 None)."""
    raw = (text or "").strip()
    if not raw:
        return None
    m = re.search(r"\{[\s\S]*\}", raw)
    if not m:
        return None
    try:
        o = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None

    crop_name_ko = "없음"
    crop_count = 0
    leaf_count = 0

    if isinstance(o.get("crops"), list):
        best_n = 0
        for c in o["crops"]:
            if not isinstance(c, dict):
                continue
            nm = str(c.get("name") or "").strip()
            try:
                n = int(c.get("count") or 0)
            except (TypeError, ValueError):
                n = 0
            if n > best_n and nm:
                crop_name_ko = nm
                best_n = n
        crop_count = best_n
        leaf_count = max(crop_count, int(o.get("leaf_count") or 0))
    else:
        crop_name_ko = str(o.get("crop_name") or "없음").strip() or "없음"
        try:
            crop_count = int(o.get("crop_count") or 0)
        except (TypeError, ValueError):
            crop_count = 0
        try:
            leaf_count = int(o.get("leaf_count") or 0)
        except (TypeError, ValueError):
            leaf_count = 0

    if crop_name_ko in ("없음", "none") or crop_count <= 0:
        return analyze_crop_detections([], ko_map=KO_CROP_MAP)

    label = _label_from_ko_name(crop_name_ko)
    if not label:
        caption = f"작물: {crop_name_ko} | 개수: {crop_count} | 잎: {leaf_count or crop_count}"
        return {
            "count": leaf_count or crop_count,
            "crop_name": crop_name_ko,
            "crop_count": crop_count,
            "leaf_count": leaf_count or crop_count,
            "caption": caption,
        }

    leaf_n = max(leaf_count, crop_count) if leaf_count > 0 else crop_count
    items = [CropDet(label=label, conf=1.0) for _ in range(max(leaf_n, 1))]
    analysis = analyze_crop_detections(items, ko_map=KO_CROP_MAP)
    # Gemini가 준 식물·잎 수를 우선(클러스터·박스 수보다 현장에 맞음)
    analysis["crop_count"] = crop_count
    analysis["leaf_count"] = leaf_n
    analysis["count"] = leaf_n
    analysis["crop_name"] = KO_CROP_MAP.get(label, crop_name_ko)
    analysis["caption"] = (
        f"작물: {analysis['crop_name']} | 개수: {crop_count} | 잎: {leaf_n}"
    )
    return analysis


def analyze_crop_detections(
    items: list[CropDet],
    *,
    ko_map: dict[str, str] | None = None,
) -> dict[str, Any]:
    """
    검출 목록 → MQTT/자막용 dict.
    - leaf_count: 검출 박스 수(잎·유묘 단위)
    - crop_count: 중심 클러스터 수(식물/포트 추정)
    - crop_name: 최빈 작물 한글명
    """
    km = ko_map or KO_CROP_MAP
    labels = [d.label for d in items if d.label]
    leaf_count = len(labels)
    if leaf_count == 0:
        return {
            "count": 0,
            "crop_name": "없음",
            "crop_count": 0,
            "leaf_count": 0,
            "caption": "작물: 없음 | 개수: 0 | 잎: 0",
        }

    ctr = Counter(labels)
    top_key = ctr.most_common(1)[0][0]
    if len(ctr) > 1:
        crop_name = "·".join(km.get(k, k) for k, _ in ctr.most_common(3))
    else:
        crop_name = km.get(top_key, top_key)
    centers = [
        (d.cx, d.cy)
        for d in items
        if d.cx is not None and d.cy is not None and d.label
    ]
    crop_count = _estimate_plant_count(centers) if centers else 1
    caption = f"작물: {crop_name} | 개수: {crop_count} | 잎: {leaf_count}"
    return {
        "count": leaf_count,
        "crop_name": crop_name,
        "crop_count": crop_count,
        "leaf_count": leaf_count,
        "caption": caption,
    }


def hailo_det_to_crop_det(d: Any, normalize) -> CropDet | None:
    """Hailo Detection → CropDet (normalize: (raw, conf) -> label|None)."""
    try:
        raw = str(d.get_label())
        conf = float(d.get_confidence()) if hasattr(d, "get_confidence") else 1.0
        label = normalize(raw, conf)
        if not label:
            return None
        cx = cy = None
        if hasattr(d, "get_bbox"):
            b = d.get_bbox()
            if callable(getattr(b, "xmin", None)):
                xmin = float(b.xmin())
                ymin = float(b.ymin())
                w = float(b.width())
                h = float(b.height())
            else:
                xmin = float(b.xmin)
                ymin = float(b.ymin)
                w = float(b.width)
                h = float(b.height)
            cx = xmin + w / 2.0
            cy = ymin + h / 2.0
        return CropDet(
            label=label,
            conf=conf,
            cx=cx,
            cy=cy,
            xmin=xmin,
            ymin=ymin,
            w=w,
            h=h,
        )
    except Exception:
        return None


def draw_detection_boxes_on_bgr(
    bgr: Any,
    items: list[CropDet],
    ko_map: dict[str, str] | None = None,
) -> Any:
    """검출 대상(클래스)마다 다른 색 박스·라벨."""
    import cv2

    km = ko_map or KO_CROP_MAP
    if not items:
        return bgr
    img_h, img_w = bgr.shape[:2]

    def _xyxy(d: CropDet) -> tuple[int, int, int, int] | None:
        if d.xmin is not None and d.ymin is not None and d.w is not None and d.h is not None:
            x1 = int(max(0, min(img_w - 1, d.xmin * img_w)))
            y1 = int(max(0, min(img_h - 1, d.ymin * img_h)))
            x2 = int(max(0, min(img_w - 1, (d.xmin + d.w) * img_w)))
            y2 = int(max(0, min(img_h - 1, (d.ymin + d.h) * img_h)))
            if x2 > x1 and y2 > y1:
                return x1, y1, x2, y2
        if d.cx is not None and d.cy is not None:
            side = max(24, int(min(img_w, img_h) * 0.08))
            cx = int(d.cx * img_w)
            cy = int(d.cy * img_h)
            return (
                max(0, cx - side // 2),
                max(0, cy - side // 2),
                min(img_w - 1, cx + side // 2),
                min(img_h - 1, cy + side // 2),
            )
        return None

    for d in items:
        box = _xyxy(d)
        if not box:
            continue
        x1, y1, x2, y2 = box
        color = CROP_BOX_COLORS_BGR.get(d.label, (0, 255, 255))
        cv2.rectangle(bgr, (x1, y1), (x2, y2), color, 3, cv2.LINE_AA)
        name = km.get(d.label, d.label)
        tag = f"{name} {d.conf:.0%}" if d.conf < 0.999 else name
        ty = max(14, y1 - 6)
        cv2.putText(
            bgr,
            tag[:24],
            (x1, ty),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.48,
            color,
            2,
            cv2.LINE_AA,
        )
    return bgr


def draw_subtitle_on_bgr(bgr: Any, text: str) -> Any:
    """영상 하단 자막(한글). PIL·한글 폰트 없으면 OpenCV ASCII 폴백."""
    import cv2
    import numpy as np

    cap = (text or "").strip()
    if not cap:
        return bgr
    h, w = bgr.shape[:2]
    try:
        from PIL import Image, ImageDraw, ImageFont

        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        pil = Image.fromarray(rgb)
        draw = ImageDraw.Draw(pil)
        font = None
        for fp in (
            "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ):
            try:
                from pathlib import Path

                if Path(fp).is_file():
                    font = ImageFont.truetype(fp, 20)
                    break
            except OSError:
                continue
        if font is None:
            font = ImageFont.load_default()
        draw.rectangle((0, h - 42, w, h), fill=(0, 0, 0))
        draw.text((8, h - 36), cap[:90], font=font, fill=(220, 255, 220))
        return cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)
    except Exception:
        bar = cap.encode("ascii", "ignore").decode("ascii") or "crop stats"
        cv2.rectangle(bgr, (0, h - 44), (w, h), (0, 0, 0), -1)
        cv2.putText(
            bgr,
            bar[:72],
            (8, h - 12),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.52,
            (220, 255, 220),
            2,
            cv2.LINE_AA,
        )
        return bgr


def ultralytics_boxes_to_crop_dets(
    boxes: Any, names: dict[int, str], normalize
) -> list[CropDet]:
    """Ultralytics result.boxes → CropDet 목록."""
    out: list[CropDet] = []
    if boxes is None or len(boxes) == 0:
        return out
    xywhn = getattr(boxes, "xywhn", None)
    for i, c in enumerate(boxes.cls):
        conf = float(boxes.conf[i].item()) if hasattr(boxes, "conf") else 1.0
        raw = str(names.get(int(c.item()), int(c.item())))
        label = normalize(raw, conf)
        if not label:
            continue
        cx = cy = xmin = ymin = bw = bh = None
        if xywhn is not None and len(xywhn) > i:
            row = xywhn[i]
            cx = float(row[0].item())
            cy = float(row[1].item())
            bw = float(row[2].item())
            bh = float(row[3].item())
            xmin = cx - bw / 2.0
            ymin = cy - bh / 2.0
        out.append(
            CropDet(
                label=label,
                conf=conf,
                cx=cx,
                cy=cy,
                xmin=xmin,
                ymin=ymin,
                w=bw,
                h=bh,
            )
        )
    return out
