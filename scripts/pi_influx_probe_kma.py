#!/usr/bin/env python3
import json
import os
import re
import subprocess
import sys
import urllib.parse
import urllib.request

CONF = "/etc/systemd/system/nodered.service.d/cronusfarm-influx.conf"


def _get_env(conf_text: str, key: str) -> str:
    m = re.search(rf"^Environment={re.escape(key)}=(.*)$", conf_text, re.M)
    return (m.group(1).strip() if m else "")


def main() -> int:
    s = open(CONF, "r", encoding="utf-8").read()
    token = _get_env(s, "CRONUSFARM_INFLUX_TOKEN")
    org = _get_env(s, "CRONUSFARM_INFLUX_ORG")
    bucket = _get_env(s, "CRONUSFARM_INFLUX_BUCKET")
    if not token or not org or not bucket:
        print("missing token/org/bucket", file=sys.stderr)
        return 2
    print("org=", org, " bucket=", bucket, sep="")

    flux = (
        f'from(bucket: "{bucket}")\n'
        "  |> range(start: -48h)\n"
        '  |> filter(fn: (r) => r._measurement == "tele" and r._field == "kma_temp")\n'
        "  |> limit(n: 5)\n"
    )
    url = "http://127.0.0.1:8086/api/v2/query?" + urllib.parse.urlencode({"org": org})
    body = json.dumps({"query": flux, "type": "flux"}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Token {token}",
            "Content-Type": "application/json",
            "Accept": "application/csv",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            out = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        print("HTTP", e.code, file=sys.stderr)
        print(e.read().decode("utf-8", errors="replace")[:500], file=sys.stderr)
        return 1
    print("--- kma_temp sample (csv)")
    print(out[:2000])

    flux2 = (
        f'from(bucket: "{bucket}")\n'
        "  |> range(start: -2h)\n"
        '  |> filter(fn: (r) => r._measurement == "tele")\n'
        "  |> keep(columns: [\"_field\"])\n"
        "  |> distinct(column: \"_field\")\n"
        "  |> sort()\n"
    )
    body2 = json.dumps({"query": flux2, "type": "flux"}).encode("utf-8")
    req2 = urllib.request.Request(
        url,
        data=body2,
        method="POST",
        headers={
            "Authorization": f"Token {token}",
            "Content-Type": "application/json",
            "Accept": "application/csv",
        },
    )
    with urllib.request.urlopen(req2, timeout=30) as resp:
        out2 = resp.read().decode("utf-8", errors="replace")
    print("--- distinct _field in tele (last 2h, truncated)")
    print(out2[:4000])

    # influx CLI sanity (uses INFLUX_TOKEN env)
    env = os.environ.copy()
    env["INFLUX_TOKEN"] = token
    r = subprocess.run(
        ["influx", "bucket", "list", "--org", org, "--json"],
        env=env,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    print("--- influx bucket list rc=", r.returncode, sep="")
    if r.stderr:
        print(r.stderr[:300])
    if r.stdout:
        print(r.stdout[:800])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
