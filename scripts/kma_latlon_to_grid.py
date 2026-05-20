#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""WGS84 위·경도 → 기상청 초단기 격자(nx, ny). Lambert Conformal (동네예보 격자)."""
from __future__ import annotations

import math


def latlon_to_grid(lat: float, lon: float) -> tuple[int, int]:
    re = 6371.00877 / 5.0  # Earth radius km / grid km
    grid = 5.0
    slat1 = 30.0
    slat2 = 60.0
    olon = 126.0
    olat = 38.0
    xo = 43
    yo = 136

    dlat = slat2 - slat1
    sn = math.tan(math.pi * 0.25 + slat2 * math.radians(0.5)) / math.tan(
        math.pi * 0.25 + slat1 * math.radians(0.5)
    )
    sn = math.log(sn) / math.log(math.tan(math.pi * 0.25 + slat1 * math.radians(0.5)))
    if abs(slat1 - slat2) > 1e-6:
        sn = math.log(
            math.cos(math.radians(slat1)) / math.cos(math.radians(slat2))
        ) / math.log(
            math.tan(math.pi * 0.25 + slat2 * math.radians(0.5))
            / math.tan(math.pi * 0.25 + slat1 * math.radians(0.5))
        )
    sf = math.tan(math.pi * 0.25 + slat1 * math.radians(0.5)) ** sn
    sf = math.cos(math.radians(slat1)) * sf / sn
    ro = (
        re
        * sf
        / math.tan(math.pi * 0.25 + olat * math.radians(0.5)) ** sn
    )
    ra = (
        re
        * sf
        / math.tan(math.pi * 0.25 + lat * math.radians(0.5)) ** sn
    )
    theta = lon * math.radians(1.0) - olon * math.radians(1.0)
    x = ra * math.sin(theta) + xo
    y = ro - ra * math.cos(theta) + yo
    nx = int(x + 1.5)
    ny = int(y + 1.5)
    return nx, ny


if __name__ == "__main__":
    import sys

    lat = float(sys.argv[1])
    lon = float(sys.argv[2])
    nx, ny = latlon_to_grid(lat, lon)
    print(f"lat={lat} lon={lon} -> nx={nx} ny={ny}")
