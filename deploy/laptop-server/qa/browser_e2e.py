import os
"""
Real-browser end-to-end tests (headless Chrome) on the laptop-served site, which is the same build
Vercel serves. Admin: every console page. Team: full exam through the UI. Security: stored script
never executes. Results -> results/browser_e2e.json, screenshots -> results/shots/.
"""
import base64, json, subprocess, sys, time, urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import websocket

SITE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8080"
RES = Path(r"C:\reios-server\qa\results"); SHOTS = RES / "shots"; SHOTS.mkdir(parents=True, exist_ok=True)
results = []
created = json.loads((RES / "created.json").read_text())
api = httpx.Client(base_url="http://127.0.0.1:8080", timeout=60)


def check(cat, name, cond, detail=""):
    results.append({"category": cat, "name": name, "pass": bool(cond), "detail": str(detail)[:220]})
    print(("PASS " if cond else "FAIL ") + f"[{cat}] {name}" + ("" if cond else f"  -> {str(detail)[:160]}"))


# --- set up a live exam for the browser team (TST event only)
adm = api.post("/api/reios/auth/login", json={"identifier": os.environ["QA_ADMIN_EMAIL"], "password": os.environ["QA_ADMIN_PASSWORD"]}).json()["access_token"]
AH = {"Authorization": "Bearer " + adm}
now = datetime.now(timezone.utc)
ex = api.post("/api/reios/admin/exams", headers=AH, json={
    "title": "QA Browser Exam", "exam_type": "mcq", "duration_minutes": 30, "require_fullscreen": False,
    "show_results": True, "show_answers": True, "start_at": (now + timedelta(days=1)).isoformat(),
    "end_at": (now + timedelta(days=2)).isoformat()}).json()
EX = ex["id"]; created["exams"].append(EX)
qs = []
for text, opts, right in (("QA UI: 5+5?", ["9", "10", "11"], 1), ("QA UI: largest planet?", ["Mars", "Jupiter", "Venus"], 1)):
    q = api.post("/api/reios/admin/mcqs", headers=AH, json={"section": "QA", "question_text": text,
                                                            "options": opts, "correct_options": [right]}).json()
    qs.append(q["id"]); created["mcqs"].append(q["id"])
api.put(f"/api/reios/admin/exams/{EX}/items", headers=AH, json={"items": [{"item_type": "mcq", "question_id": i} for i in qs]})
api.post(f"/api/reios/admin/exams/{EX}/publish", headers=AH)
api.post(f"/api/reios/admin/exams/{EX}/control?action=start", headers=AH)
team = api.post("/api/reios/admin/students", headers=AH, json={"roll_no": "QA-UI", "name": "QA Browser Team"}).json()
created["students"].append(team["id"])
(RES / "created.json").write_text(json.dumps(created))

# --- browser
PORT = 9701
chrome = subprocess.Popen([r"C:\Program Files\Google\Chrome\Application\chrome.exe", "--headless=new",
                           f"--remote-debugging-port={PORT}", "--window-size=1400,900", "--no-first-run",
                           "--remote-allow-origins=*", "--user-data-dir=" + str(RES / "_chrome")],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
for _ in range(240):
    try:
        url = json.load(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json/version"))["webSocketDebuggerUrl"]; break
    except Exception:
        time.sleep(0.5)
ws = websocket.create_connection(url, timeout=90)
n = [0]; errors = []; failed = []; dialogs = []


def send(m, p=None, sid=None):
    n[0] += 1
    msg = {"id": n[0], "method": m, "params": p or {}}
    if sid: msg["sessionId"] = sid
    ws.send(json.dumps(msg))
    while True:
        r = json.loads(ws.recv())
        meth = r.get("method")
        if meth == "Runtime.exceptionThrown":
            d = r["params"]["exceptionDetails"]; errors.append(str(d.get("exception", {}).get("description") or d.get("text"))[:200])
        elif meth == "Page.javascriptDialogOpening":
            dialogs.append(r["params"].get("message"))
            ws.send(json.dumps({"id": 0, "method": "Page.handleJavaScriptDialog", "params": {"accept": True}, "sessionId": r.get("sessionId")}))
        elif meth == "Network.responseReceived":
            resp = r["params"]["response"]
            if "/api/" in resp["url"] and resp["status"] >= 500:
                failed.append(f'{resp["status"]} {resp["url"][:90]}')
        if r.get("id") == n[0]:
            return r.get("result", {})


def new_tab():
    t = send("Target.createTarget", {"url": "about:blank"})["targetId"]
    sid = send("Target.attachToTarget", {"targetId": t, "flatten": True})["sessionId"]
    for d in ("Page.enable", "Runtime.enable", "Network.enable"): send(d, {}, sid)
    return sid


def ev(sid, e):
    return send("Runtime.evaluate", {"expression": e, "returnByValue": True, "awaitPromise": True}, sid).get("result", {}).get("value")


def wait(sid, expr, secs=20):
    for _ in range(secs * 2):
        if ev(sid, expr): return True
        time.sleep(0.5)
    return False


def shot(sid, name):
    (SHOTS / f"{name}.png").write_bytes(base64.b64decode(send("Page.captureScreenshot", {"format": "png"}, sid)["data"]))


def sign_in(sid, ident, pw):
    send("Page.navigate", {"url": SITE + "/login"}, sid)
    wait(sid, "document.readyState === 'complete'")
    ev(sid, "localStorage.clear()")  # sign out whoever used this browser before
    send("Page.navigate", {"url": SITE + "/login"}, sid)
    wait(sid, "!!document.getElementById('identifier')")
    ev(sid, f"""(() => {{ const set = (el, v) => {{ const d = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
      d.call(el, v); el.dispatchEvent(new Event('input', {{bubbles:true}})); }};
      set(document.getElementById('identifier'), {json.dumps(ident)}); set(document.getElementById('password'), {json.dumps(pw)}); }})()""")
    ev(sid, "document.querySelector('form').requestSubmit()")


click_text = lambda sid, sel, text: ev(sid, f"""(() => {{ const el = [...document.querySelectorAll({json.dumps(sel)})]
    .find(e => e.textContent.trim().includes({json.dumps(text)})); if (el) {{ el.click(); return true; }} return false; }})()""")

# ===================== admin pages
B = "Browser (admin)"
a = new_tab()
sign_in(a, os.environ["QA_ADMIN_EMAIL"], os.environ["QA_ADMIN_PASSWORD"])
check(B, "Admin signs in through the login page", wait(a, "location.pathname.startsWith('/console')"), ev(a, "location.pathname"))
for path, must in (("/console", "Overview"), ("/console/students", "Teams"), ("/console/exams", "Exams"),
                   (f"/console/exams/{EX}", "QA Browser Exam"), (f"/console/exams/{EX}/results", "Results"),
                   (f"/console/exams/{EX}/live", "Live"), ("/console/live", "Live"), ("/console/leaderboard", "Leaderboard"),
                   ("/console/announcements", "Announcements"), ("/console/mcqs", "MCQ"), ("/console/account", "Account")):
    errors.clear(); failed.clear()
    send("Page.navigate", {"url": SITE + path}, a)
    ok = wait(a, f"document.body.innerText.includes({json.dumps(must)})", 20)
    time.sleep(1)
    check(B, f"{path} renders with no JS errors or server errors", ok and not errors and not failed,
          {"rendered": ok, "js": errors[:2], "api": failed[:2]})
shot(a, "admin-live-monitor")

# ===================== team takes the exam through the UI
T = "Browser (team)"
s = new_tab()
errors.clear(); failed.clear(); dialogs.clear()
sign_in(s, "QA-UI", "QA Browser Team")
check(T, "Team signs in with team code + team name", wait(s, "location.pathname === '/student'"), ev(s, "location.pathname"))
check(T, "Dashboard shows the live exam with a Start button",
      wait(s, "document.body.innerText.includes('QA Browser Exam') && document.body.innerText.includes('Start exam')"), "")
xss_safe = not dialogs and ev(s, "document.body.innerText.includes('<script>')") is not None
check(T, "Stored <script> announcement is shown as text and never runs", not dialogs, f"dialogs: {dialogs}")
shot(s, "team-dashboard")
click_text(s, "a", "Start exam")
check(T, "Rules page appears before the exam starts", wait(s, "document.body.innerText.includes('I have read the rules')"), "")
start_disabled = ev(s, "[...document.querySelectorAll('button')].find(b => b.textContent.trim()==='Start exam')?.disabled")
check(T, "Start stays disabled until the rules are accepted", start_disabled is True, start_disabled)
ev(s, "document.querySelector('label.check input').click()")
click_text(s, "button", "Start exam")
check(T, "Exam opens on question 1 with a running timer", wait(s, "!!document.querySelector('ul.options') && !!document.querySelector('.timer')"), "")
shot(s, "team-exam-question")
answers = {"QA UI: 5+5?": "10", "QA UI: largest planet?": "Jupiter"}
for i in range(2):
    ev(s, f"document.querySelectorAll('.pal-btn')[{i}].click()")
    time.sleep(0.8)
    q = ev(s, "document.querySelector('.exam-body .card')?.innerText || ''")
    want = next(v for k, v in answers.items() if k in q)
    ev(s, f"""(() => {{ const l = [...document.querySelectorAll('ul.options label')].find(x => x.textContent.trim().replace(/^[A-Z]\.\s*/, '') === {json.dumps(want)});
        l.querySelector('input').click(); }})()""")
    time.sleep(1.2)
check(T, "Both answers saved (palette shows 2 answered)", wait(s, "document.querySelectorAll('.pal-btn.answered').length === 2", 10),
      ev(s, "document.querySelectorAll('.pal-btn.answered').length"))
click_text(s, "button", "Submit exam")
wait(s, "document.body.innerText.includes('Submit exam?')", 10)
ev(s, "(() => { const m = [...document.querySelectorAll('.modal button, [role=dialog] button')]; const b = m.reverse().find(x => x.textContent.includes('Submit exam')); b && b.click(); })()")
done = wait(s, "!document.querySelector('ul.options')", 20)
time.sleep(1.5)
shot(s, "team-after-submit")
check(T, "Submitting ends the exam", done, ev(s, "document.body.innerText.slice(0,120)"))
att = api.get(f"/api/reios/admin/exams/{EX}/results", headers=AH).json()["results"]
row = next((x for x in att if x["roll_no"] == "QA-UI"), {})
check(T, "Server recorded the UI answers correctly (2/2)", row.get("total_score") == 2 and row.get("status") == "submitted", row)
check(T, "No JS errors or server errors during the whole exam", not errors and not failed, {"js": errors[:2], "api": failed[:2]})

ws.close(); chrome.terminate()
(RES / "browser_e2e.json").write_text(json.dumps(results, indent=1))
print(f"\n{sum(r['pass'] for r in results)}/{len(results)} browser checks passed")
