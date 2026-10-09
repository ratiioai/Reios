"""
Signs in as every student/team in the database through nginx, opens their dashboard, and signs out.
Event teams' password is their team name (unless they changed it); anyone whose password isn't
known is reported separately rather than guessed at repeatedly (one try only, so no lockouts).
"""
import sys
from collections import Counter
from pathlib import Path

import httpx
import psycopg

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8080"
env = dict(l.split("=", 1) for l in Path(r"C:\reios-server\server.env").read_text(encoding="utf-8-sig").splitlines()
           if "=" in l and not l.startswith("#"))
dsn = env["DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://")

with psycopg.connect(dsn) as conn:
    rows = conn.execute("""
        SELECT u.id, u.roll_no, u.name, u.is_active, c.code, c.name, c.org_type, u.must_change_password
        FROM reios_users u JOIN reios_colleges c ON c.id = u.college_id
        WHERE u.role = 'STUDENT' ORDER BY c.code, u.roll_no""").fetchall()
    before = {r[0]: r for r in conn.execute(
        "SELECT id, failed_login_attempts, locked_until FROM reios_users WHERE role = 'STUDENT'").fetchall()}

results = Counter()
problems = []
with httpx.Client(base_url=BASE, timeout=30) as c:
    for uid, roll, name, active, code, org, org_type, must_change in rows:
        r = c.post("/api/reios/auth/login", json={"identifier": roll, "password": name, "college_code": code})
        if r.status_code != 200:
            key = "inactive" if not active else f"login {r.status_code}"
            results[(org, key)] += 1
            problems.append(f"{org} {roll} ({name}): {r.status_code} {r.text[:80]}")
            continue
        h = {"Authorization": "Bearer " + r.json()["access_token"]}
        me = c.get("/api/reios/auth/me", headers=h)
        dash = c.get("/api/reios/student/dashboard", headers=h)
        out = c.post("/api/reios/auth/logout", headers=h)
        if me.status_code == dash.status_code == out.status_code == 200 and me.json()["roll_no"] == roll:
            results[(org, "ok")] += 1
        else:
            results[(org, "dashboard/logout failed")] += 1
            problems.append(f"{org} {roll}: me {me.status_code} dash {dash.status_code} logout {out.status_code}")

print(f"{len(rows)} student/team accounts tested through {BASE}")
for (org, outcome), n in sorted(results.items()):
    print(f"  {org:25} {outcome:28} {n}")
if problems:
    print("Not signed in (first 15):")
    for p in problems[:15]:
        print("  ", p)

# Undo the side effects of any failed tries so nobody starts the event one wrong attempt closer to lockout
with psycopg.connect(dsn) as conn:
    for uid, (_, failed, locked) in before.items():
        conn.execute("UPDATE reios_users SET failed_login_attempts = %s, locked_until = %s WHERE id = %s",
                     (failed, locked, uid))
    conn.commit()
