#!/usr/bin/env python3
"""best.hef 출력 텐서·후처리 힌트 (Pi에서 실행)."""
from __future__ import annotations

import sys
from pathlib import Path

hef_path = Path(sys.argv[1] if len(sys.argv) > 1 else "~/CronusFarm/Hailo/best.hef").expanduser()

try:
    from hailo_platform import HEF
except ImportError as e:
    print("hailo_platform import failed:", e)
    sys.exit(1)

hef = HEF(str(hef_path))
print("HEF:", hef_path)
for ng in hef.get_network_group_names():
    print("network_group:", ng)
for info in hef.get_network_groups_infos():
    name = getattr(info, "name", str(info))
    print("ng_info:", name)
    for v in info.get_output_vstream_infos():
        print("  out:", v.name, v.shape, getattr(v, "format", ""))
