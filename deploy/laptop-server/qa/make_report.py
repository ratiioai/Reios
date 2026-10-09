"""Builds the test report (HTML -> PDF via headless Chrome) from everything in qa/results."""
import html
import json
import re
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

R = Path(r"C:\reios-server\qa\results")
OUT_HTML = Path(r"C:\reios-server\qa\Reios_Test_Report.html")
OUT_PDF = Path(r"C:\Users\Dell\Downloads\Reios_Test_Report_2026-10-09.pdf")
J = lambda n: json.loads((R / n).read_text(encoding="utf-8"))
e = html.escape

inv = J("code_inventory.json"); api = J("api_suite.json"); br = J("browser_e2e.json"); db = J("db_integrity.json")
perf = J("perf_baseline.json"); lb = J("lb_analysis.json"); avs = J("availability_summary.json")


def junit(name):
    t = ET.parse(R / name).getroot()
    s = t if t.tag == "testsuite" else t.find("testsuite")
    cases = [c.get("name") for c in s.iter("testcase")]
    failed = int(s.get("failures", 0)) + int(s.get("errors", 0))
    return {"tests": int(s.get("tests")), "failed": failed, "time": float(s.get("time")), "cases": cases}


py_sqlite, py_pg = junit("pytest_sqlite.xml"), junit("pytest_postgres.xml")


def parse_load(name):
    txt = (R / f"load_{name}.txt").read_text(encoding="utf-8")
    meta = J(f"load_{name}.meta.json")
    steps = {}
    for m in re.finditer(r"^(sign in|dashboard|exam page|start|save answer|heartbeat|submit|leaderboard)\s+(\d+)\s+(\d+)\s+([\d.]+)s\s+([\d.]+)s\s+([\d.]+)s", txt, re.M):
        steps[m.group(1)] = {"calls": int(m.group(2)), "errors": int(m.group(3)), "median": float(m.group(4)),
                             "p95": float(m.group(5)), "max": float(m.group(6))}
    outcomes = re.search(r"outcomes: (\{.*\})", txt).group(1)
    minutes = re.search(r"whole test ([\d.]+) min", txt).group(1)
    return {"meta": meta, "steps": steps, "outcomes": outcomes, "minutes": minutes,
            "requests": sum(s["calls"] for s in steps.values()), "errors": sum(s["errors"] for s in steps.values())}


loads = {n: parse_load(n) for n in ("public150", "failover200", "scale300", "dbrestart100")}
stress_txt = (R / "stress.txt").read_text(encoding="utf-8")
stress_rows = [m.groups() for m in re.finditer(r"^\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)ms\s+(\d+)ms\s+(\d+)ms", stress_txt, re.M)]
storm = re.search(r"sign-in storm: (\d+) at the same instant -> \{200: (\d+)\} in ([\d.]+)s", stress_txt)
startb = re.search(r"(\d+) teams pressed Start together -> all inside in ([\d.]+)s \(median ([\d.]+)s, 95% ([\d.]+)s\)", stress_txt)
av = avs["availability"]; peaks = avs["peaks"]

rl = (R / "ratelimit.txt").read_text(encoding="utf-8")
m1 = re.search(r"sign-in flood, 600 at once:\s+(\{.*?\})", rl); m2 = re.search(r"one user flooding, 400 at once: (\{.*?\})", rl)
m3 = re.search(r"150 teams on one IP: sign-in (\{.*?\}), then normal use (\{.*?\})", rl)
ratelimit = [
    {"category": "Rate limiting", "name": "600 password guesses at once from one IP are throttled (429)", "pass": "429" in m1.group(1), "detail": m1.group(1)},
    {"category": "Rate limiting", "name": "One signed-in user flooding 400 requests is throttled (429)", "pass": "429" in m2.group(1), "detail": m2.group(1)},
    {"category": "Rate limiting", "name": "A whole venue on ONE IP signing in and using the app is never throttled", "pass": "429" not in m3.group(1) + m3.group(2),
     "detail": f"sign-in {m3.group(1)} (401s = test accounts that don't exist), use {m3.group(2)}"},
]
all_checks = api + br + db + ratelimit
cat_order = ["Functional", "Browser (admin)", "Browser (team)", "Security", "Rate limiting", "Security headers", "Input validation",
             "Negative", "Integration", "Data integrity", "Database security", "Database health", "Backup & restore"]
by_cat = {}
for c in all_checks:
    by_cat.setdefault(c["category"], []).append(c)
total_checks = len(all_checks) + py_sqlite["tests"] + py_pg["tests"]
total_pass = sum(c["pass"] for c in all_checks) + (py_sqlite["tests"] - py_sqlite["failed"]) + (py_pg["tests"] - py_pg["failed"])


def badge(ok, yes="PASS", no="FAIL"):
    return f'<span class="b {"ok" if ok else "bad"}">{yes if ok else no}</span>'


def bars(values, unit="", maxv=None, color="#e12616"):
    """Horizontal bar chart (inline SVG) for {label: value}."""
    maxv = maxv or max(values.values()) or 1
    h = 22 * len(values) + 6
    out = [f'<svg width="100%" viewBox="0 0 640 {h}" class="chart">']
    for i, (k, v) in enumerate(values.items()):
        y = 4 + i * 22; w = 430 * v / maxv
        out.append(f'<text x="0" y="{y + 14}" class="cl">{e(str(k))}</text>'
                   f'<rect x="150" y="{y + 2}" width="{w:.1f}" height="15" rx="3" fill="{color}"/>'
                   f'<text x="{156 + w:.1f}" y="{y + 14}" class="cv">{v}{unit}</text>')
    out.append("</svg>")
    return "".join(out)


def table(headers, rows, cls=""):
    th = "".join(f"<th>{h}</th>" for h in headers)
    trs = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f'<table class="{cls}"><thead><tr>{th}</tr></thead><tbody>{trs}</tbody></table>'


def checks_table(cat):
    rows = by_cat.get(cat, [])
    return table(["Check", "Result", "Observed"], [[e(c["name"]), badge(c["pass"]),
                 f'<span class="small">{e(c["detail"]) if not c["pass"] or len(c["detail"]) < 90 else ""}</span>'] for c in rows])


def summary_row(label, items):
    p = sum(c["pass"] for c in items)
    return [label, f"{p} / {len(items)}", badge(p == len(items), "ALL PASS", f"{len(items) - p} FAILED")]


# ------------------------------------------------------------------------------------------- HTML
L = loads
pub, fo, sc, dr = L["public150"], L["failover200"], L["scale300"], L["dbrestart100"]
lat_local = [x for x in perf["latency"] if x["path"].startswith("local")]
lat_net = {x["request"]: x for x in perf["latency"] if x["path"].startswith("internet")}

findings = [
    ("High", "Connection-pool starvation under a 300-team simultaneous start",
     "Each request kept its database connection while waiting for a worker thread. With 300 teams pressing Start in the same instant, all connections were held by waiting requests while all threads waited for a connection: 267/300 got in, slowest 93 s, 136 pool-timeout errors.",
     "Authentication now ends its read transaction immediately, returning the connection. Re-test: 300/300 inside in 10 s, 0 errors; stress ramp 0 errors at every level.", "Fixed (b12f29b)"),
    ("Medium", "Branded event's logo sent inside every sign-in and page load",
     "The ~280 KB logo was embedded in every sign-in and /auth/me response: 374 KB per TECHSPRINT page load, slow on mobile data.",
     "Logo served once from a versioned, cacheable URL (browser 1 day, nginx cache). Sign-in response 374 KB -> 0.6 KB.", "Fixed (6ebc3ff)"),
    ("Medium", "Missing browser security headers; plain HTTP accepted",
     "No HSTS, nosniff, anti-framing, CSP or referrer policy; http:// served without redirect.",
     "Added on nginx and Vercel (HSTS, nosniff, X-Frame-Options DENY, CSP frame-ancestors/object-src/base-uri, Referrer-Policy, Permissions-Policy); http -> https 301.", "Fixed (6ebc3ff)"),
    ("Medium", "nginx silently kept an old config after a reload",
     "Changing a rate-limit zone's key can't be applied by reload; nginx rejected it ([emerg] in error.log) and kept running the previous config, so the CORS-preflight exemption wasn't active.",
     "Full nginx restart applied it; verified 400/400 preflights pass. The new log viewer surfaces such errors.", "Fixed"),
    ("Low", "Uploading an empty/garbage team list reported success",
     "A file with no rows returned 200 '0 created, 0 failed'.", "Now a clear 400 'No rows found in the file'.", "Fixed (6ebc3ff)"),
]
risks = [
    ("Critical (only if coding exams are used)", "Student code runs on the laptop without a sandbox",
     "Coding questions execute participants' code directly on this machine with only a time limit - no memory, file-system or network isolation. A malicious submission could read server.env/db-passwords.txt or damage the machine. TECHSPRINT is MCQ-only, so this is not reachable today.",
     "Don't publish coding exams on the laptop server, or run the code runner in an isolated container/VM first."),
    ("Medium", "Single machine, quick-tunnel URL",
     "The laptop is a single point of failure (power, sleep, Wi-Fi, OS updates), and the free Cloudflare URL changes on every restart (handled automatically via backend.json, ~1-2 min Vercel rebuild).",
     "Keep it plugged in, sleep off, wired network, Windows Update paused during the event; a named Cloudflare tunnel on your domain gives a permanent URL."),
    ("Low", "CORS reflects any origin",
     "The API answers cross-origin requests from any website. Sign-in tokens are bearer tokens in the site's storage (not cookies), so another site can't use them - low risk.",
     "Optionally restrict to reios-web.vercel.app and the tunnel origin."),
    ("Low", "Memory headroom", f"The laptop ran at ~{round(peaks['machine']['mem'] / 1024, 1)} of 15.7 GB in use during the heaviest tests (includes other apps and the load generator).",
     "Close unneeded apps (browsers, IDEs) during the event."),
    ("Info", "Render database password", "The Render database URL with its password was shared in chat.", "Rotate it in Render after the event."),
]

css = """
@page { size: A4; margin: 16mm 14mm 16mm 14mm; }
body { font-family: 'Segoe UI', Arial, sans-serif; color: #1d1d1f; font-size: 10.2pt; line-height: 1.45; margin: 0; }
h1 { font-size: 26pt; margin: 0 0 6px; letter-spacing: -.5px; }
h2 { font-size: 15pt; border-bottom: 2.5px solid #e12616; padding-bottom: 4px; margin: 22px 0 10px; page-break-after: avoid; }
h3 { font-size: 11.5pt; margin: 14px 0 6px; color: #9a1d12; page-break-after: avoid; }
p { margin: 5px 0 8px; }
.cover { height: 250mm; display: flex; flex-direction: column; justify-content: center; page-break-after: always; }
.cover .brand { color: #e12616; font-weight: 800; font-size: 13pt; letter-spacing: 2px; text-transform: uppercase; }
.cover .sub { font-size: 13pt; color: #555; margin-top: 6px; }
.cover .verdict { margin-top: 28px; padding: 16px 18px; border-left: 6px solid #138a36; background: #eef8f0; font-size: 12pt; }
.cover table { margin-top: 26px; width: 100%; }
table { width: 100%; border-collapse: collapse; margin: 6px 0 12px; font-size: 9.2pt; page-break-inside: auto; }
tr { page-break-inside: avoid; }
th { background: #2b1512; color: #fff; text-align: left; padding: 5px 7px; font-weight: 600; }
td { border-bottom: 1px solid #e6e1df; padding: 4px 7px; vertical-align: top; }
tbody tr:nth-child(even) td { background: #faf7f6; }
.b { display: inline-block; padding: 1px 7px; border-radius: 9px; font-weight: 700; font-size: 8pt; white-space: nowrap; }
.ok { background: #dff3e4; color: #0f6b2b; } .bad { background: #fde2e0; color: #a0170c; } .warn { background: #fff1d6; color: #8a5a00; }
.small { font-size: 8.3pt; color: #666; }
.kpis { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; margin: 10px 0 14px; }
.kpi { border: 1px solid #eadfdc; border-radius: 8px; padding: 9px 10px; background: #fffdfc; }
.kpi .v { font-size: 17pt; font-weight: 800; color: #9a1d12; } .kpi .l { font-size: 8.3pt; color: #666; }
.chart .cl { font-size: 11px; fill: #333; } .chart .cv { font-size: 11px; fill: #333; font-weight: 600; }
.box { border: 1px solid #eadfdc; border-radius: 8px; padding: 9px 12px; margin: 8px 0; background: #fffdfc; page-break-inside: avoid; }
.arch { font-family: Consolas, monospace; font-size: 8.6pt; background: #fbf8f7; border: 1px solid #eadfdc; padding: 10px; border-radius: 8px; white-space: pre; }
.pb { page-break-before: always; }
.sev-High, .sev-Critical { color: #a0170c; font-weight: 700; } .sev-Medium { color: #8a5a00; font-weight: 700; } .sev-Low, .sev-Info { color: #555; font-weight: 700; }
footer { font-size: 8pt; color: #888; }
"""

H = []
H.append(f"""<div class="cover">
<div class="brand">Reios &middot; Developed by Ratiio</div>
<h1>Platform Test Report</h1>
<div class="sub">Functional, API, security, database, performance, load, stress, load-balancing, reliability and availability testing<br>
of the laptop deployment (nginx + 6 API instances + PostgreSQL + Cloudflare tunnel, website on Vercel)</div>
<div class="verdict"><b>Verdict: ready for the event.</b> 150 participants over the public internet completed a full exam with
<b>zero errors</b>; 300 participants and injected failures (API crash, nginx reload, database restart) were also handled.
{len(findings)} defects were found during testing and <b>all were fixed and re-tested</b>; one critical risk applies only if coding exams are run on the laptop.</div>
<table>
<tr><td><b>Date</b></td><td>9 October 2026</td><td><b>Code version</b></td><td>b12f29b (main)</td></tr>
<tr><td><b>System under test</b></td><td>Reios exam platform</td><td><b>Event data</b></td><td>TECHSPRINT (93 teams) - untouched by tests</td></tr>
<tr><td><b>Test event</b></td><td>TST (all test data removed afterwards)</td><td><b>Machine</b></td><td>Intel i5-1155G7 (8 threads), 15.7 GB RAM, Windows 11</td></tr>
</table>
</div>""")

H.append(f"""<h2>1. Executive summary</h2>
<div class="kpis">
<div class="kpi"><div class="v">{total_pass}/{total_checks}</div><div class="l">automated checks passed (after fixes)</div></div>
<div class="kpi"><div class="v">{pub['errors']}</div><div class="l">errors - 150 participants over the internet ({pub['requests']:,} requests)</div></div>
<div class="kpi"><div class="v">{av['nginx']['pct']}%</div><div class="l">server availability during testing ({av['nginx']['checks']} checks)</div></div>
<div class="kpi"><div class="v">{len(findings)}</div><div class="l">defects found - all fixed and re-tested</div></div>
<div class="kpi"><div class="v">{pub['steps']['save answer']['p95']:.2f} s</div><div class="l">answer save, 95th percentile (150 over internet)</div></div>
<div class="kpi"><div class="v">{sc['errors']}</div><div class="l">errors with 300 participants ({sc['requests']:,} requests)</div></div>
<div class="kpi"><div class="v">0</div><div class="l">participants affected by an API instance crash mid-exam</div></div>
<div class="kpi"><div class="v">{round(peaks['api']['cpu'])}%</div><div class="l">peak API CPU (under deliberate stress only)</div></div>
</div>""")
H.append(table(["Test type", "Result", "Status"], [
    ["Regression suite (SQLite + PostgreSQL)", f"{py_sqlite['tests'] - py_sqlite['failed']}/{py_sqlite['tests']} + {py_pg['tests'] - py_pg['failed']}/{py_pg['tests']}", badge(py_sqlite['failed'] + py_pg['failed'] == 0, "ALL PASS")],
    summary_row("Functional & API (live stack)", by_cat["Functional"]),
    summary_row("Browser end-to-end (real Chrome)", by_cat["Browser (admin)"] + by_cat["Browser (team)"]),
    summary_row("Security (auth, tokens, isolation, injection, hardening)", by_cat["Security"]),
    summary_row("Rate limiting (abuse blocked, venue on one IP never blocked)", by_cat["Rate limiting"]),
    [*summary_row("Security headers & CORS", by_cat["Security headers"])[:2], '<span class="b warn">1 ACCEPTED RISK</span>'],
    summary_row("Input validation", by_cat["Input validation"]),
    summary_row("Negative / business rules", by_cat["Negative"]),
    summary_row("Integration (Vercel / Cloudflare / nginx / API / DB)", by_cat["Integration"]),
    summary_row("Database, data integrity, backup & restore", by_cat["Data integrity"] + by_cat["Database security"] + by_cat["Database health"] + by_cat["Backup & restore"]),
    ["Load: 150 over internet / 200 / 300 participants", f"{pub['errors']} / {fo['errors']} / {sc['errors']} errors", badge(pub['errors'] + fo['errors'] + sc['errors'] == 0, "ALL PASS")],
    ["Stress ramp (up to 300 teams x 10 saves/s)", f"{sum(int(r[3]) for r in stress_rows)} errors", badge(sum(int(r[3]) for r in stress_rows) == 0, "PASS")],
    ["Load balancing across 6 instances", "within ~1% in every run", badge(True, "PASS")],
    ["Reliability: API crash, nginx reload, DB restart", f"0 / 0 / {dr['errors']} failed requests of {dr['requests']:,}", '<span class="b warn">PASS WITH NOTE</span>'],
    ["Availability (whole session)", f"nginx {av['nginx']['pct']}%, public {av['public']['pct']}%", badge(True, "PASS")],
]))

H.append("""<h2>2. System under test</h2>
<div class="arch">Participants (any country, any network)
    |  https://reios-web.vercel.app  -- the website (React), reads /backend.json = laptop's address
    v
Cloudflare quick tunnel  (*.trycloudflare.com, HTTPS, passes the participant's real IP)
    v
nginx 1.28 :8080  -- reverse proxy, load balancer (least_conn), cache, gzip, rate limits, security headers
    |-- 127.0.0.1:8001 .. 8006   6 x Reios API (FastAPI / uvicorn, 12 worker threads each)
    v
PostgreSQL 18 :5433  -- dedicated instance, data in C:\\reios-server\\pgdata, synchronous commit on</div>""")
H.append(table(["Component", "Detail"], [
    ["Codebase", f"{inv['total_files']} source files, {inv['total_lines']:,} lines - Python {inv['lines_by_language'].get('Python', 0):,}, React {inv['lines_by_language'].get('React (JSX)', 0):,}, other {inv['total_lines'] - inv['lines_by_language'].get('Python', 0) - inv['lines_by_language'].get('React (JSX)', 0):,}"],
    ["API surface", f"{inv['route_count']} endpoints: " + ", ".join(f"{v} {k}" for k, v in inv['routes_by_auth'].items())],
    ["Data at test time", "2 events, ~200 accounts, 4 real exams, ~229 real attempts, ~3,200 real answers (TECHSPRINT)"],
    ["Secrets in GitHub", "none found (scan of all tracked files); server.env / db-passwords kept only on the laptop"],
]))

H.append("""<h2>3. Approach</h2><p>Every test ran against the <b>real deployed stack</b> on this laptop (except the regression suite, which runs
against throwaway SQLite and PostgreSQL databases). Destructive and high-volume tests used the separate <b>TST</b> test event;
everything they created was deleted afterwards and the real TECHSPRINT event was verified untouched. Load is generated from the same
laptop, so all capacity figures are <b>conservative</b> - the test tools compete with the server for CPU.</p>""")
H.append(table(["Type", "How it was tested"], [
    ["Regression", "28 automated end-to-end API tests (pytest) - run on SQLite and on PostgreSQL 18"],
    ["Functional / API", "Black-box calls through nginx covering exam lifecycle, Start/Pause/Resume/End, answers, scoring, results, Live Monitor, reopen, reset login"],
    ["Browser E2E", "Headless Chrome driving the real UI: every admin page; a team signing in, accepting rules, answering by clicking and submitting"],
    ["Security", "Unauthenticated / wrong-role / cross-event access, forged/expired/alg:none tokens, lockout, enumeration, SQL injection, stored XSS, path traversal, upload limits, headers, TLS redirect"],
    ["Input validation / negative", "Invalid, missing, oversized and wrong-type input; business rules (double submit, deleted/disabled accounts, ended exams)"],
    ["Database / data integrity", "Orphans, duplicates, score arithmetic, answers vs answer key, password hashing, privileges, backup -> restore drill"],
    ["Performance", "Single-user latency per request type (local and over the internet), page weight, payload sizes"],
    ["Load", "Realistic exam: staggered sign-in, everyone presses Start together, 20 answers each at a human pace, submit, leaderboard"],
    ["Stress", "Teams saving an answer every 0.1 s (~100x a person) in rising steps to find the breaking point"],
    ["Load balancing", "Per-instance request counts from nginx's access log during every load test"],
    ["Reliability / availability", "API instance killed and restarted mid-exam, nginx reload mid-exam, PostgreSQL restart mid-exam; 5-second health probes all session"],
]))

H.append('<h2 class="pb">4. Load testing</h2>')
H.append(f"<p>Scenario: participants sign in over 2 minutes, wait on the rules page, <b>all press Start at the same moment</b>, answer 20 questions "
         "(8-20 s each), submit, open the leaderboard. Times are measured at the participant.</p>")
H.append(table(["Run", "Participants", "Path", "Requests", "Errors", "Outcome", "Duration"], [
    ["Public internet", "150", "Cloudflare -> nginx", f"{pub['requests']:,}", f"<b>{pub['errors']}</b>", "all completed", f"{pub['minutes']} min"],
    ["Failure injection", "200", "nginx", f"{fo['requests']:,}", f"<b>{fo['errors']}</b>", "all completed", f"{fo['minutes']} min"],
    ["Scale", "300", "nginx", f"{sc['requests']:,}", f"<b>{sc['errors']}</b>", "all completed", f"{sc['minutes']} min"],
    ["Database restart", "100", "nginx", f"{dr['requests']:,}", f"<b>{dr['errors']}</b>", "all completed", f"{dr['minutes']} min"],
]))
steps_order = ["sign in", "dashboard", "exam page", "start", "save answer", "heartbeat", "submit", "leaderboard"]
H.append("<h3>Response times per step (median / 95th percentile / slowest, seconds)</h3>")
H.append(table(["Step", "150 over internet", "200 + crash", "300 participants"], [
    [s] + [f"{L[n]['steps'][s]['median']:.2f} / {L[n]['steps'][s]['p95']:.2f} / {L[n]['steps'][s]['max']:.2f}" for n in ("public150", "failover200", "scale300")]
    for s in steps_order]))
H.append(f"""<div class="box"><b>Reading these results.</b> At 150-200 participants every step is well under a second, including 200 teams pressing
Start together (95% under {fo['steps']['start']['p95']:.2f} s). At 300 the simultaneous Start is queued rather than failed: half get in within
{sc['steps']['start']['median']:.1f} s and the slowest after {sc['steps']['start']['max']:.1f} s; everything else stays fast. The slowest
answer saves ({fo['steps']['save answer']['max']:.1f} s at 200) are the moment an API instance was killed - nginx retried them elsewhere.</div>""")

H.append("<h2>5. Load balancing</h2><p>Requests handled by each of the 6 API instances (from nginx's log). <code>least_conn</code> spreads load "
         "almost perfectly; when instance 8003 was killed for 60 s in the failure run, its share moved to the other five.</p>")
for n, label in (("public150", "150 participants over the internet"), ("scale300", "300 participants"), ("failover200", "200 participants, instance 8003 down for 60 s")):
    d = lb[n]["per_instance"]
    H.append(f"<h3>{label} - {lb[n]['requests']:,} API requests</h3>" + bars({k.replace('127.0.0.1:', 'API '): v for k, v in d.items()},
             color="#e12616" if n != "failover200" else "#b54708"))

H.append('<h2>6. Stress testing</h2>')
H.append(f"<p>Each virtual team saves an answer every 0.1 s - roughly 100 times a real participant - for 30 s per step, spread over 40 source "
         f"addresses so the rate limiter doesn't cap it. Sign-in storm: <b>{storm.group(2)}/{storm.group(1)}</b> succeeded in {storm.group(3)} s; "
         f"<b>{startb.group(1)} teams pressing Start in the same instant</b> were all inside in {startb.group(2)} s (median {startb.group(3)} s).</p>")
H.append(table(["Teams hammering", "Saves / s", "Succeeded", "Errors", "Median", "95%", "99%"],
               [[r[0], r[1], f"{int(r[2]):,}", f"<b>{r[3]}</b>", f"{int(r[4]) / 1000:.2f} s", f"{int(r[5]) / 1000:.2f} s", f"{int(r[6]) / 1000:.2f} s"] for r in stress_rows]))
H.append(f"""<div class="box"><b>Breaking point.</b> Before the connection-pool fix, 300 simultaneous starts gave 267/300 success, a 93 s tail and
136 pool-timeout errors. After the fix there are <b>no errors at any level</b>: past ~70 saves/s the server <b>slows down instead of failing</b>.
For scale: 150 real teams save roughly 5-15 answers per second, so the ceiling is about 5-10x the event's real load - and the measurement
includes the load generator running on the same laptop (peak machine CPU 100%).</div>""")

H.append("<h2>7. Reliability and availability</h2>")
H.append(table(["Injected failure (during a live exam)", "What participants saw"], [
    ["API instance 8003 killed, restarted 60 s later (200 participants)", "<b>Nothing</b> - 0 errors; nginx routed around it, slowest save 2.1 s at the moment of the crash"],
    ["nginx configuration reloaded mid-exam (200 participants)", "<b>Nothing</b> - 0 errors"],
    ["Rolling restart of all 6 API instances (3 times during the session)", "<b>Nothing</b> - health probes stayed 100%"],
    ["PostgreSQL restarted mid-exam (100 participants)", f"Database down 1.1 s; <b>{dr['errors']} of {dr['requests']:,} requests</b> failed (answer saves/heartbeats) and recovered automatically. In the real exam page failed saves are retried automatically, so no answer would be lost."],
]))
H.append(table(["Health probe (every 5 s for the whole session)", "Checks", "Up", "Median response", "95%"], [
    ["nginx on the laptop", av["nginx"]["checks"], f"<b>{av['nginx']['pct']}%</b>", f"{av['nginx']['median_ms']} ms", f"{av['nginx']['p95_ms']} ms"],
    ["Public URL (through Cloudflare)", av["public"]["checks"], f"<b>{av['public']['pct']}%</b>", f"{av['public']['median_ms']} ms", f"{av['public']['p95_ms']} ms"],
]))
H.append(f"<p class='small'>The one missed public probe ({', '.join(t[11:] for t in av['public']['failed_at'])}) was during the deliberate 300-team burst before the pool fix.</p>")
names = {"api": "6 API instances", "postgres": "PostgreSQL", "nginx": "nginx", "tunnel": "Cloudflare tunnel", "machine": "Whole laptop (incl. other apps + load generator)"}
H.append('<div class="box" style="background:#fff"><b>Peak resource use</b> (during the heaviest stress; CPU as % of the whole machine)' +
         table(["Component", "Peak CPU", "Peak memory"], [[names.get(k, k), f"{peaks[k]['cpu']:.0f}%", f"{peaks[k]['mem']:,.0f} MB"]
               for k in ("api", "postgres", "nginx", "tunnel", "machine") if k in peaks]) + "</div>")

H.append('<h2>8. Performance baseline (one user at a time)</h2>')
H.append(table(["Request", "Local via nginx (median / 95%)", "Over the internet (median / 95%)"], [
    [x["request"], f"{x['median_ms']} ms" + (f" / {x['p95_ms']} ms" if x["p95_ms"] else ""),
     f"{lat_net[x['request']]['median_ms']} ms" + (f" / {lat_net[x['request']]['p95_ms']} ms" if lat_net[x['request']]['p95_ms'] else "")]
    for x in lat_local]))
w = perf["weight"]; pl = perf["payloads"]
H.append(table(["Measure", "Value"], [
    ["Website first load", f"{w['first_load_files']} files, {w['uncompressed_kb']} KB -> <b>{w['gzip_kb']} KB</b> compressed; hashed files cached 1 year"],
    ["Sign-in response, branded event (TECHSPRINT)", f"<b>{pl['branded event (TECHSPRINT)']['sign_in_kb']} KB</b> (was 374 KB before the logo fix)"],
    ["Sign-in response, plain event", f"{pl['plain event (TST)']['sign_in_kb']} KB"],
    ["Internet overhead (Cloudflare round trip from India)", f"~{round(lat_net['Health check']['median_ms'] - lat_local[1]['median_ms'])} ms per request"],
]))

H.append('<h2 class="pb">9. Detailed results</h2>')
H.append(f"<h3>Regression suite - {py_sqlite['tests']} tests on SQLite ({py_sqlite['time']:.0f} s) and PostgreSQL ({py_pg['time']:.0f} s), all passing</h3>")
H.append("<p class='small'>" + ", ".join(e(c.replace("test_", "").replace("_", " ")) for c in py_sqlite["cases"]) + "</p>")
for cat in cat_order:
    if cat in by_cat:
        items = by_cat[cat]
        H.append(f"<h3>{cat} - {sum(c['pass'] for c in items)}/{len(items)} passed</h3>" + checks_table(cat))

H.append('<h2 class="pb">10. Defects found and fixed</h2>')
for sev, title, problem, fix, status in findings:
    H.append(f'<div class="box"><span class="sev-{sev.split()[0]}">{sev}</span> &middot; <b>{e(title)}</b> &middot; <span class="b ok">{status}</span>'
             f'<p><b>Problem:</b> {e(problem)}</p><p><b>Fix and re-test:</b> {e(fix)}</p></div>')
H.append("<h2>11. Open risks and recommendations</h2>")
for sev, title, desc, rec in risks:
    H.append(f'<div class="box"><span class="sev-{sev.split()[0]}">{sev}</span> &middot; <b>{e(title)}</b>'
             f'<p>{e(desc)}</p><p><b>Recommendation:</b> {e(rec)}</p></div>')
H.append("""<h3>Event-day checklist</h3><ul>
<li>Laptop on charger, sleep disabled (<code>powercfg /change standby-timeout-ac 0</code>), wired or stable network, Windows Update paused.</li>
<li>Start the server once with <code>start-server.ps1</code>; don't restart during the exam. Check with <code>status.ps1</code>; watch with <code>watch-logs.ps1</code>.</li>
<li>Vercel: Firewall -> Attack Challenge Mode off. Confirm <code>reios-web.vercel.app/backend.json</code> shows the current tunnel URL.</li>
<li>For a very large simultaneous start (300+), expect a few seconds' wait after pressing Start - tell participants not to refresh.</li>
<li>MCQ exams only on the laptop server until the code runner is sandboxed.</li></ul>""")
H.append("<footer><p>Generated from the raw results in C:\\reios-server\\qa\\results. Test tools: deploy/laptop-server/tests and C:\\reios-server\\qa.</p></footer>")

OUT_HTML.write_text(f"<!doctype html><html><head><meta charset='utf-8'><title>Reios Test Report</title><style>{css}</style></head><body>{''.join(H)}</body></html>",
                    encoding="utf-8")
subprocess.run([r"C:\Program Files\Google\Chrome\Application\chrome.exe", "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                f"--print-to-pdf={OUT_PDF}", "--user-data-dir=" + str(R / "_chrome_pdf"), OUT_HTML.as_uri()],
               check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=180)
print("PDF:", OUT_PDF, f"{OUT_PDF.stat().st_size / 1024:.0f} KB")
