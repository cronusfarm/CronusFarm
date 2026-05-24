#!/usr/bin/env python3
import re
import subprocess
from pathlib import Path

site = Path("/etc/nginx/sites-enabled/cronusfarm-nodered.conf")
text = site.read_text(encoding="utf-8")
fixed, n = re.subn(
    r"(location = /farm/ui \{)\s*return 301 /ui/;",
    r"\1 return 301 /farm/ui/;",
    text,
)
if n:
    site.write_text(fixed, encoding="utf-8")
    print(f"fixed {n} block(s)")
else:
    print("no change needed")
subprocess.run(["nginx", "-t"], check=True)
subprocess.run(["systemctl", "reload", "nginx"], check=True)
