"""
Load test against the LIVE backend, entirely through its API as the LOADTEST event's admin.

  python live_loadtest.py setup <gk10.docx> [N]   -> creates N teams, uploads 10 sets, publishes an exam
  python live_loadtest.py run <exam_id> [N]       -> N teams sign in + start together, answer at a human pace, submit
"""
import asyncio
import csv
import io
import json
import os
import random
import sys
import time
from collections import defaultdict
from pathlib import Path

import httpx

BASE = os.environ.get("LT_BASE", "http://127.0.0.1:8080")
ADMIN = (os.environ["LT_ADMIN_EMAIL"], os.environ["LT_ADMIN_PASSWORD"])
STATE = Path(__file__).with_name("loadtest_state.json")
PACE = (8, 20)  # seconds a team spends per question (overridable, see below)
SPREAD = float(sys.argv[4]) if len(sys.argv) > 4 else 3
WAVE = int(sys.argv[5]) if len(sys.argv) > 5 else 10**6   # teams per wave
GAP = float(sys.argv[6]) if len(sys.argv) > 6 else 0      # seconds between waves
START_AT = float(sys.argv[9]) if len(sys.argv) > 9 else 0  # seconds after go when all press Start
PACE_ARG = len(sys.argv) > 8
if PACE_ARG:
    PACE = (float(sys.argv[7]), float(sys.argv[8]))


def admin_client() -> httpx.Client:
    c = httpx.Client(base_url=BASE, timeout=180)
    r = c.post("/api/reios/auth/login", json={"identifier": ADMIN[0], "password": ADMIN[1]})
    r.raise_for_status()
    c.headers["Authorization"] = "Bearer " + r.json()["access_token"]
    me = r.json()["user"]
    assert me["college"]["code"] == "TST", f"wrong account: {me['college']}"
    return c


def setup(docx: str, n: int):
    t0 = time.time()
    c = admin_client()
    print("admin ok, event", c.get("/api/reios/auth/me").json()["college"])

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["roll_no", "name", "password"])
    teams = [(f"LT{i:03d}", f"Team {i:03d}") for i in range(1, n + 1)]
    for roll, name in teams:
        w.writerow([roll, name, name])  # team name is the password, as at real events
    r = c.post("/api/reios/admin/students/import", files={"file": ("teams.csv", buf.getvalue(), "text/csv")})
    r.raise_for_status()
    print(f"teams: created {r.json()['created']}, failed {r.json()['failed']}  ({time.time()-t0:.0f}s)")

    parsed = c.post("/api/reios/admin/questions/parse", files={"file": ("gk10.docx", Path(docx).read_bytes())},
                    data={"default_section": "General Knowledge"}).json()
    by_set = defaultdict(list)
    keep = {"section", "question_text", "options", "correct_options", "marks", "negative_marks"}
    for q in parsed["questions"]:
        by_set[q["set"]].append({k: v for k, v in q.items() if k in keep})

    now = time.time()
    iso = lambda t: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t))
    exam = c.post("/api/reios/admin/exams", json={
        "title": "LOAD TEST - GK", "exam_type": "mcq", "start_at": iso(now - 60), "end_at": iso(now + 4 * 3600),
        "duration_minutes": 60, "show_leaderboard": True}).json()
    for name, qs in by_set.items():
        r = c.post(f"/api/reios/admin/exams/{exam['id']}/sets", json={"name": name, "questions": qs})
        r.raise_for_status()
    c.post(f"/api/reios/admin/exams/{exam['id']}/publish").raise_for_status()
    a = c.get(f"/api/reios/admin/exams/{exam['id']}/set-assignments").json()
    STATE.write_text(json.dumps({"exam_id": exam["id"], "teams": teams}))
    print(f"exam {exam['id']} published: {len(by_set)} sets, {len(a['students'])} teams, {a['unassigned']} unassigned"
          f"  (setup took {time.time()-t0:.0f}s)")


async def run(exam_id: int, n: int):
    teams = json.loads(STATE.read_text())["teams"][:n]
    stats, errors = defaultdict(list), defaultdict(list)
    inside = []

    async def call(client, name, method, url, **kw):
        t0 = time.perf_counter()
        for attempt in range(3):  # the real site retries reads, sign-in and start the same way
            try:
                r = await client.request(method, url, **kw)
                if r.status_code in (502, 503, 504) and attempt < 2:
                    await asyncio.sleep(0.5 * 2 ** attempt)
                    continue
                stats[name].append(time.perf_counter() - t0)
                if r.status_code >= 400:
                    errors[name].append(f"{r.status_code} {r.text[:100]}")
                    return None
                return r.json()
            except Exception as exc:
                if attempt == 2:
                    stats[name].append(time.perf_counter() - t0)
                    errors[name].append(f"{type(exc).__name__}: {exc}"[:120])
                    return None
                await asyncio.sleep(0.5 * 2 ** attempt)

    late = []
    go = asyncio.Event()
    t_go = [0.0]

    async def team(roll, password, client):
        await go.wait()
        idx = int(roll[2:]) - 1
        await asyncio.sleep((idx // WAVE) * GAP + random.uniform(0, SPREAD))  # wave start + small spread
        login = await call(client, "sign in", "POST", "/api/reios/auth/login",
                           json={"identifier": roll, "password": password})
        if not login:
            return "sign-in failed"
        h = {"Authorization": "Bearer " + login["access_token"]}
        await call(client, "dashboard", "GET", "/api/reios/student/dashboard", headers=h)
        await call(client, "exam page", "GET", f"/api/reios/student/exams/{exam_id}", headers=h)
        if START_AT:  # everyone waits on the instructions page, then presses Start together
            now = time.perf_counter() - t_go[0]
            if now < START_AT:
                await asyncio.sleep(START_AT - now + random.uniform(0, 5))
            else:
                late.append(roll)
        paper = await call(client, "start", "POST", f"/api/reios/student/exams/{exam_id}/start", headers=h)
        if not paper:
            return "start failed"
        inside.append(time.perf_counter() - t_go[0])
        hs = {**h, "X-Exam-Session": paper["session"]}
        aid = paper["attempt_id"]
        for k, item in enumerate(paper["items"]):
            await asyncio.sleep(random.uniform(*PACE))
            await call(client, "save answer", "PUT", f"/api/reios/student/attempts/{aid}/mcq/{item['item_id']}",
                       headers=hs, json={"selected": [random.choice(item["options"])["id"]], "marked_for_review": False})
            if k % 2 == 1:  # the real exam page sends a heartbeat about every 30 s
                await call(client, "heartbeat", "POST", f"/api/reios/student/attempts/{aid}/heartbeat", headers=hs)
        res = await call(client, "submit", "POST", f"/api/reios/student/attempts/{aid}/submit", headers=hs)
        if not res:
            return "submit failed"
        await call(client, "leaderboard", "GET", f"/api/reios/student/exams/{exam_id}/leaderboard", headers=h)
        return "ok"

    limits = httpx.Limits(max_connections=n + 20, max_keepalive_connections=n + 20)
    async with httpx.AsyncClient(base_url=BASE, timeout=120, limits=limits) as client:
        tasks = [asyncio.create_task(team(r, p, client)) for r, p in teams]
        await asyncio.sleep(0.5)
        t_go[0] = time.perf_counter()
        go.set()
        outcomes = await asyncio.gather(*tasks)
        wall = time.perf_counter() - t_go[0]

    print(f"\n{n} teams, whole test {wall/60:.1f} min")
    print("outcomes:", {o: outcomes.count(o) for o in set(outcomes)})
    if START_AT:
        print(f"signed in after the common start (couldn't wait): {len(late)}")
    if inside:
        inside.sort()
        print(f"from pressing Start to inside the exam: half {inside[len(inside)//2]:.1f}s, "
              f"95% {inside[int(.95*len(inside))]:.1f}s, slowest {inside[-1]:.1f}s")
    print(f"{'step':12} {'calls':>6} {'errors':>6} {'median':>8} {'95%':>8} {'slowest':>8}")
    for name in ("sign in", "dashboard", "exam page", "start", "save answer", "heartbeat", "submit", "leaderboard"):
        xs = sorted(stats[name])
        if xs:
            q = lambda f: xs[min(len(xs) - 1, int(f * len(xs)))]
            print(f"{name:12} {len(xs):6} {len(errors[name]):6} {q(.5):7.2f}s {q(.95):7.2f}s {xs[-1]:7.2f}s")
    for name, errs in errors.items():
        print(f"  {name} errors: {errs[:3]}")


def new_exam(docx: str):
    c = admin_client()
    parsed = c.post("/api/reios/admin/questions/parse", files={"file": ("gk10.docx", Path(docx).read_bytes())},
                    data={"default_section": "General Knowledge"}).json()
    by_set = defaultdict(list)
    keep = {"section", "question_text", "options", "correct_options", "marks", "negative_marks"}
    for q in parsed["questions"]:
        by_set[q["set"]].append({k: v for k, v in q.items() if k in keep})
    now = time.time()
    iso = lambda t: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t))
    exam = c.post("/api/reios/admin/exams", json={
        "title": "LOAD TEST - waves", "exam_type": "mcq", "start_at": iso(now - 60), "end_at": iso(now + 4 * 3600),
        "duration_minutes": 60, "show_leaderboard": True}).json()
    for name, qs in by_set.items():
        c.post(f"/api/reios/admin/exams/{exam['id']}/sets", json={"name": name, "questions": qs}).raise_for_status()
    c.post(f"/api/reios/admin/exams/{exam['id']}/publish").raise_for_status()
    print("new exam", exam["id"])


if __name__ == "__main__":
    if sys.argv[1] == "newexam":
        new_exam(sys.argv[2]); sys.exit()
    if sys.argv[1] == "setup":
        setup(sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 150)
    else:
        asyncio.run(run(int(sys.argv[2]), int(sys.argv[3]) if len(sys.argv) > 3 else 150))
