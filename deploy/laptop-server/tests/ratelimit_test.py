"""
Rate-limit checks through nginx (all from one IP, like a venue behind one router):
  1. Password-guessing flood on sign-in      -> must get cut off with 429
  2. One signed-in user flooding the API      -> must get cut off with 429
  3. 150 different teams, same IP, normal use -> must NOT see a single 429
"""
import asyncio
import os
import time
from collections import Counter

import httpx

BASE = os.environ.get("LT_BASE", "http://127.0.0.1:8080")
ADMIN = (os.environ["LT_ADMIN_EMAIL"], os.environ["LT_ADMIN_PASSWORD"])


async def main():
    limits = httpx.Limits(max_connections=400, max_keepalive_connections=400)
    async with httpx.AsyncClient(base_url=BASE, timeout=60, limits=limits) as c:
        # 1. 600 sign-in attempts at once with a wrong password (unknown email, so no real account is locked)
        t = time.perf_counter()
        rs = await asyncio.gather(*[c.post("/api/reios/auth/login",
                                           json={"identifier": f"nobody{i}@nowhere.test", "password": "guess"})
                                    for i in range(600)])
        codes = Counter(r.status_code for r in rs)
        print(f"1. sign-in flood, 600 at once:    {dict(codes)}  ({time.perf_counter() - t:.1f}s)")
        assert codes[429] > 0, "sign-in flood was never limited"

        await asyncio.sleep(30)  # let the sign-in bucket refill

        # 2. one admin token, 400 requests at once
        tok = (await c.post("/api/reios/auth/login", json={"identifier": ADMIN[0], "password": ADMIN[1]})).json()["access_token"]
        h = {"Authorization": "Bearer " + tok}
        rs = await asyncio.gather(*[c.get("/api/reios/auth/me", headers=h) for _ in range(400)])
        codes = Counter(r.status_code for r in rs)
        print(f"2. one user flooding, 400 at once: {dict(codes)}")
        assert codes[429] > 0, "a single user flooding was never limited"

        await asyncio.sleep(10)

        # 3. 150 teams from the same IP: sign in together, then each makes 6 normal requests
        teams = [(f"LT{i:03d}", f"Team {i:03d}") for i in range(1, 151)]
        rs = await asyncio.gather(*[c.post("/api/reios/auth/login",
                                           json={"identifier": r, "password": p, "college_code": "TST"}) for r, p in teams])
        login_codes = Counter(r.status_code for r in rs)
        tokens = [r.json()["access_token"] for r in rs if r.status_code == 200]

        async def normal_use(tk):
            hh = {"Authorization": "Bearer " + tk}
            out = []
            for path in ("/api/reios/auth/me", "/api/reios/student/dashboard") * 3:
                out.append((await c.get(path, headers=hh)).status_code)
            await c.post("/api/reios/auth/logout", headers=hh)
            return out

        use = Counter(code for codes_ in await asyncio.gather(*[normal_use(tk) for tk in tokens]) for code in codes_)
        print(f"3. 150 teams on one IP: sign-in {dict(login_codes)}, then normal use {dict(use)}")
        assert login_codes.get(429, 0) == 0 and use.get(429, 0) == 0, "a venue sharing one IP got rate-limited"
        print("RATE LIMITS OK: abuse blocked, a full venue on one IP never blocked")


asyncio.run(main())
