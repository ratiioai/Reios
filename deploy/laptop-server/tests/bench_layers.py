"""Find which layer limits throughput: same request mix through nginx vs straight to one API instance."""
import asyncio
import os
import sys
import time
from collections import Counter

import httpx

CONC = int(sys.argv[1]) if len(sys.argv) > 1 else 100
SECS = 10


async def bench(label, base, path, headers=None):
    stop = time.perf_counter() + SECS
    codes, lat = Counter(), []
    async with httpx.AsyncClient(base_url=base, timeout=60,
                                 limits=httpx.Limits(max_connections=CONC, max_keepalive_connections=CONC)) as c:
        async def w(i):
            while time.perf_counter() < stop:
                t = time.perf_counter()
                r = await c.get(path, headers=headers or {})
                codes[r.status_code] += 1
                lat.append(time.perf_counter() - t)
        await asyncio.gather(*[w(i) for i in range(CONC)])
    lat.sort()
    print(f"{label:42} {sum(codes.values()) / SECS:7.0f} req/s  median {lat[len(lat)//2]*1000:6.1f}ms  "
          f"95% {lat[int(.95*len(lat))]*1000:7.1f}ms  {dict(codes)}")


async def main():
    tok = httpx.post("http://127.0.0.1:8001/api/reios/auth/login",
                     json={"identifier": os.environ["LT_ADMIN_EMAIL"], "password": os.environ["LT_ADMIN_PASSWORD"]}).json()["access_token"]
    h = {"Authorization": "Bearer " + tok}
    await bench("static file via nginx (no Python)", "http://127.0.0.1:8080", "/reios-logo.png")
    await bench("/api/health via nginx (no DB)", "http://127.0.0.1:8080", "/api/health")
    await bench("/api/health direct to one instance", "http://127.0.0.1:8001", "/api/health")
    await bench("/auth/me direct to one instance (1 DB read)", "http://127.0.0.1:8001", "/api/reios/auth/me", h)


asyncio.run(main())
