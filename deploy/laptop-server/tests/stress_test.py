"""
Stress test: find the breaking point of the whole stack (nginx -> API instances -> PostgreSQL).
Uses aiohttp (a fast client) and spreads traffic over 40 loopback source addresses (127.0.0.10-49),
like 40 separate venues, so the per-IP limit doesn't cap it - the rate limiter is tested separately.

  1. Sign-in storm: every team signs in at the same instant (bcrypt - the most CPU-heavy request).
  2. Answer-save ramp: N teams each save an answer every ~0.1s (about 50x a real person) for 30s.

    tests\\venv\\Scripts\\python stress_test.py <exam_id> <teams> [levels, e.g. 50,100,200,300] [offset]
"""
import asyncio
import json
import os
import random
import sys
import time
from collections import Counter
from pathlib import Path

import aiohttp

BASES = os.environ.get("LT_BASE", "http://127.0.0.1:8080").split(",")
EXAM = int(sys.argv[1])
N = int(sys.argv[2])
LEVELS = [int(x) for x in (sys.argv[3] if len(sys.argv) > 3 else "50,100,200,300").split(",")]
OFFSET = int(sys.argv[4]) if len(sys.argv) > 4 else 0
TEAMS = json.loads(Path(__file__).with_name("loadtest_state.json").read_text())["teams"][OFFSET:OFFSET + N]
SOURCES = 40


def pct(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(p * len(xs)))] if xs else 0


async def main():
    sessions = [aiohttp.ClientSession(
        connector=aiohttp.TCPConnector(limit=0, local_addr=(f"127.0.0.{10 + i}", 0)),
        timeout=aiohttp.ClientTimeout(total=60)) for i in range(SOURCES)]
    ses = lambda i: sessions[i % SOURCES]

    async def call(i, method, path, **kw):
        async with ses(i).request(method, BASES[i % len(BASES)] + path, **kw) as r:
            return r.status, (await r.json(content_type=None) if r.status < 500 else None)

    # 1. sign-in storm
    t0, lat = time.perf_counter(), []

    async def login(i, roll, pw):
        t = time.perf_counter()
        res = await call(i, "POST", "/api/reios/auth/login", json={"identifier": roll, "password": pw, "college_code": "TST"})
        lat.append(time.perf_counter() - t)
        return res

    rs = await asyncio.gather(*[login(i, r, p) for i, (r, p) in enumerate(TEAMS)])
    print(f"1. sign-in storm: {N} at the same instant -> {dict(Counter(s for s, _ in rs))} in "
          f"{time.perf_counter() - t0:.1f}s (median {pct(lat, .5):.2f}s, 95% {pct(lat, .95):.2f}s)")
    tokens = [(i, b["access_token"]) for i, (s, b) in enumerate(rs) if s == 200]

    async def start(i, tk):
        h = {"Authorization": "Bearer " + tk}
        s, p = await call(i, "POST", f"/api/reios/student/exams/{EXAM}/start", headers=h)
        if s != 200:
            return None
        return {"i": i, "h": {**h, "X-Exam-Session": p["session"]}, "aid": p["attempt_id"], "items": p["items"]}

    t0 = time.perf_counter()
    papers = [p for p in await asyncio.gather(*[start(i, tk) for i, tk in tokens]) if p]
    print(f"   {len(papers)} teams pressed Start together -> all inside in {time.perf_counter() - t0:.1f}s")

    print("2. answer-save ramp (each team saves every ~0.1s, 30s per level)")
    print(f"   {'teams':>6} {'saves/s':>8} {'ok':>7} {'errors':>7} {'median':>9} {'95%':>9} {'99%':>9}  error kinds")
    for level in LEVELS:
        if level > len(papers):
            print(f"   (only {len(papers)} teams available, skipping {level})")
            break
        stop = time.perf_counter() + 30
        lat, codes = [], Counter()

        async def hammer(p):
            while time.perf_counter() < stop:
                item = random.choice(p["items"])
                t = time.perf_counter()
                try:
                    s, _ = await call(p["i"], "PUT", f"/api/reios/student/attempts/{p['aid']}/mcq/{item['item_id']}",
                                      headers=p["h"], json={"selected": [random.choice(item["options"])["id"]],
                                                            "marked_for_review": False})
                    codes[s] += 1
                except Exception as e:
                    codes[type(e).__name__] += 1
                lat.append(time.perf_counter() - t)
                await asyncio.sleep(0.1)

        await asyncio.gather(*[hammer(p) for p in papers[:level]])
        ok = codes.get(200, 0)
        errs = sum(v for k, v in codes.items() if k != 200)
        print(f"   {level:6} {(ok + errs) / 30:8.0f} {ok:7} {errs:7} {pct(lat, .5) * 1000:7.0f}ms {pct(lat, .95) * 1000:7.0f}ms "
              f"{pct(lat, .99) * 1000:7.0f}ms  {({k: v for k, v in codes.items() if k != 200}) or ''}")

    for s in sessions:
        await s.close()


asyncio.run(main())
