import json
from pathlib import Path

d = json.loads(Path("nodered/flows_cronusfarm_dashboard.json").read_text(encoding="utf-8"))
out = []
for n in d:
    t = n.get("type", "")
    if t == "ui-template":
        g = n.get("group", "")
        fmt = n.get("format") or ""
        out.append(
            {
                "id": n["id"],
                "name": n.get("name", ""),
                "group": g,
                "format_len": len(fmt),
                "has_vue": "{{" in fmt or "v-" in fmt or "vuetify" in fmt.lower(),
                "has_fetch": "fetch(" in fmt,
            }
        )
Path("_nrdb2_inv.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
print("wrote", len(out), "ui-template nodes")
