"""Database & data-integrity checks on the live DB (read-only), plus a backup-restore drill into a scratch DB."""
import json
import os
import subprocess
from pathlib import Path

import psycopg

RES = Path(r"C:\reios-server\qa\results")
env = dict(l.split("=", 1) for l in Path(r"C:\reios-server\server.env").read_text(encoding="utf-8-sig").splitlines()
           if "=" in l and not l.startswith("#"))
dsn = env["DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://")
super_pw = Path(r"C:\reios-server\db-passwords.txt").read_text().splitlines()[0].split(": ")[1]
app_pw = Path(r"C:\reios-server\db-passwords.txt").read_text().splitlines()[1].split(": ")[1]
results = []


def check(cat, name, cond, detail=""):
    results.append({"category": cat, "name": name, "pass": bool(cond), "detail": str(detail)[:220]})
    print(("PASS " if cond else "FAIL ") + f"[{cat}] {name}" + ("" if cond else f"  -> {detail}"))


zero = lambda conn, sql: conn.execute(sql).fetchone()[0]

with psycopg.connect(dsn) as db:
    D = "Data integrity"
    orphans = {
        "attempts without a user": "SELECT count(*) FROM reios_attempts a LEFT JOIN reios_users u ON u.id=a.student_id WHERE u.id IS NULL",
        "attempts without an exam": "SELECT count(*) FROM reios_attempts a LEFT JOIN reios_exams e ON e.id=a.exam_id WHERE e.id IS NULL",
        "answers without an attempt": "SELECT count(*) FROM reios_mcq_answers m LEFT JOIN reios_attempts a ON a.id=m.attempt_id WHERE a.id IS NULL",
        "answers without a question item": "SELECT count(*) FROM reios_mcq_answers m LEFT JOIN reios_exam_items i ON i.id=m.item_id WHERE i.id IS NULL",
        "proctor events without an attempt": "SELECT count(*) FROM reios_proctor_events p LEFT JOIN reios_attempts a ON a.id=p.attempt_id WHERE a.id IS NULL",
        "exam items without an exam": "SELECT count(*) FROM reios_exam_items i LEFT JOIN reios_exams e ON e.id=i.exam_id WHERE e.id IS NULL",
        "set assignments without a team": "SELECT count(*) FROM reios_set_assignments s LEFT JOIN reios_users u ON u.id=s.student_id WHERE u.id IS NULL",
        "users pointing at a missing event": "SELECT count(*) FROM reios_users u LEFT JOIN reios_colleges c ON c.id=u.college_id WHERE u.college_id IS NOT NULL AND c.id IS NULL",
    }
    for name, sql in orphans.items():
        n = zero(db, sql); check(D, f"No {name}", n == 0, n)
    dupes = {
        "duplicate team codes within an event": "SELECT count(*) FROM (SELECT college_id, lower(roll_no) FROM reios_users WHERE roll_no IS NOT NULL GROUP BY 1,2 HAVING count(*)>1) x",
        "duplicate answers for the same question": "SELECT count(*) FROM (SELECT attempt_id,item_id FROM reios_mcq_answers GROUP BY 1,2 HAVING count(*)>1) x",
        "teams with two attempts at one exam": "SELECT count(*) FROM (SELECT exam_id,student_id FROM reios_attempts GROUP BY 1,2 HAVING count(*)>1) x",
    }
    for name, sql in dupes.items():
        n = zero(db, sql); check(D, f"No {name}", n == 0, n)

    n = zero(db, """SELECT count(*) FROM reios_attempts WHERE status<>'IN_PROGRESS' AND abs(total_score-(mcq_score+coding_score))>0.01""")
    check(D, "Every finished attempt: total = MCQ + coding score", n == 0, n)
    n = zero(db, """SELECT count(*) FROM reios_attempts a WHERE status<>'IN_PROGRESS' AND abs(a.mcq_score -
                 coalesce((SELECT sum(marks_awarded) FROM reios_mcq_answers m WHERE m.attempt_id=a.id),0))>0.01""")
    check(D, "Every finished attempt: MCQ score = sum of its answer marks", n == 0, n)
    n = zero(db, """SELECT count(*) FROM reios_mcq_answers m JOIN reios_exam_items i ON i.id=m.item_id
                 JOIN reios_mcq_questions q ON q.id=i.mcq_id WHERE m.selected::text<>'[]' AND m.is_correct IS DISTINCT FROM
                 (m.selected::jsonb = (SELECT coalesce(jsonb_agg(x ORDER BY x),'[]'::jsonb) FROM jsonb_array_elements(q.correct_options::jsonb) x))""")
    total = zero(db, "SELECT count(*) FROM reios_mcq_answers WHERE selected::text<>'[]'")
    check(D, f"All {total} saved answers are graded exactly per the answer key", n == 0, f"{n} mismatched")
    n = zero(db, """SELECT count(*) FROM reios_mcq_answers m JOIN reios_attempts a ON a.id=m.attempt_id
                 WHERE NOT (a.item_order::jsonb @> to_jsonb(m.item_id))""")
    check(D, "Every answer belongs to a question on that team's own paper", n == 0, n)
    n = zero(db, """SELECT count(*) FROM reios_mcq_answers m JOIN reios_exam_items i ON i.id=m.item_id JOIN reios_mcq_questions q ON q.id=i.mcq_id,
                 jsonb_array_elements(m.selected::jsonb) s WHERE (s::int) < 0 OR (s::int) >= jsonb_array_length(q.options::jsonb)""")
    check(D, "Every selected option exists on its question", n == 0, n)
    n = zero(db, "SELECT count(*) FROM reios_attempts WHERE (status='IN_PROGRESS') = (submitted_at IS NOT NULL)")
    check(D, "Submit time present exactly for finished attempts", n == 0, n)
    n = zero(db, "SELECT count(*) FROM reios_attempts WHERE deadline_at < started_at")
    check(D, "No attempt has a deadline before its start", n == 0, n)
    n = zero(db, "SELECT count(*) FROM reios_exams WHERE end_at <= start_at OR duration_minutes <= 0")
    check(D, "Every exam window and duration is valid", n == 0, n)
    n = zero(db, "SELECT count(*) FROM reios_exams WHERE control_state NOT IN ('scheduled','live','paused','ended')")
    check(D, "Exam control states are all valid", n == 0, n)

    S = "Database security"
    n = zero(db, "SELECT count(*) FROM reios_users WHERE hashed_password NOT LIKE '$2%'")
    check(S, "Every password is stored as a bcrypt hash", n == 0, f"{n} not bcrypt")
    n = zero(db, "SELECT count(*) FROM reios_users WHERE hashed_password = name OR hashed_password = roll_no")
    check(S, "No password stored in plain text", n == 0, n)
    n = zero(db, """SELECT count(*) FROM information_schema.tables t WHERE t.table_schema='public' AND NOT EXISTS
                 (SELECT 1 FROM information_schema.table_constraints c WHERE c.table_name=t.table_name AND c.constraint_type='PRIMARY KEY')""")
    check(S, "Every table has a primary key", n == 0, n)
    r = db.execute("SELECT rolsuper FROM pg_roles WHERE rolname='reios'").fetchone()[0]
    check(S, "The app connects as a non-superuser account", r is False, r)
    r = db.execute("SHOW listen_addresses").fetchone()[0]
    check(S, "Database only listens on this machine (127.0.0.1)", r == "127.0.0.1", r)

    H = "Database health"
    r = db.execute("SHOW synchronous_commit").fetchone()[0]
    check(H, "Every saved answer is flushed to disk before success (synchronous_commit)", r == "on", r)
    r = db.execute("SELECT checksum_failures FROM pg_stat_database WHERE datname='reios'").fetchone()[0]
    check(H, "No data-page checksum failures", not r, r)
    conns = db.execute("SELECT count(*), current_setting('max_connections')::int FROM pg_stat_activity").fetchone()
    check(H, "Connection headroom (in use vs limit)", conns[0] < conns[1] * 0.8, f"{conns[0]} of {conns[1]}")
    size = db.execute("SELECT pg_size_pretty(pg_database_size('reios'))").fetchone()[0]
    counts = dict(db.execute("""SELECT 'events',count(*) FROM reios_colleges UNION ALL SELECT 'users',count(*) FROM reios_users
        UNION ALL SELECT 'exams',count(*) FROM reios_exams UNION ALL SELECT 'attempts',count(*) FROM reios_attempts
        UNION ALL SELECT 'answers',count(*) FROM reios_mcq_answers UNION ALL SELECT 'questions',count(*) FROM reios_mcq_questions""").fetchall())
    check(H, f"Database size {size}", True, counts)

# Backup / restore drill: dump the live DB, restore into a scratch DB, compare every table's row count
R = "Backup & restore"
pg = r"C:\Program Files\PostgreSQL\18\bin"
dump = r"C:\reios-server\backups\qa-drill.dump"
e1 = dict(os.environ, PGPASSWORD=app_pw); e2 = dict(os.environ, PGPASSWORD=super_pw)
subprocess.run([f"{pg}\\pg_dump.exe", "-h", "127.0.0.1", "-p", "5433", "-U", "reios", "-Fc", "-f", dump, "reios"], env=e1, check=True)
subprocess.run([f"{pg}\\psql.exe", "-h", "127.0.0.1", "-p", "5433", "-U", "postgres", "-d", "postgres", "-q", "-c",
                "DROP DATABASE IF EXISTS reios_restore_drill", "-c", "CREATE DATABASE reios_restore_drill OWNER reios"], env=e2, check=True)
rr = subprocess.run([f"{pg}\\pg_restore.exe", "-h", "127.0.0.1", "-p", "5433", "-U", "reios", "-d", "reios_restore_drill",
                     "--no-owner", "--exit-on-error", dump], env=e1)
check(R, "A fresh backup restores without errors", rr.returncode == 0, rr.returncode)
q = "SELECT relname, n_live_tup FROM pg_stat_user_tables ORDER BY 1"
tables = [t for (t,) in psycopg.connect(dsn).execute("SELECT tablename FROM pg_tables WHERE schemaname='public'").fetchall()]
with psycopg.connect(dsn) as a, psycopg.connect(dsn.rsplit("/", 1)[0] + "/reios_restore_drill") as b:
    diff = [t for t in tables if a.execute(f'SELECT count(*) FROM "{t}"').fetchone()[0] != b.execute(f'SELECT count(*) FROM "{t}"').fetchone()[0]]
check(R, f"Restored copy matches the live database in all {len(tables)} tables", not diff, diff)
subprocess.run([f"{pg}\\psql.exe", "-h", "127.0.0.1", "-p", "5433", "-U", "postgres", "-d", "postgres", "-q", "-c",
                "DROP DATABASE IF EXISTS reios_restore_drill WITH (FORCE)"], env=e2)
Path(dump).unlink(missing_ok=True)

(RES / "db_integrity.json").write_text(json.dumps(results, indent=1))
print(f"\n{sum(r['pass'] for r in results)}/{len(results)} database checks passed")
