# Reios: website on Vercel, API on a laptop (nginx + several API instances + Cloudflare tunnel)

For when the free Render plan can't keep up. The API runs on one Windows machine, reachable
worldwide over HTTPS; the website stays on Vercel.

```
Participants ── https://reios-web.vercel.app (the website) ── reads /backend.json = the laptop's address
      └──HTTPS API calls──> Cloudflare quick tunnel ──> nginx :8080 ──> 6 API instances :8001-8006 ──> PostgreSQL :5433
                             (*.trycloudflare.com)      load balancer,   (uvicorn, 12 threads each)     (own data dir)
                                                        reverse proxy, cache, gzip, rate limits
```

The tunnel address changes whenever the server restarts. `start-server.ps1` writes the new one
into `web/public/backend.json` and pushes it; Vercel rebuilds in ~1-2 minutes. Pages already open
notice the old address is gone, re-read `backend.json` and carry on without a reload.
The laptop also serves the site itself at the tunnel address (fallback if Vercel has trouble).

## Layout on the machine (`C:\reios-server`)

| Path | What |
|---|---|
| `nginx\`, `cloudflared.exe` | nginx 1.28 for Windows, Cloudflare tunnel client |
| `pgdata\` | Reios' own PostgreSQL 18 instance (port 5433) - separate from any other Postgres |
| `web\` | the built website (`VITE_BASE=/ npx vite build --outDir C:/reios-server/web`) |
| `server.env` | settings + secrets (copy `server.env.example`); **never commit** |
| `db-passwords.txt` | generated Postgres passwords; **never commit** |
| `backups\` | every Render dump and a safety dump before each sync |
| `logs\` | API, nginx, Postgres and tunnel logs |

## Running an event

1. **Fresh data from Render** (stops the server while swapping; also signs every team out, since
   sessions from Render can't be used here):
   `powershell -ExecutionPolicy Bypass -File C:\reios-server\sync-from-render.ps1 -RenderUrl "postgresql://...render.com/reios"`
2. **Start**: `powershell -ExecutionPolicy Bypass -File C:\reios-server\start-server.ps1`
   It prints the public URL (also saved to `PUBLIC_URL.txt`). Share `<URL>/login` with participants.
   The quick-tunnel URL changes every time the server is restarted.
3. **Check**: `status.ps1`. **Stop**: `stop-server.ps1`.
4. Don't use the Render site after step 1: anything saved there won't reach the laptop.

Keep the laptop plugged in, on wired/stable internet, with sleep disabled
(`powercfg /change standby-timeout-ac 0`).

## nginx features

- **Load balancer**: `least_conn` over 6 instances; a crashed instance is skipped (`max_fails`)
  and its in-flight requests retried on another (`proxy_next_upstream`).
- **Reverse proxy**: keep-alive pool to the instances, real client IP from Cloudflare
  (`CF-Connecting-IP`), 25 MB uploads, 120 s timeouts.
- **Cache**: hashed site files cached 1 year (`immutable`), `index.html` never cached, public
  config/branding cached 60 s; nothing signed-in is ever cached. gzip (388 KB -> 114 KB main bundle).
- **Rate limits**: per signed-in user 15 req/s (burst 60); per IP 150 req/s (burst 600) - generous
  because a whole venue can share one IP; sign-in 10/s per IP (burst 250) on top of the app's own
  5-wrong-passwords lockout.

## Test results (2026-10-09, i5-1155G7 / 16 GB, real event data)

| Test | Result |
|---|---|
| Every admin page in a real browser (local and public URL) | no JS errors, no failed requests |
| All 193 real accounts sign in / dashboard / sign out (public URL) | 193/193 OK |
| Load: 100 teams, all press Start together | 0 errors; start 0.04 s, save 0.02 s median |
| Load: 200 teams + one API instance killed mid-exam | 0 errors; nginx routed around the crash |
| Load: 200 teams, final settings | 0 errors; save p95 0.03 s, start p95 0.09 s |
| Load: 150 teams over the public internet | 0 errors; save p95 0.19 s, start p95 0.19 s |
| Sign-in storm: 300 at the same instant | 300/300 OK in ~4 s |
| 300 teams press Start at the same instant | all inside in 4.4 s |
| Stress: teams saving 10x per second (~100x a person) | ~90 saves/s, 0 errors up to 200 such teams; overload shows as slowness, not failures |
| Rate limits | sign-in flood and single-user flood cut off with 429; 100 teams on one IP never limited |
| Cache / gzip / load balancing | config cached (HIT), assets immutable, requests spread evenly |

For comparison, Render's free plan with 100 teams: save p95 10.6 s, start up to 57 s.

## Tests (`tests\`)

Use the backend venv for `loadtest.py`/`test_all_users.py` and a separate venv with `aiohttp` for
`stress_test.py` (httpx can't generate enough load on Windows). Admin credentials for the test event
come from `LT_ADMIN_EMAIL` / `LT_ADMIN_PASSWORD`; `LT_BASE` picks the target URL.

```
python tests\loadtest.py setup gk10.docx 300          # test teams + an exam on the test event
python tests\loadtest.py newexam gk10.docx            # a fresh exam for each run
python tests\loadtest.py run <exam> 200 120 1000000 0 8 20 150   # 200 teams, common Start at 150 s
python tests\stress_test.py <exam> 300 50,100,200,300  # breaking point
python tests\ratelimit_test.py
powershell tests\crash_one_instance.ps1 -Port 8002 -AfterSeconds 200   # failover drill during a run
python tests\test_all_users.py <public URL>           # every real account
```
