"""Load-balancer analysis from nginx's access log: traffic per API instance during each load test."""
import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path

RES = Path(r"C:\reios-server\qa\results")
LINE = re.compile(r'^(\S+) \[(\d+/\w+/\d+):(\d+:\d+:\d+) [^\]]+\] "(\S+) (\S+)[^"]*" (\d{3}) \d+ rt=([\d.]+) urt=(\S+) up=(\S+)')
entries = []
for line in Path(r"C:\reios-server\nginx\logs\access.log").read_text(encoding="utf-8", errors="ignore").splitlines():
    m = LINE.match(line)
    if m and m.group(2).startswith("09/Oct/2026"):
        entries.append({"t": m.group(3), "status": int(m.group(6)), "rt": float(m.group(7)), "up": m.group(9), "path": m.group(5)})

out = {}
for meta in sorted(RES.glob("load_*.meta.json")):
    mt = json.loads(meta.read_text())
    win = [e for e in entries if mt["start"] <= e["t"] <= mt["end"] and e["path"].startswith("/api/")]
    ups = Counter(e["up"].split(",")[0] for e in win if e["up"].startswith("127.0.0.1:80"))
    statuses = Counter(e["status"] for e in win)
    rts = sorted(e["rt"] for e in win) or [0]
    total = sum(ups.values()) or 1
    out[mt["name"]] = {
        "requests": len(win), "per_instance": dict(sorted(ups.items())),
        "share_pct": {k: round(100 * v / total, 1) for k, v in sorted(ups.items())},
        "spread_pct": round(100 * (max(ups.values()) - min(ups.values())) / (total / len(ups)), 1) if ups else None,
        "status": dict(statuses), "nginx_p50_ms": round(rts[len(rts) // 2] * 1000, 1),
        "nginx_p95_ms": round(rts[int(len(rts) * .95)] * 1000, 1), "retried_on_another_instance": sum(1 for e in win if "," in e["up"]),
    }
    print(f"{mt['name']:14} {len(win):6} requests  per instance: {dict(sorted(ups.items()))}  statuses: {dict(statuses)}  "
          f"retried: {out[mt['name']]['retried_on_another_instance']}")
(RES / "lb_analysis.json").write_text(json.dumps(out, indent=1))
