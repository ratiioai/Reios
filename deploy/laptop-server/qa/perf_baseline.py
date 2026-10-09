import os
"""Single-user latency per request type (local nginx vs public internet path) and page weight."""
import json
import statistics
import time
from pathlib import Path

import httpx

RES = Path(r"C:\reios-server\qa\results")
PUBLIC = Path(r"C:\reios-server\PUBLIC_URL.txt").read_text().strip()
out = {"latency": [], "weight": {}, "payloads": {}}


def timed(c, method, path, n=20, **kw):
    """Paced at ~10 req/s (under nginx's 15/s per-user limit) and only successful replies are timed."""
    xs, r = [], None
    for _ in range(n):
        t = time.perf_counter(); r = c.request(method, path, **kw); ms = (time.perf_counter() - t) * 1000
        if r.status_code == 200:
            xs.append(ms)
        time.sleep(0.1)
    if not xs:
        raise RuntimeError(f"{path}: no successful replies (last status {r.status_code})")
    xs.sort()
    return round(statistics.median(xs), 1), round(xs[max(0, int(0.95 * len(xs)) - 1)], 1), r


for label, base in (("local (nginx)", "http://127.0.0.1:8080"), ("internet (Cloudflare tunnel)", PUBLIC)):
    c = httpx.Client(base_url=base, timeout=30)
    t0 = time.perf_counter()
    adm = c.post("/api/reios/auth/login", json={"identifier": os.environ["QA_ADMIN_EMAIL"], "password": os.environ["QA_ADMIN_PASSWORD"]})
    login_ms = (time.perf_counter() - t0) * 1000
    h = {"Authorization": "Bearer " + adm.json()["access_token"]}
    rows = [("Sign in (bcrypt)", round(login_ms, 1), None)]
    for name, m, p in (("Health check", "GET", "/api/health"), ("Who am I (/auth/me)", "GET", "/api/reios/auth/me"),
                       ("Admin overview stats", "GET", "/api/reios/admin/stats"), ("Teams list (50)", "GET", "/api/reios/admin/students"),
                       ("Exams list", "GET", "/api/reios/admin/exams"), ("Exam results (100 attempts)", "GET", "/api/reios/admin/exams/11/results"),
                       ("Live Monitor (100 attempts)", "GET", "/api/reios/admin/exams/11/live"), ("Leaderboard", "GET", "/api/reios/admin/leaderboard"),
                       ("Website page (index.html)", "GET", "/")):
        med, p95, r = timed(c, m, p, headers=h)
        rows.append((name, med, p95))
    for name, med, p95 in rows:
        out["latency"].append({"path": label, "request": name, "median_ms": med, "p95_ms": p95})
        print(f"{label:30} {name:30} median {med:7.1f} ms   p95 {p95 if p95 is not None else '-':>7} ms")

# page weight of the website (what a participant downloads)
c = httpx.Client(base_url="http://127.0.0.1:8080", timeout=30)
html = c.get("/").text
assets = [s for s in html.split('"') if s.startswith("/assets/")]
raw = gz = 0
for a in assets:
    raw += len(c.get(a).content)
    with c.stream("GET", a, headers={"Accept-Encoding": "gzip"}) as r:
        gz += sum(len(chunk) for chunk in r.iter_raw())   # bytes on the wire, before decompression
out["weight"] = {"first_load_files": len(assets) + 1, "uncompressed_kb": round(raw / 1024), "gzip_kb": round(gz / 1024)}
print("first page load:", out["weight"])

# sign-in response sizes: plain event vs a branded event (logo sent inline)
tst = c.post("/api/reios/auth/login", json={"identifier": "LT001", "password": "Team 001", "college_code": "TST"})
sts = c.post("/api/reios/auth/login", json={"identifier": os.environ["QA_BRANDED_TEAM"], "password": os.environ["QA_BRANDED_TEAM_PASSWORD"], "college_code": os.environ["QA_BRANDED_EVENT"]})
for label, r in (("plain event (TST)", tst), ("branded event (TECHSPRINT)", sts)):
    if r.status_code == 200:
        tok = r.json()["access_token"]
        me = c.get("/api/reios/auth/me", headers={"Authorization": "Bearer " + tok})
        out["payloads"][label] = {"sign_in_kb": round(len(r.content) / 1024, 1), "auth_me_kb": round(len(me.content) / 1024, 1)}
        c.post("/api/reios/auth/logout", headers={"Authorization": "Bearer " + tok})
print("sign-in payloads:", out["payloads"])
(RES / "perf_baseline.json").write_text(json.dumps(out, indent=1))
