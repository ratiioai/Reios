"""
Browser check of the Vercel-style setup: site on one origin, API on another (read from backend.json),
then the server's address changes while the page is open - the page must follow it on its own.
  python vercel_flow_check.py <site_url> <site_dir> <old_api> <new_api> <relay_pid> <email> <password>
"""
import base64, json, os, subprocess, sys, time, urllib.request
from pathlib import Path
import websocket

SITE, SITE_DIR, OLD_API, NEW_API, RELAY_PID, EMAIL, PWD = sys.argv[1:8]
OUT = Path(r"C:\reios-server\logs\vercel-flow"); OUT.mkdir(parents=True, exist_ok=True)
PORT = 9688
Path(SITE_DIR, "backend.json").write_text(json.dumps({"api": OLD_API}))

chrome = subprocess.Popen([r"C:\Program Files\Google\Chrome\Application\chrome.exe", "--headless=new",
                           f"--remote-debugging-port={PORT}", "--window-size=1400,900", "--no-first-run",
                           "--remote-allow-origins=*", "--user-data-dir=" + str(OUT / "_prof")],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
for _ in range(240):
    try:
        url = json.load(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json/version"))["webSocketDebuggerUrl"]; break
    except Exception:
        time.sleep(0.5)
ws = websocket.create_connection(url, timeout=90)
n = [0]; errors = []; api_hosts = []; failed = []


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
        elif meth == "Network.requestWillBeSent":
            u = r["params"]["request"]["url"]
            if "/api/" in u and r["params"]["request"]["method"] != "OPTIONS":
                api_hosts.append(u.split("/api/")[0])
        elif meth == "Network.responseReceived":
            resp = r["params"]["response"]
            if "/api/" in resp["url"] and resp["status"] >= 400:
                failed.append(f'{resp["status"]} {resp["url"][:90]}')
        if r.get("id") == n[0]:
            return r.get("result", {})


t = send("Target.createTarget", {"url": "about:blank"})["targetId"]
sid = send("Target.attachToTarget", {"targetId": t, "flatten": True})["sessionId"]
for d in ("Page.enable", "Runtime.enable", "Network.enable"): send(d, {}, sid)
ev = lambda e: send("Runtime.evaluate", {"expression": e, "returnByValue": True, "awaitPromise": True}, sid).get("result", {}).get("value")


def wait_for(expr, secs=20):
    for _ in range(secs * 2):
        if ev(expr): return True
        time.sleep(0.5)
    return False


send("Page.navigate", {"url": SITE + "/login"}, sid)
wait_for("!!document.getElementById('identifier')")
ev(f"""(() => {{ const set = (el, v) => {{ const d = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
  d.call(el, v); el.dispatchEvent(new Event('input', {{bubbles:true}})); }};
  set(document.getElementById('identifier'), {json.dumps(EMAIL)}); set(document.getElementById('password'), {json.dumps(PWD)}); }})()""")
ev("document.querySelector('form').requestSubmit()")
wait_for("location.pathname.startsWith('/console')")
time.sleep(3)
print("1. signed in on the site origin:", ev("location.origin + location.pathname"))
print("   API calls went to:", sorted(set(api_hosts)), "| failures:", failed, "| js errors:", errors)
assert set(api_hosts) == {OLD_API}, "calls didn't go to the backend.json address"

# The server restarts under a new address: backend.json changes, the old address dies
api_hosts.clear(); failed.clear()
Path(SITE_DIR, "backend.json").write_text(json.dumps({"api": NEW_API}))
subprocess.run(["taskkill", "/PID", RELAY_PID, "/T", "/F"], capture_output=True)
time.sleep(1)
# Navigate inside the app (no reload) - this is what a participant mid-session does
ev("[...document.querySelectorAll('nav a')].find(a => a.textContent.includes('Students')).click()")
wait_for("document.body.innerText.includes('TEAM CODE') || document.body.innerText.includes('Roll no')", 30)
time.sleep(2)
body = ev("document.querySelector('main').innerText.slice(0, 160)").replace("\n", " | ")
print("2. after the address changed, WITHOUT reloading the page:")
print("   API calls went to:", sorted(set(api_hosts)), "| failures:", failed, "| js errors:", errors)
print("   page shows:", body)
(OUT / "after-move.png").write_bytes(base64.b64decode(send("Page.captureScreenshot", {"format": "png"}, sid)["data"]))
ok = NEW_API in api_hosts and not errors and "TEAM" in body.upper()
print("RESULT:", "PASS - the open page followed the server to its new address" if ok else "FAIL")
ws.close(); chrome.terminate()
