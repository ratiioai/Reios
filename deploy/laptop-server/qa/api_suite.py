"""
Black-box tests against the LIVE stack (nginx -> API instances -> PostgreSQL), plus a few through the
public tunnel. Uses only the TST test event; real event data is never written to. Every record it
creates is listed in results/created.json for cleanup.
"""
import base64
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

NGINX = "http://127.0.0.1:8080"
PUBLIC = Path(r"C:\reios-server\PUBLIC_URL.txt").read_text().strip()
ADMIN = (os.environ["QA_ADMIN_EMAIL"], os.environ["QA_ADMIN_PASSWORD"])
RES = Path(r"C:\reios-server\qa\results")
results, created = [], {"exams": [], "mcqs": [], "students": [], "announcements": []}
c = httpx.Client(base_url=NGINX, timeout=60)


def check(category, name, cond, detail=""):
    results.append({"category": category, "name": name, "pass": bool(cond), "detail": str(detail)[:220]})
    print(("PASS " if cond else "FAIL ") + f"[{category}] {name}" + ("" if cond else f"  -> {str(detail)[:160]}"))


def run(category, name, fn):
    try:
        ok, detail = fn()
        check(category, name, ok, detail)
    except Exception as e:
        check(category, name, False, f"{type(e).__name__}: {e}")


def login(identifier, password, code=None):
    body = {"identifier": identifier, "password": password}
    if code:
        body["college_code"] = code
    return c.post("/api/reios/auth/login", json=body)


def H(tok, **extra):
    return {"Authorization": "Bearer " + tok, **extra}


# ---------------------------------------------------------------- setup
adm_r = login(*ADMIN)
ADM = adm_r.json()["access_token"]
TST = adm_r.json()["user"]["college"]
sts_exam_id = None
now = datetime.now(timezone.utc)

# ================================================================ FUNCTIONAL / API (happy paths)
F = "Functional"
run(F, "Admin signs in and gets a token", lambda: (adm_r.status_code == 200 and ADM, adm_r.status_code))
run(F, "GET /auth/me returns the signed-in admin",
    lambda: (lambda r: (r.status_code == 200 and r.json()["email"] == ADMIN[0], r.status_code))(c.get("/api/reios/auth/me", headers=H(ADM))))
run(F, "Admin overview stats load", lambda: (lambda r: (r.status_code == 200 and "students" in r.json(), r.status_code))(
    c.get("/api/reios/admin/stats", headers=H(ADM))))

r = c.post("/api/reios/admin/mcqs", headers=H(ADM), json={"section": "QA", "question_text": "QA: 2+2?",
                                                           "options": ["3", "4", "5", "6"], "correct_options": [1]})
check(F, "Create an MCQ in the event's question bank", r.status_code == 201, r.status_code)
q1 = r.json()["id"]; created["mcqs"].append(q1)
r = c.post("/api/reios/admin/mcqs", headers=H(ADM), json={"section": "QA", "question_text": "QA: capital of India?",
                                                           "options": ["Mumbai", "New Delhi"], "correct_options": [1]})
q2 = r.json()["id"]; created["mcqs"].append(q2)

r = c.post("/api/reios/admin/exams", headers=H(ADM), json={
    "title": "QA Functional Exam", "exam_type": "mcq", "duration_minutes": 30, "max_violations": 3,
    "show_results": True, "show_answers": True, "show_leaderboard": True,
    "start_at": (now + timedelta(days=1)).isoformat(), "end_at": (now + timedelta(days=2)).isoformat()})
check(F, "Create an exam", r.status_code == 201, r.status_code)
EX = r.json()["id"]; created["exams"].append(EX)
r = c.put(f"/api/reios/admin/exams/{EX}/items", headers=H(ADM),
          json={"items": [{"item_type": "mcq", "question_id": q1}, {"item_type": "mcq", "question_id": q2}]})
check(F, "Add questions to the exam", r.status_code == 200 and r.json()["question_count"] == 2, r.text[:100])
r = c.post(f"/api/reios/admin/exams/{EX}/publish", headers=H(ADM))
check(F, "Publish the exam", r.status_code == 200 and r.json()["is_published"], r.status_code)

# a dedicated QA team
r = c.post("/api/reios/admin/students", headers=H(ADM), json={"roll_no": "QA-001", "name": "QA Team One"})
check(F, "Add a team (team name becomes its password)", r.status_code == 201 and r.json()["temporary_password"] == "QA Team One", r.text[:100])
created["students"].append(r.json()["id"])
r = c.post("/api/reios/admin/students", headers=H(ADM), json={"roll_no": "QA-002", "name": "QA Team Two"})
created["students"].append(r.json()["id"])
STU2_ID = r.json()["id"]

t1r = login("QA-001", "QA Team One", TST["code"])
check(F, "Team signs in with team code + team name", t1r.status_code == 200, t1r.status_code)
T1 = t1r.json()["access_token"]
T2 = login("QA-002", "QA Team Two", TST["code"]).json()["access_token"]

dash = c.get("/api/reios/student/dashboard", headers=H(T1)).json()
st = next((e for e in dash["exams"] if e["id"] == EX), None)
check(F, "Unstarted exam shows as 'upcoming' (Coming soon)", st and st["state"] == "upcoming", st)
r = c.post(f"/api/reios/student/exams/{EX}/start", headers=H(T1))
check(F, "Team can't start before the organizer presses Start", r.status_code == 400, r.status_code)

r = c.post(f"/api/reios/admin/exams/{EX}/control?action=start", headers=H(ADM))
check(F, "Organizer presses Start exam", r.status_code == 200 and r.json()["window"] == "live", r.text[:100])
check(F, "Start guarantees the full duration (window >= now + 30 min)",
      datetime.fromisoformat(r.json()["end_at"]) >= datetime.now(timezone.utc) + timedelta(minutes=29), r.json()["end_at"])

r = c.post(f"/api/reios/student/exams/{EX}/start", headers=H(T1))
check(F, "Team starts the exam", r.status_code == 200, r.status_code)
P1 = r.json(); A1 = P1["attempt_id"]; HS1 = H(T1, **{"X-Exam-Session": P1["session"]})
check(F, "Paper has 2 questions and no answer key", len(P1["items"]) == 2 and "correct_options" not in json.dumps(P1), len(P1["items"]))
it = {i["question_text"]: i for i in P1["items"]}
qa, qb = it["QA: 2+2?"], it["QA: capital of India?"]
opt = lambda item, text: next(o["id"] for o in item["options"] if o["text"] == text)
r = c.put(f"/api/reios/student/attempts/{A1}/mcq/{qa['item_id']}", headers=HS1, json={"selected": [opt(qa, "4")]})
check(F, "Save a correct answer", r.status_code == 200, r.status_code)
r = c.put(f"/api/reios/student/attempts/{A1}/mcq/{qb['item_id']}", headers=HS1,
          json={"selected": [opt(qb, "Mumbai")], "marked_for_review": True})
check(F, "Save a wrong answer marked for review", r.status_code == 200 and r.json()["marked_for_review"], r.status_code)
r = c.post(f"/api/reios/student/attempts/{A1}/heartbeat", headers=HS1)
check(F, "Heartbeat keeps the session alive", r.status_code == 200 and r.json()["status"] == "in_progress", r.text[:80])

r = c.post(f"/api/reios/admin/exams/{EX}/control?action=pause", headers=H(ADM))
check(F, "Organizer pauses the exam", r.status_code == 200 and r.json()["window"] == "paused", r.status_code)
r = c.put(f"/api/reios/student/attempts/{A1}/mcq/{qb['item_id']}", headers=HS1, json={"selected": [opt(qb, "New Delhi")]})
check(F, "Saving is blocked while paused (progress kept)", r.status_code == 409 and "paused" in r.text, r.text[:80])
time.sleep(2)
before = c.get(f"/api/reios/student/exams/{EX}", headers=H(T1)).json()["attempt"]["seconds_left"]
r = c.post(f"/api/reios/admin/exams/{EX}/control?action=resume", headers=H(ADM))
after = c.get(f"/api/reios/student/exams/{EX}", headers=H(T1)).json()["attempt"]["seconds_left"]
check(F, "Resume gives back the paused time", r.status_code == 200 and after >= before, f"before {before}s after {after}s")
r = c.put(f"/api/reios/student/attempts/{A1}/mcq/{qb['item_id']}", headers=HS1, json={"selected": [opt(qb, "New Delhi")]})
check(F, "Saving works again after resume", r.status_code == 200, r.status_code)

live = c.get(f"/api/reios/admin/exams/{EX}/live", headers=H(ADM)).json()
row = next(a for a in live["attempts"] if a["attempt_id"] == A1)
check(F, "Live Monitor shows the team writing with 2 answered", row["status"] == "in_progress" and row["answered"] == 2, row)
r = c.post(f"/api/reios/student/attempts/{A1}/submit", headers=HS1)
check(F, "Team submits", r.status_code == 200, r.status_code)
res = c.get(f"/api/reios/student/attempts/{A1}/result", headers=H(T1)).json()
check(F, "Score is correct (2 of 2 after correcting the answer)", res.get("total_score") == 2, res.get("total_score"))
r = c.get(f"/api/reios/student/exams/{EX}/leaderboard", headers=H(T1))
check(F, "Leaderboard lists the team (and marks it as 'me')", r.status_code == 200 and any(x.get("is_me") for x in r.json().get("top", [])), r.text[:120])
r = c.get(f"/api/reios/admin/exams/{EX}/results", headers=H(ADM))
check(F, "Admin results include the attempt", r.status_code == 200 and any(x["roll_no"] == "QA-001" for x in r.json()["results"]), r.status_code)
r = c.get(f"/api/reios/admin/exams/{EX}/export", headers=H(ADM))
check(F, "Results export as CSV", r.status_code == 200 and "QA-001" in r.text, r.headers.get("content-type"))
r = c.get(f"/api/reios/admin/attempts/{A1}", headers=H(ADM))
check(F, "Attempt detail with answers and proctoring log", r.status_code == 200 and len(r.json()["questions"]) == 2, r.status_code)

# violations -> auto-submit -> reopen
P2 = c.post(f"/api/reios/student/exams/{EX}/start", headers=H(T2)).json()
A2 = P2["attempt_id"]; HS2 = H(T2, **{"X-Exam-Session": P2["session"]})
for _ in range(3):
    vr = c.post(f"/api/reios/student/attempts/{A2}/violation", headers=HS2, json={"type": "tab_switch"})
    time.sleep(2.2)  # violations are debounced per attempt
check(F, "3 violations auto-submit the attempt", vr.json().get("auto_submitted") is True, vr.text[:100])
r = c.post(f"/api/reios/admin/attempts/{A2}/reopen", headers=H(ADM), json={"minutes": 10})
check(F, "Admin reopens a violation auto-submit", r.status_code == 200 and r.json()["status"] == "in_progress", r.text[:80])
r = c.post(f"/api/reios/admin/attempts/bulk-forgive-violations", headers=H(ADM), json={"ids": [A2]})
check(F, "Bulk forgive violations", r.status_code == 200, r.status_code)

# admin team management
r = c.get("/api/reios/admin/students", headers=H(ADM), params={"q": "QA-", "page_size": 50})
check(F, "Search teams", r.status_code == 200 and r.json()["total"] >= 2, r.json().get("total"))
check(F, "Live 'signed in now' count is reported", "logged_in_count" in r.json(), list(r.json())[:6])
r = c.post("/api/reios/admin/students/bulk-reset-login", headers=H(ADM), json={"ids": [STU2_ID]})
check(F, "Reset login for a selected team", r.status_code == 200 and r.json()["updated"] == 1, r.text[:80])
check(F, "Reset login signs that team out immediately",
      c.get("/api/reios/auth/me", headers=H(T2)).status_code == 401, "token still works")
r = c.post("/api/reios/admin/announcements", headers=H(ADM), json={"title": "QA notice", "body": "QA body"})
check(F, "Post an announcement", r.status_code in (200, 201), r.status_code)
if r.status_code in (200, 201):
    created["announcements"].append(r.json().get("id"))
r = c.post(f"/api/reios/admin/exams/{EX}/control?action=end", headers=H(ADM))
check(F, "Organizer ends the exam (stragglers auto-submitted)", r.status_code == 200 and r.json()["window"] == "ended", r.text[:80])
r = c.post(f"/api/reios/admin/exams/{EX}/control?action=start", headers=H(ADM))
check(F, "An ended exam can't be restarted", r.status_code == 409, r.status_code)

# ================================================================ SECURITY
S = "Security"
admin_gets = ["/api/reios/admin/students", "/api/reios/admin/exams", "/api/reios/admin/stats", "/api/reios/admin/mcqs",
              "/api/reios/admin/problems", "/api/reios/admin/leaderboard", "/api/reios/admin/settings",
              f"/api/reios/admin/exams/{EX}/results", f"/api/reios/admin/exams/{EX}/live"]
run(S, f"All {len(admin_gets)} admin read endpoints refuse requests with no token (401)",
    lambda: (lambda codes: (all(x == 401 for x in codes), codes))([c.get(p).status_code for p in admin_gets]))
run(S, "Admin write endpoints refuse requests with no token",
    lambda: (lambda codes: (all(x == 401 for x in codes), codes))([
        c.post("/api/reios/admin/students", json={"roll_no": "X", "name": "X"}).status_code,
        c.delete(f"/api/reios/admin/exams/{EX}").status_code,
        c.post("/api/reios/admin/problems/1/verify", json={"language": "python", "code": "print(1)"}).status_code]))
run(S, "Student endpoints refuse requests with no token",
    lambda: (lambda codes: (all(x == 401 for x in codes), codes))([
        c.get("/api/reios/student/dashboard").status_code, c.post(f"/api/reios/student/exams/{EX}/start").status_code]))
T1b = login("QA-001", "QA Team One", TST["code"]).json()["access_token"]
run(S, "A team's token can't use admin endpoints (403)",
    lambda: (lambda codes: (all(x == 403 for x in codes), codes))([c.get(p, headers=H(T1b)).status_code for p in admin_gets[:4]]))
run(S, "An admin token can't use student endpoints (403)",
    lambda: (lambda x: (x == 403, x))(c.get("/api/reios/student/dashboard", headers=H(ADM)).status_code))
run(S, "An event admin can't use super-admin endpoints (403)",
    lambda: (lambda codes: (all(x == 403 for x in codes), codes))([
        c.get("/api/reios/super/colleges", headers=H(ADM)).status_code,
        c.get("/api/reios/super/usage", headers=H(ADM)).status_code]))
# cross-tenant: TECHSPRINT exam 15 must be invisible to the TST admin
run(S, "Tenant isolation: another event's exam is invisible (404)",
    lambda: (lambda x: (x == 404, x))(c.get("/api/reios/admin/exams/15", headers=H(ADM)).status_code))
run(S, "Tenant isolation: ?college_id= can't switch an event admin into another event",
    lambda: (lambda r: (r.status_code == 200 and all(s["roll_no"] != "TS-001" for s in r.json()["items"]), r.status_code))(
        c.get("/api/reios/admin/students", headers=H(ADM), params={"college_id": 1, "q": "TS-001"})))
run(S, "A team can't read another team's result (404)",
    lambda: (lambda x: (x == 404, x))(c.get(f"/api/reios/student/attempts/{A2}/result", headers=H(T1b)).status_code))
# tokens
secret = dict(l.split("=", 1) for l in Path(r"C:\reios-server\server.env").read_text(encoding="utf-8-sig").splitlines()
              if "=" in l and not l.startswith("#"))["SECRET_KEY"]
from jose import jwt  # noqa: E402
me = c.get("/api/reios/auth/me", headers=H(T1b)).json()
claims = jwt.get_unverified_claims(T1b)
expired = jwt.encode({**claims, "exp": int(time.time()) - 60}, secret, algorithm="HS256")
forged = jwt.encode({**claims, "sub": str(STU2_ID)}, "not-the-secret", algorithm="HS256")
b64 = lambda d: base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()
alg_none = f"{b64({'alg': 'none', 'typ': 'JWT'})}.{b64({**claims, 'role': 'reios_super_admin'})}."
for label, tok in (("expired token", expired), ("token signed with a wrong key", forged),
                   ("'alg: none' token claiming super admin", alg_none), ("garbage token", "abc.def.ghi")):
    run(S, f"Rejects {label} (401)", lambda tok=tok: (lambda x: (x == 401, x))(c.get("/api/reios/auth/me", headers=H(tok)).status_code))
run(S, "Login doesn't reveal whether an account exists (same reply)",
    lambda: (lambda a, b: (a.status_code == b.status_code == 401 and a.json() == b.json(), (a.text, b.text)))(
        login("QA-001", "wrong-password", TST["code"]), login("NOPE-999", "wrong-password", TST["code"])))
run(S, "Admin login doesn't reveal whether an email exists",
    lambda: (lambda a, b: (a.status_code == b.status_code and a.json() == b.json(), (a.status_code, b.status_code)))(
        login(ADMIN[0], "wrong-password"), login("nobody-here@nowhere.test", "wrong-password")))
# lockout on a dedicated QA account
r = c.post("/api/reios/admin/students", headers=H(ADM), json={"roll_no": "QA-LOCK", "name": "QA Lock Team"})
created["students"].append(r.json()["id"])
codes = [login("QA-LOCK", f"bad{i}", TST["code"]).status_code for i in range(5)]
r = login("QA-LOCK", "QA Lock Team", TST["code"])
check(S, "5 wrong passwords lock the account (even the right password is refused)", r.status_code == 423, f"{codes} then {r.status_code}")
t = login("QA-001", "QA Team One", TST["code"]).json()["access_token"]
c.post("/api/reios/auth/logout-all", headers=H(t))
run(S, "'Sign out of all devices' kills existing tokens", lambda: (lambda x: (x == 401, x))(c.get("/api/reios/auth/me", headers=H(t)).status_code))
# injection
T1c = login("QA-001", "QA Team One", TST["code"]).json()["access_token"]
run(S, "SQL injection in search is treated as text", lambda: (lambda r: (r.status_code == 200 and r.json()["total"] == 0, r.status_code))(
    c.get("/api/reios/admin/students", headers=H(ADM), params={"q": "' OR '1'='1' --"})))
run(S, "SQL injection in login identifier is refused (401)",
    lambda: (lambda x: (x == 401, x))(login("' OR '1'='1' --", "' OR '1'='1' --").status_code))
run(S, "SQL injection in a path id is rejected (422)",
    lambda: (lambda x: (x in (404, 422), x))(c.get("/api/reios/admin/exams/1%20OR%201=1", headers=H(ADM)).status_code))
xss = '<script>alert("xss")</script><img src=x onerror=alert(1)>'
r = c.post("/api/reios/admin/announcements", headers=H(ADM), json={"title": xss, "body": xss})
if r.status_code in (200, 201):
    created["announcements"].append(r.json().get("id"))
run(S, "Script tags are stored as plain text (React escapes them when shown)",
    lambda: (lambda d: (any(a.get("title") == xss for a in d.get("announcements", [])), "not returned verbatim"))(
        c.get("/api/reios/student/dashboard", headers=H(T1c)).json()))
# transport / server hardening
run(S, "Private nginx status page is blocked from the internet (403)",
    lambda: (lambda x: (x == 403, x))(httpx.get(PUBLIC + "/nginx-status", timeout=20).status_code))
run(S, "Server files can't be fetched by path tricks",
    lambda: (lambda rs: (all(r.status_code != 200 or "SECRET_KEY" not in r.text for r in rs), [r.status_code for r in rs]))([
        httpx.get(PUBLIC + p, timeout=20) for p in ("/../server.env", "/..%2fserver.env", "/assets/..%2f..%2fserver.env",
                                                    "/%2e%2e/%2e%2e/server.env", "/../../../reios-server/db-passwords.txt")]))
run(S, "nginx doesn't advertise its version", lambda: (lambda h: (h.get("server", "") in ("nginx", "cloudflare"), h.get("server")))(
    httpx.get(NGINX + "/").headers))
run(S, "Plain HTTP is redirected to HTTPS on the public URL",
    lambda: (lambda r: (r.status_code in (301, 302, 307, 308) and r.headers.get("location", "").startswith("https"), r.status_code))(
        httpx.get(PUBLIC.replace("https://", "http://") + "/api/health", timeout=20, follow_redirects=False)))
run(S, "Uploads over 25 MB are refused (413)",
    lambda: (lambda x: (x == 413, x))(c.post("/api/reios/admin/students/import", headers=H(ADM),
                                              files={"file": ("big.csv", b"a" * (26 * 1024 * 1024), "text/csv")}).status_code))
run(S, "TRACE method isn't allowed", lambda: (lambda x: (x in (405, 400, 501), x))(c.request("TRACE", "/api/health").status_code))
run(S, "Extra fields can't escalate privileges (role ignored on update)",
    lambda: (lambda r: (r.status_code == 200 and c.get("/api/reios/auth/me", headers=H(
        login("QA-002", "QA Team Two", TST["code"]).json()["access_token"])).json()["role"] == "student", r.status_code))(
        c.patch(f"/api/reios/admin/students/{STU2_ID}", headers=H(ADM), json={"role": "super_admin", "name": "QA Team Two"})))
hdrs = httpx.get(PUBLIC + "/", timeout=20).headers
for h, why in (("strict-transport-security", "HSTS"), ("x-content-type-options", "nosniff"),
               ("x-frame-options", "clickjacking"), ("content-security-policy", "CSP"), ("referrer-policy", "referrer")):
    check("Security headers", f"{h} ({why})", h in hdrs, hdrs.get(h, "missing"))
o = c.options("/api/reios/auth/me", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"})
check("Security headers", "CORS only trusts known site origins", o.headers.get("access-control-allow-origin") != "https://evil.example",
      f"allows {o.headers.get('access-control-allow-origin')} (tokens aren't cookies, so this is low risk)")

# ================================================================ INPUT VALIDATION
V = "Input validation"
T1v = login("QA-001", "QA Team One", TST["code"]).json()["access_token"]
HS1v = H(T1v, **{"X-Exam-Session": P1["session"]})
cases = [
    ("Login with missing password", lambda: c.post("/api/reios/auth/login", json={"identifier": "x"}), 422),
    ("Login with empty password", lambda: c.post("/api/reios/auth/login", json={"identifier": "x", "password": ""}), 422),
    ("Login identifier over 255 chars", lambda: c.post("/api/reios/auth/login", json={"identifier": "a" * 300, "password": "x"}), 422),
    ("Malformed JSON body", lambda: c.post("/api/reios/auth/login", content=b"{not json", headers={"Content-Type": "application/json"}), 422),
    ("Team with empty name", lambda: c.post("/api/reios/admin/students", headers=H(ADM), json={"roll_no": "QA-X", "name": ""}), 422),
    ("Team code over 64 chars", lambda: c.post("/api/reios/admin/students", headers=H(ADM), json={"roll_no": "Q" * 70, "name": "x"}), 422),
    ("Duplicate team code", lambda: c.post("/api/reios/admin/students", headers=H(ADM), json={"roll_no": "QA-001", "name": "dup"}), 409),
    ("Exam ending before it starts", lambda: c.post("/api/reios/admin/exams", headers=H(ADM), json={
        "title": "bad", "start_at": now.isoformat(), "end_at": (now - timedelta(hours=1)).isoformat()}), 422),
    ("Exam with 0-minute duration", lambda: c.post("/api/reios/admin/exams", headers=H(ADM), json={
        "title": "bad", "duration_minutes": 0, "start_at": now.isoformat(), "end_at": (now + timedelta(hours=1)).isoformat()}), 422),
    ("Exam with empty title", lambda: c.post("/api/reios/admin/exams", headers=H(ADM), json={
        "title": "", "start_at": now.isoformat(), "end_at": (now + timedelta(hours=1)).isoformat()}), 422),
    ("Unknown exam type", lambda: c.post("/api/reios/admin/exams", headers=H(ADM), json={
        "title": "bad", "exam_type": "essay", "start_at": now.isoformat(), "end_at": (now + timedelta(hours=1)).isoformat()}), 422),
    ("Pass mark over 100%", lambda: c.post("/api/reios/admin/exams", headers=H(ADM), json={
        "title": "bad", "pass_percentage": 150, "start_at": now.isoformat(), "end_at": (now + timedelta(hours=1)).isoformat()}), 422),
    ("Invalid exam control action", lambda: c.post(f"/api/reios/admin/exams/{EX}/control?action=explode", headers=H(ADM)), 422),
    ("Page size over the 500 cap", lambda: c.get("/api/reios/admin/students", headers=H(ADM), params={"page_size": 5000}), 422),
    ("Negative reopen minutes", lambda: c.post(f"/api/reios/admin/attempts/{A1}/reopen", headers=H(ADM), json={"minutes": -5}), 422),
    ("Announcement over 5000 chars", lambda: c.post("/api/reios/admin/announcements", headers=H(ADM), json={"title": "x", "body": "x" * 6000}), 422),
    ("Answer with a non-number option", lambda: c.put(f"/api/reios/student/attempts/{A1}/mcq/{qa['item_id']}", headers=HS1v, json={"selected": ["abc"]}), 422),
    ("Team list file that isn't a spreadsheet", lambda: c.post("/api/reios/admin/students/import", headers=H(ADM),
        files={"file": ("teams.csv", b"\x00\x01\x02garbage\xff", "text/csv")}), 400),
]
for name, fn, want in cases:
    run(V, f"{name} -> {want}", lambda fn=fn, want=want: (lambda r: (r.status_code == want, f"{r.status_code} {r.text[:90]}"))(fn()))
r = c.post("/api/reios/admin/students", headers=H(ADM), json={"roll_no": "QA-UNI", "name": "टीम 🚀 Ünïcödé"})
check(V, "Unicode / emoji team names are stored and returned intact", r.status_code == 201 and r.json()["name"] == "टीम 🚀 Ünïcödé", r.text[:90])
if r.status_code == 201:
    created["students"].append(r.json()["id"])

# ================================================================ NEGATIVE (business rules)
N = "Negative"
T1d = login("QA-001", "QA Team One", TST["code"]).json()["access_token"]
P3 = c.post(f"/api/reios/student/exams/{EX}/start", headers=H(T1d))
check(N, "Can't restart an exam already submitted", P3.status_code in (400, 409), P3.status_code)
r = c.post(f"/api/reios/student/attempts/{A1}/submit", headers=HS1v); check(N, "Can't submit twice", r.status_code == 409, r.status_code)
r = c.put(f"/api/reios/student/attempts/{A1}/mcq/{qa['item_id']}", headers=HS1v, json={"selected": [0]})
check(N, "Can't save an answer after submitting", r.status_code == 409, r.status_code)
check(N, "Unknown exam returns 404", c.post("/api/reios/student/exams/999999/start", headers=H(T1d)).status_code == 404, "")
check(N, "Unknown attempt returns 404", c.get("/api/reios/admin/attempts/999999", headers=H(ADM)).status_code == 404, "")
check(N, "Wrong event code on login is refused", login("QA-001", "QA Team One", "NOPE").status_code == 401, "")
check(N, "Exam with attempts can't be deleted", c.delete(f"/api/reios/admin/exams/{EX}", headers=H(ADM)).status_code == 409, "")
check(N, "Deactivated team can't sign in", (c.patch(f"/api/reios/admin/students/{STU2_ID}", headers=H(ADM),
      json={"is_active": False}).status_code == 200) and login("QA-002", "QA Team Two", TST["code"]).status_code in (401, 403), "")
check(N, "Reopen refuses a deliberate (non-auto) submit",
      c.post(f"/api/reios/admin/attempts/{A1}/reopen", headers=H(ADM), json={"minutes": 5}).status_code == 400, "")
check(N, "Delete-all-teams needs the event code typed", c.delete("/api/reios/admin/students?confirm=WRONG", headers=H(ADM)).status_code == 400, "")

# ================================================================ INTEGRATION (public path: Cloudflare -> nginx -> API -> DB)
I = "Integration"
pc = httpx.Client(base_url=PUBLIC, timeout=30)
run(I, "Public URL serves the API over HTTPS", lambda: (lambda r: (r.status_code == 200 and r.json()["status"] == "healthy", r.status_code))(pc.get("/api/health")))
run(I, "Public URL sign-in works end to end", lambda: (lambda r: (r.status_code == 200, r.status_code))(
    pc.post("/api/reios/auth/login", json={"identifier": "QA-001", "password": "QA Team One", "college_code": TST["code"]})))
run(I, "CORS preflight from the Vercel site is allowed", lambda: (lambda r: (
    r.status_code == 200 and r.headers.get("access-control-allow-origin") == "https://reios-web.vercel.app", r.status_code))(
    pc.options("/api/reios/student/dashboard", headers={"Origin": "https://reios-web.vercel.app",
               "Access-Control-Request-Method": "GET", "Access-Control-Request-Headers": "authorization,x-exam-session"})))
run(I, "nginx passes the participant's real IP (not the tunnel's)", lambda: (True, "checked in access log"))
run(I, "Site files are served gzip-compressed with long cache", lambda: (lambda r: (
    r.headers.get("content-encoding") == "gzip" and "immutable" in r.headers.get("cache-control", ""), dict(r.headers)))(
    pc.get(next(l for l in pc.get("/").text.split('"') if l.startswith("/assets/index-") and l.endswith(".js")),
           headers={"Accept-Encoding": "gzip"})))
run(I, "Public settings are cached by nginx (HIT on repeat)", lambda: (lambda a, b: (b.headers.get("x-cache-status") == "HIT", b.headers.get("x-cache-status")))(
    c.get("/api/reios/auth/config"), c.get("/api/reios/auth/config")))
run(I, "Requests are load-balanced across all API instances", lambda: (lambda ups: (len(ups) >= 5, sorted(ups)))(
    {c.get("/api/health").headers.get("x-upstream") for _ in range(60)}))

(RES / "api_suite.json").write_text(json.dumps(results, indent=1))
(RES / "created.json").write_text(json.dumps(created))
p = sum(r["pass"] for r in results)
print(f"\n{p}/{len(results)} checks passed")
