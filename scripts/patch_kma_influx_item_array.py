import json

path = r"d:\WorkSpace\Study\MyCode\Cursor\CronusFarm\nodered\merged-deploy.json"
with open(path, encoding="utf-8") as f:
    d = json.load(f)
node = next(x for x in d if x.get("id") == "fn_kma_to_influx")
old = (
    "const items = body?.response?.body?.items?.item;\n"
    "if (!Array.isArray(items)) {\n"
    "  node.warn('KMA: items 없음/형식 불일치');\n"
    "  return null;\n"
    "}\n"
)
new = (
    "let items = body?.response?.body?.items?.item;\n"
    "if (items == null) {\n"
    "  node.warn('KMA: items 없음');\n"
    "  return null;\n"
    "}\n"
    "if (!Array.isArray(items)) {\n"
    "  items = [items];\n"
    "}\n"
)
if old not in node["func"]:
    raise SystemExit("OLD_SNIPPET_NOT_FOUND:\n" + repr(node["func"][400:900]))
node["func"] = node["func"].replace(old, new, 1)
with open(path, "w", encoding="utf-8") as f:
    json.dump(d, f, ensure_ascii=False, indent=2)
print("patched fn_kma_to_influx item array normalization")
