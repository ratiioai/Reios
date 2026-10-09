"""Polls the public URL and nginx every 5 s for the whole test session; one CSV row per check."""
import csv
import sys
import time
from datetime import datetime
from pathlib import Path

import httpx

PUBLIC = Path(r"C:\reios-server\PUBLIC_URL.txt").read_text().strip()
OUT = Path(r"C:\reios-server\qa\results\availability.csv")
OUT.parent.mkdir(parents=True, exist_ok=True)
targets = {"public": PUBLIC + "/api/health", "nginx": "http://127.0.0.1:8080/api/health"}

with OUT.open("a", newline="") as f:
    w = csv.writer(f)
    if f.tell() == 0:
        w.writerow(["time", "target", "ok", "status", "ms"])
    while True:
        for name, url in targets.items():
            t = time.perf_counter()
            try:
                r = httpx.get(url, timeout=10)
                ok, status = r.status_code == 200, r.status_code
            except Exception as e:
                ok, status = False, type(e).__name__
            w.writerow([datetime.now().isoformat(timespec="seconds"), name, int(ok), status,
                        round((time.perf_counter() - t) * 1000)])
        f.flush()
        if Path(r"C:\reios-server\qa\STOP_MONITOR").exists():
            break
        time.sleep(5)
