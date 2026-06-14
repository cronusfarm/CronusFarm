#!/usr/bin/env python3
import json
import urllib.parse
import urllib.request
from pathlib import Path

key = ""
for line in Path("/etc/cronusfarm/nodered-telegram.env").read_text().splitlines():
    if line.startswith("CRONUSFARM_GEMINI_API_KEY="):
        key = line.split("=", 1)[1].strip()
url = "https://generativelanguage.googleapis.com/v1beta/models?key=" + urllib.parse.quote(key)
with urllib.request.urlopen(url, timeout=30) as r:
    data = json.loads(r.read())
for m in data.get("models", []):
    name = m.get("name", "").replace("models/", "")
    methods = m.get("supportedGenerationMethods", [])
    if "generateContent" in methods:
        print(name)
