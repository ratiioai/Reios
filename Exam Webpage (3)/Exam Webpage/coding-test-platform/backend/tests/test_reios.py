"""
End-to-end tests for the Reios module: super admin -> college -> college admin -> students -> exam -> results.
Run from the backend folder:  python -m pytest tests/test_reios.py -q
"""
import os
import tempfile
from datetime import datetime, timedelta, timezone

_DB = os.path.join(tempfile.mkdtemp(), "reios_test.db")
# REIOS_TEST_DATABASE_URL runs the suite against another database, e.g. a throwaway PostgreSQL
os.environ["DATABASE_URL"] = os.environ.get("REIOS_TEST_DATABASE_URL") or f"sqlite:///{_DB}"
os.environ["SUPER_ADMIN_EMAIL"] = "root@reios.test"
os.environ["SUPER_ADMIN_PASSWORD"] = "RootPass123"
# Independent of the developer's backend/.env (load_dotenv never overrides variables already set)
os.environ["FIREBASE_PROJECT_ID"] = ""

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

SUM_CODE = "a, b = map(int, input().split())\nprint(a + b)\n"


def auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def setup(client):
    """Build a college with an admin, two students, an MCQ bank, a coding problem and a live exam."""
    r = client.post("/api/reios/auth/login", json={"identifier": "root@reios.test", "password": "RootPass123"})
    assert r.status_code == 200, r.text
    root = r.json()["access_token"]

    r = client.post("/api/reios/super/colleges", headers=auth(root),
                    json={"name": "Test Engineering College", "code": "tec", "city": "Hyderabad", "max_students": 10})
    assert r.status_code == 201, r.text
    college = r.json()
    assert college["code"] == "TEC"
    assert client.post("/api/reios/super/colleges", headers=auth(root),
                       json={"name": "Dup", "code": "TEC"}).status_code == 409

    r = client.post(f"/api/reios/super/colleges/{college['id']}/admins", headers=auth(root),
                    json={"name": "TPO Officer", "email": "tpo@tec.edu"})
    assert r.status_code == 201, r.text
    admin_tmp = r.json()["temporary_password"]

    r = client.post("/api/reios/auth/login", json={"identifier": "tpo@tec.edu", "password": admin_tmp})
    assert r.status_code == 200
    assert r.json()["user"]["must_change_password"] is True
    r = client.post("/api/reios/auth/change-password", headers=auth(r.json()["access_token"]),
                    json={"current_password": admin_tmp, "new_password": "TpoSecure99"})
    assert r.status_code == 200
    admin = r.json()["access_token"]

    # Students: one manually, others by CSV
    r = client.post("/api/reios/admin/students", headers=auth(admin),
                    json={"roll_no": "21cs001", "name": "Asha", "branch": "cse", "section": "a",
                          "batch_year": 2025, "password": "student1"})
    assert r.status_code == 201, r.text
    assert r.json()["roll_no"] == "21CS001" and r.json()["branch"] == "CSE"
    csv_data = ("roll_no,name,email,branch,section,batch_year,password\n"
                "21CS002,Ravi,ravi@tec.edu,CSE,A,2025,student2\n"
                "21EC001,Meena,,ECE,B,2025,\n"
                "21CS001,Duplicate,,CSE,A,2025,\n"
                ",Missing Roll,,CSE,A,2025,\n")
    r = client.post("/api/reios/admin/students/import", headers=auth(admin),
                    files={"file": ("students.csv", csv_data, "text/csv")})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["created"] == 2 and body["failed"] == 2
    assert {c["roll_no"] for c in body["credentials"]} == {"21CS002", "21EC001"}

    # MCQs by CSV and one by JSON
    mcq_csv = ("section,topic,difficulty,question,option_a,option_b,option_c,option_d,correct,marks,negative_marks\n"
               "Quantitative Aptitude,Percent,easy,What is 10% of 50?,5,10,15,20,A,1,0.25\n"
               "Logical Reasoning,Series,medium,Next: 2 4 8 ?,10,12,16,18,C,1,0.25\n"
               "Technical,OOP,easy,Which are OOP pillars?,Inheritance,Compilation,Polymorphism,Linking,\"A,C\",2,0\n"
               "Technical,Bad,easy,Broken row,only one,,,,A,1,0\n")
    r = client.post("/api/reios/admin/mcqs/import", headers=auth(admin),
                    files={"file": ("mcqs.csv", mcq_csv, "text/csv")})
    assert r.status_code == 200, r.text
    assert r.json()["created"] == 3 and r.json()["failed"] == 1

    r = client.post("/api/reios/admin/mcqs", headers=auth(admin), json={
        "section": "Verbal Ability", "question_text": "Synonym of 'rapid'", "options": ["slow", "fast"],
        "correct_options": [1]})
    assert r.status_code == 201
    mcqs = client.get("/api/reios/admin/mcqs", headers=auth(admin)).json()["items"]
    assert len(mcqs) == 4

    # Super admin adds a global coding problem; college admin can use but not edit it
    r = client.post("/api/reios/admin/problems", headers=auth(root), json={
        "title": "Sum of Two", "statement": "Read a and b, print a+b",
        "sample_tests": [{"input": "1 2", "output": "3"}],
        "hidden_tests": [{"input": "5 7", "output": "12"}, {"input": "-1 1", "output": "0"},
                         {"input": "100 200", "output": "300"}, {"input": "0 0", "output": "0"}],
        "starter_code": {"python": "# read input\n"}, "marks": 20})
    assert r.status_code == 201, r.text
    problem = r.json()
    assert problem["is_global"] is True
    assert client.delete(f"/api/reios/admin/problems/{problem['id']}", headers=auth(admin)).status_code == 403
    r = client.post(f"/api/reios/admin/problems/{problem['id']}/verify", headers=auth(admin),
                    json={"language": "python", "code": SUM_CODE})
    assert r.status_code == 200 and r.json()["passed"] == 5, r.text

    now = datetime.now(timezone.utc)
    exam_body = {
        "title": "Reios Mock 1", "instructions": "No cheating", "start_at": (now - timedelta(minutes=5)).isoformat(),
        "end_at": (now + timedelta(hours=2)).isoformat(), "duration_minutes": 60, "negative_marking": True,
        "branch_filter": "CSE", "max_violations": 3, "show_answers": True,
    }
    r = client.post("/api/reios/admin/exams", headers=auth(admin), json=exam_body)
    assert r.status_code == 201, r.text
    exam = r.json()
    assert client.post(f"/api/reios/admin/exams/{exam['id']}/publish", headers=auth(admin)).status_code == 400

    items = [{"item_type": "mcq", "question_id": q["id"]} for q in mcqs] + \
            [{"item_type": "coding", "question_id": problem["id"]}]
    r = client.put(f"/api/reios/admin/exams/{exam['id']}/items", headers=auth(admin), json={"items": items})
    assert r.status_code == 200, r.text
    assert r.json()["question_count"] == 5
    assert r.json()["max_score"] == 1 + 1 + 2 + 1 + 20
    assert client.post(f"/api/reios/admin/exams/{exam['id']}/publish", headers=auth(admin)).status_code == 200

    return {"root": root, "admin": admin, "college": college, "exam": exam, "problem": problem, "mcqs": mcqs}


def student_login(client, roll, password, new_password=None):
    r = client.post("/api/reios/auth/login", json={"identifier": roll, "password": password, "college_code": "tec"})
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    if new_password:
        r = client.post("/api/reios/auth/change-password", headers=auth(token),
                        json={"current_password": password, "new_password": new_password})
        assert r.status_code == 200, r.text
        token = r.json()["access_token"]
    return token


def test_isolation_between_colleges(client, setup):
    r = client.post("/api/reios/super/colleges", headers=auth(setup["root"]), json={"name": "Other", "code": "OTH"})
    other = r.json()
    r = client.post(f"/api/reios/super/colleges/{other['id']}/admins", headers=auth(setup["root"]),
                    json={"name": "Other TPO", "email": "tpo@oth.edu", "password": "OtherPass1"})
    other_admin = client.post("/api/reios/auth/login",
                              json={"identifier": "tpo@oth.edu", "password": "OtherPass1"}).json()["access_token"]
    # Other college cannot see TEC's students or exams
    assert client.get("/api/reios/admin/students", headers=auth(other_admin)).json()["total"] == 0
    assert client.get(f"/api/reios/admin/exams/{setup['exam']['id']}", headers=auth(other_admin)).status_code == 404
    # College admin cannot reach super admin endpoints, even with ?college_id=
    assert client.get("/api/reios/super/colleges", headers=auth(other_admin)).status_code == 403
    r = client.get(f"/api/reios/admin/students?college_id={setup['college']['id']}", headers=auth(other_admin))
    assert r.json()["total"] == 0
    # Super admin can view any college with ?college_id=
    r = client.get(f"/api/reios/admin/students?college_id={setup['college']['id']}", headers=auth(setup["root"]))
    assert r.json()["total"] == 3


def test_login_errors(client, setup):
    assert client.post("/api/reios/auth/login", json={"identifier": "21CS001", "password": "wrong",
                                                    "college_code": "TEC"}).status_code == 401
    assert client.post("/api/reios/auth/login", json={"identifier": "NOSUCHID", "password": "x"}).status_code == 401


def test_sign_in_with_id_only(client, setup):
    """No code needed; when two places reuse an ID the password picks the account."""
    root = setup["root"]
    ids = {}
    for code in ("IDA", "IDB"):
        org = client.post("/api/reios/super/colleges", headers=auth(root),
                          json={"name": f"Event {code}", "code": code, "org_type": "event"}).json()
        client.post(f"/api/reios/super/colleges/{org['id']}/admins", headers=auth(root),
                    json={"name": "Admin", "email": f"admin@{code.lower()}.com", "password": "AdminPass1"})
        ids[code] = client.post("/api/reios/auth/login", json={
            "identifier": f"admin@{code.lower()}.com", "password": "AdminPass1"}).json()["access_token"]
    client.post("/api/reios/admin/students", headers=auth(ids["IDA"]), json={"roll_no": "T01", "name": "Alpha", "password": "alpha-pass"})
    client.post("/api/reios/admin/students", headers=auth(ids["IDB"]), json={"roll_no": "T01", "name": "Beta", "password": "beta-pass"})
    client.post("/api/reios/admin/students", headers=auth(ids["IDA"]), json={"roll_no": "SOLO7", "name": "Solo", "password": "solo-pass"})

    def login(i, p, code=None):
        body = {"identifier": i, "password": p, **({"college_code": code} if code else {})}
        return client.post("/api/reios/auth/login", json=body)

    assert login("solo7", "solo-pass").json()["user"]["college"]["code"] == "IDA"
    assert login("T01", "alpha-pass").json()["user"]["name"] == "Alpha"
    assert login("T01", "beta-pass").json()["user"]["name"] == "Beta"
    assert login("T01", "nope").status_code == 401
    # Same ID and same password in two events: only then is the code needed
    client.post("/api/reios/admin/students", headers=auth(ids["IDA"]), json={"roll_no": "T02", "name": "A2", "password": "same-pass"})
    client.post("/api/reios/admin/students", headers=auth(ids["IDB"]), json={"roll_no": "T02", "name": "B2", "password": "same-pass"})
    assert login("T02", "same-pass").status_code == 409
    assert login("T02", "same-pass", "IDB").json()["user"]["name"] == "B2"

    for c in client.get("/api/reios/super/colleges", headers=auth(root)).json():
        if c["code"] in ("IDA", "IDB"):
            client.delete(f"/api/reios/super/colleges/{c['id']}?confirm={c['code']}", headers=auth(root))


def test_full_exam_flow(client, setup):
    admin, exam_id = setup["admin"], setup["exam"]["id"]
    token = student_login(client, "21cs001", "student1")

    # Must change password before starting
    assert client.post(f"/api/reios/student/exams/{exam_id}/start", headers=auth(token)).status_code == 403
    token = student_login(client, "21cs001", "student1", new_password="AshaPass11")

    dash = client.get("/api/reios/student/dashboard", headers=auth(token)).json()
    assert [e["state"] for e in dash["exams"]] == ["live"]

    r = client.post(f"/api/reios/student/exams/{exam_id}/start", headers=auth(token))
    assert r.status_code == 200, r.text
    paper = r.json()
    session = paper["session"]
    attempt_id = paper["attempt_id"]
    hdr = {**auth(token), "X-Exam-Session": session}
    assert len(paper["items"]) == 5
    # Paper must not leak answers or hidden tests
    raw = r.text
    assert "correct_options" not in raw and "hidden_tests" not in raw and "12" not in [
        t["output"] for i in paper["items"] if i["type"] == "coding" for t in i["sample_tests"]]

    mcq_items = [i for i in paper["items"] if i["type"] == "mcq"]
    by_text = {i["question_text"]: i for i in mcq_items}

    def option_id(item, text):
        return next(o["id"] for o in item["options"] if o["text"] == text)

    # Correct answers
    q = by_text["What is 10% of 50?"]
    assert client.put(f"/api/reios/student/attempts/{attempt_id}/mcq/{q['item_id']}", headers=hdr,
                      json={"selected": [option_id(q, "5")]}).status_code == 200
    q = by_text["Which are OOP pillars?"]
    assert client.put(f"/api/reios/student/attempts/{attempt_id}/mcq/{q['item_id']}", headers=hdr,
                      json={"selected": [option_id(q, "Inheritance"), option_id(q, "Polymorphism")]}).status_code == 200
    # Wrong answer (negative marking 0.25)
    q = by_text["Next: 2 4 8 ?"]
    assert client.put(f"/api/reios/student/attempts/{attempt_id}/mcq/{q['item_id']}", headers=hdr,
                      json={"selected": [option_id(q, "10")], "marked_for_review": True}).status_code == 200
    # Multiple options on a single-answer question is rejected
    q = by_text["Synonym of 'rapid'"]
    assert client.put(f"/api/reios/student/attempts/{attempt_id}/mcq/{q['item_id']}", headers=hdr,
                      json={"selected": [0, 1]}).status_code == 400

    # Missing / wrong session header is rejected
    assert client.put(f"/api/reios/student/attempts/{attempt_id}/mcq/{q['item_id']}", headers=auth(token),
                      json={"selected": [0]}).status_code == 409

    coding = next(i for i in paper["items"] if i["type"] == "coding")
    url = f"/api/reios/student/attempts/{attempt_id}/code/{coding['item_id']}"
    r = client.post(f"{url}/run", headers=hdr, json={"language": "python", "code": SUM_CODE})
    assert r.status_code == 200 and r.json()["passed"] == 1, r.text
    assert client.post(f"{url}/run", headers=hdr, json={"language": "python", "code": SUM_CODE}).status_code == 429
    import app.reios.routes_student as rs
    rs._last_run.clear()
    r = client.post(f"{url}/run", headers=hdr, json={"language": "python", "code": SUM_CODE, "custom_input": "40 2"})
    assert r.json()["stdout"].strip() == "42"
    rs._last_run.clear()
    # Wrong solution (a*b) only passes the "0 0" hidden test: 1 of 4
    r = client.post(f"{url}/submit", headers=hdr,
                    json={"language": "python", "code": "a, b = map(int, input().split())\nprint(a * b)\n"})
    assert r.status_code == 200, r.text
    assert r.json()["passed_tests"] == 1
    rs._last_run.clear()
    r = client.post(f"{url}/submit", headers=hdr, json={"language": "python", "code": SUM_CODE})
    assert r.json() == {"passed_tests": 4, "total_tests": 4, "all_passed": True}

    # Violations: blur + tab switch together count once (debounce)
    r = client.post(f"/api/reios/student/attempts/{attempt_id}/violation", headers=hdr, json={"type": "tab_switch"})
    assert r.json()["violations"] == 1
    r = client.post(f"/api/reios/student/attempts/{attempt_id}/violation", headers=hdr, json={"type": "window_blur"})
    assert r.json()["violations"] == 1 and r.json()["counted"] is False
    r = client.post(f"/api/reios/student/attempts/{attempt_id}/violation", headers=hdr, json={"type": "copy_attempt"})
    assert r.json()["counted"] is False

    # Live monitor shows the student
    live = client.get(f"/api/reios/admin/exams/{exam_id}/live", headers=auth(admin)).json()
    assert live["attempts"][0]["online"] is True and live["attempts"][0]["violations"] == 1

    # Resuming from another tab takes over the session
    r = client.post(f"/api/reios/student/exams/{exam_id}/start", headers=auth(token))
    new_session = r.json()["session"]
    assert r.json()["items"][0]["item_id"] == paper["items"][0]["item_id"]  # same order on resume
    assert client.post(f"/api/reios/student/attempts/{attempt_id}/submit", headers=hdr).status_code == 409
    hdr = {**auth(token), "X-Exam-Session": new_session}

    r = client.post(f"/api/reios/student/attempts/{attempt_id}/submit", headers=hdr)
    assert r.status_code == 200 and r.json()["status"] == "submitted"
    assert client.post(f"/api/reios/student/exams/{exam_id}/start", headers=auth(token)).status_code == 409

    result = client.get(f"/api/reios/student/attempts/{attempt_id}/result", headers=auth(token)).json()
    # 1 (percent) + 2 (OOP) - 0.25 (series) + 0 (verbal unanswered) + 20 (coding)
    assert result["total_score"] == 22.75, result
    assert result["max_score"] == 25 and result["rank"] == 1
    assert {s["section"]: s["score"] for s in result["sections"]}["Coding"] == 20
    assert len(result["review"]) == 5

    detail = client.get(f"/api/reios/admin/attempts/{attempt_id}", headers=auth(admin)).json()
    assert detail["total_score"] == 22.75
    assert any(e["type"] == "session_resumed" for e in detail["events"])


def test_auto_submit_on_violations_and_similarity(client, setup):
    admin, exam_id = setup["admin"], setup["exam"]["id"]
    token = student_login(client, "21CS002", "student2", new_password="RaviPass22")
    paper = client.post(f"/api/reios/student/exams/{exam_id}/start", headers=auth(token)).json()
    hdr = {**auth(token), "X-Exam-Session": paper["session"]}
    attempt_id = paper["attempt_id"]
    coding = next(i for i in paper["items"] if i["type"] == "coding")
    # Same code as Asha, only comments/whitespace changed -> similarity flag
    assert client.put(f"/api/reios/student/attempts/{attempt_id}/code/{coding['item_id']}", headers=hdr,
                      json={"language": "python", "code": "# my solution\n" + SUM_CODE + "\n\n"}).status_code == 200

    import app.reios.routes_student as rs
    for n in range(3):
        rs.VIOLATION_DEBOUNCE_SECONDS = 0
        r = client.post(f"/api/reios/student/attempts/{attempt_id}/violation", headers=hdr,
                        json={"type": "fullscreen_exit"})
    rs.VIOLATION_DEBOUNCE_SECONDS = 2
    assert r.json()["auto_submitted"] is True and r.json()["violations"] == 3
    assert client.post(f"/api/reios/student/attempts/{attempt_id}/submit", headers=hdr).status_code == 409

    # Saved-but-never-submitted code is graded on auto-submit
    result = client.get(f"/api/reios/student/attempts/{attempt_id}/result", headers=auth(token)).json()
    assert result["status"] == "auto_submitted" and result["submit_reason"] == "max_violations"
    assert result["total_score"] == 20

    sim = client.get(f"/api/reios/admin/exams/{exam_id}/similarity", headers=auth(admin)).json()
    assert len(sim["pairs"]) == 1 and sim["pairs"][0]["similarity"] == 100.0

    results = client.get(f"/api/reios/admin/exams/{exam_id}/results", headers=auth(admin)).json()
    assert results["summary"]["completed"] == 2
    assert results["summary"]["eligible"] == 2  # ECE student is filtered out by branch
    assert [r["roll_no"] for r in results["results"]] == ["21CS001", "21CS002"]

    r = client.get(f"/api/reios/admin/exams/{exam_id}/export", headers=auth(admin))
    assert r.status_code == 200 and "21CS001" in r.text and "Coding" in r.text.splitlines()[0]

    # ECE student can't see or start the CSE-only exam
    ece = client.post("/api/reios/auth/login", json={"identifier": "21EC001", "password": "x", "college_code": "TEC"})
    assert ece.status_code == 401

    # Admin resets Ravi's attempt so he can retake
    assert client.delete(f"/api/reios/admin/attempts/{attempt_id}", headers=auth(admin)).status_code == 200
    assert client.post(f"/api/reios/student/exams/{exam_id}/start", headers=auth(token)).status_code == 200
    # Questions are locked once attempts exist
    r = client.put(f"/api/reios/admin/exams/{exam_id}/items", headers=auth(admin), json={"items": []})
    assert r.status_code == 409


def test_time_expiry_auto_submits(client, setup):
    from app.database import SessionLocal
    from app.reios.models import Attempt

    admin = setup["admin"]
    r = client.post("/api/reios/admin/students", headers=auth(admin),
                    json={"roll_no": "21CS003", "name": "Late", "branch": "CSE", "password": "student3"})
    assert r.status_code == 201
    token = student_login(client, "21CS003", "student3", new_password="LatePass33")
    paper = client.post(f"/api/reios/student/exams/{setup['exam']['id']}/start", headers=auth(token)).json()
    db = SessionLocal()
    attempt = db.get(Attempt, paper["attempt_id"])
    attempt.deadline_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.commit()
    db.close()
    hdr = {**auth(token), "X-Exam-Session": paper["session"]}
    r = client.post(f"/api/reios/student/attempts/{paper['attempt_id']}/heartbeat", headers=hdr)
    assert r.json()["status"] == "auto_submitted"


def test_deactivated_college_blocks_login(client, setup):
    cid = setup["college"]["id"]
    assert client.patch(f"/api/reios/super/colleges/{cid}", headers=auth(setup["root"]),
                        json={"is_active": False}).status_code == 200
    r = client.post("/api/reios/auth/login", json={"identifier": "21CS001", "password": "AshaPass11", "college_code": "TEC"})
    assert r.status_code == 403
    assert client.get("/api/reios/admin/students", headers=auth(setup["admin"])).status_code == 403
    client.patch(f"/api/reios/super/colleges/{cid}", headers=auth(setup["root"]), json={"is_active": True})
    stats = client.get("/api/reios/super/stats", headers=auth(setup["root"])).json()
    assert stats["colleges"] == 2 and stats["students"] == 4


def _word_doc(lines=None, table=None) -> bytes:
    import io
    from docx import Document
    d = Document()
    for t in lines or []:
        d.add_paragraph(t)
    if table:
        t = d.add_table(rows=0, cols=len(table[0]))
        for row in table:
            for c, v in zip(t.add_row().cells, row):
                c.text = v
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


def test_sets_exam_types_preview_and_leaderboard(client, setup):
    root = setup["root"]
    college = client.post("/api/reios/super/colleges", headers=auth(root),
                          json={"name": "Sets College", "code": "SETC"}).json()
    client.post(f"/api/reios/super/colleges/{college['id']}/admins", headers=auth(root),
                json={"name": "Sets TPO", "email": "tpo@setc.edu", "password": "SetsPass1"})
    admin = client.post("/api/reios/auth/login",
                        json={"identifier": "tpo@setc.edu", "password": "SetsPass1"}).json()["access_token"]
    admin = client.post("/api/reios/auth/change-password", headers=auth(admin),
                        json={"current_password": "SetsPass1", "new_password": "SetsPass2"}).json()["access_token"]
    docx = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

    # Students from a Word table using the headers colleges actually use
    table = [["Roll Number", "Student Name", "Department", "Password"]] + \
            [[f"S00{i}", f"Student {i}", "CSE", f"start{i}pass"] for i in range(1, 6)]
    r = client.post("/api/reios/admin/students/import", headers=auth(admin),
                    files={"file": ("students.docx", _word_doc(table=table), docx)})
    assert r.status_code == 200 and r.json()["created"] == 5, r.text

    now = datetime.now(timezone.utc)
    r = client.post("/api/reios/admin/exams", headers=auth(admin), json={
        "title": "GK Sets", "exam_type": "mcq", "start_at": (now - timedelta(minutes=1)).isoformat(),
        "end_at": (now + timedelta(hours=1)).isoformat(), "duration_minutes": 30, "show_answers": True})
    assert r.status_code == 201, r.text
    exam_id = r.json()["id"]
    assert r.json()["exam_type"] == "mcq"

    # An MCQ-only exam refuses coding questions
    r = client.put(f"/api/reios/admin/exams/{exam_id}/items", headers=auth(admin),
                   json={"items": [{"item_type": "coding", "question_id": setup["problem"]["id"]}]})
    assert r.status_code == 400 and "MCQ-only" in r.text

    # Upload two sets (Word and plain text), reviewed through /questions/parse first
    keep = {"section", "question_text", "options", "correct_options", "explanation", "marks", "negative_marks"}

    def upload_set(name, filename, data, mime):
        r = client.post("/api/reios/admin/questions/parse", headers=auth(admin),
                        files={"file": (filename, data, mime)}, data={"default_section": "General Knowledge"})
        assert r.status_code == 200, r.text
        parsed = r.json()
        assert parsed["ready"] == len(parsed["questions"]) == 2, parsed
        qs = [{k: v for k, v in q.items() if k in keep} for q in parsed["questions"]]
        r = client.post(f"/api/reios/admin/exams/{exam_id}/sets", headers=auth(admin),
                        json={"name": name, "source_filename": filename, "questions": qs})
        assert r.status_code == 201, r.text
        return r.json()["sets"]

    upload_set("Set A", "a.docx", _word_doc(["1. Capital of India?", "A) Delhi", "B) Mumbai", "Answer: A",
                                             "2. Largest ocean?", "A) Indian", "B) Pacific", "Answer: B"]), docx)
    sets = upload_set("Set B", "b.txt", "1. National animal?\nA) Lion\nB) Tiger\nAns: B\n"
                                        "2. 2 + 2 =\nA) 4\nB) 5\nAns: A\n", "text/plain")
    set_a, set_b = sets[0]["id"], sets[1]["id"]
    dup = {"name": "set a", "questions": [{"section": "X", "question_text": "q", "options": ["a", "b"],
                                           "correct_options": [0]}]}
    assert client.post(f"/api/reios/admin/exams/{exam_id}/sets", headers=auth(admin), json=dup).status_code == 409

    # Set questions stay out of the browsable bank
    assert client.get("/api/reios/admin/mcqs?q=Capital", headers=auth(admin)).json()["total"] == 0

    # One common question every student gets; editing the common list keeps the sets
    common = client.post("/api/reios/admin/mcqs", headers=auth(admin), json={
        "section": "General Knowledge", "question_text": "Common: sun rises in the?",
        "options": ["East", "West"], "correct_options": [0]}).json()
    r = client.put(f"/api/reios/admin/exams/{exam_id}/items", headers=auth(admin),
                   json={"items": [{"item_type": "mcq", "question_id": common["id"]}]})
    assert r.status_code == 200 and len(r.json()["items"]) == 1
    assert r.json()["set_count"] == 2 and r.json()["question_count"] == 3

    # Sets were rotated automatically on upload: in roll order, student i gets set i mod N (A, B, A, B, A)
    assign_url = f"/api/reios/admin/exams/{exam_id}/set-assignments"

    def pattern():
        r = client.get(assign_url, headers=auth(admin)).json()
        by = {s["roll_no"]: s["set_id"] for s in r["students"]}
        return [by[f"S00{i}"] for i in range(1, 6)], r

    order, r = pattern()
    assert r["auto_assign"] is True and r["unassigned"] == 0
    assert order == [set_a, set_b, set_a, set_b, set_a]

    # A third set rotates in (A, B, C, A, B) and out again, without touching anything by hand
    r = client.post(f"/api/reios/admin/exams/{exam_id}/sets", headers=auth(admin), json={
        "name": "Set C", "questions": [{"section": "GK", "question_text": "Temp?", "options": ["x", "y"],
                                        "correct_options": [0]}]})
    set_c = r.json()["sets"][2]["id"]
    assert pattern()[0] == [set_a, set_b, set_c, set_a, set_b]
    client.delete(f"/api/reios/admin/exams/{exam_id}/sets/{set_c}", headers=auth(admin))
    assert pattern()[0] == [set_a, set_b, set_a, set_b, set_a]

    # With automatic assignment off, a new set changes nothing until it's switched back on
    client.put(f"/api/reios/admin/exams/{exam_id}/set-options", headers=auth(admin), json={"auto_assign": False})
    r = client.post(f"/api/reios/admin/exams/{exam_id}/sets", headers=auth(admin), json={
        "name": "Set C", "questions": [{"section": "GK", "question_text": "Temp?", "options": ["x", "y"],
                                        "correct_options": [0]}]})
    set_c = r.json()["sets"][2]["id"]
    assert pattern()[0] == [set_a, set_b, set_a, set_b, set_a]
    r = client.put(f"/api/reios/admin/exams/{exam_id}/set-options", headers=auth(admin), json={"auto_assign": True})
    assert r.json()["auto_assign"] is True and pattern()[0] == [set_a, set_b, set_c, set_a, set_b]
    client.delete(f"/api/reios/admin/exams/{exam_id}/sets/{set_c}", headers=auth(admin))
    by_roll = {s["roll_no"]: s for s in client.get(assign_url, headers=auth(admin)).json()["students"]}
    assert [by_roll[f"S00{i}"]["set_id"] for i in range(1, 6)] == [set_a, set_b, set_a, set_b, set_a]
    counts = {s["id"]: s["assigned"] for s in client.get(f"/api/reios/admin/exams/{exam_id}/sets",
                                                         headers=auth(admin)).json()["sets"]}
    assert counts == {set_a: 3, set_b: 2}

    # Override from a sheet: roll number + set column (S002 is already on Set B; S999 doesn't exist)
    sheet = "roll_no,set\nS001,Set B\nS002,2\nS999,1\n"
    r = client.post(f"/api/reios/admin/exams/{exam_id}/set-assignments/import", headers=auth(admin),
                    files={"file": ("sets.csv", sheet, "text/csv")})
    assert r.status_code == 200 and r.json()["changed"] == 1 and len(r.json()["errors"]) == 1, r.text
    # A hand-made change switches automatic rotation off so the next upload won't undo it
    assert r.json()["auto_assign"] is False

    # Admin preview shows the chosen set with answers, without starting an attempt
    r = client.get(f"/api/reios/admin/exams/{exam_id}/preview?set_id={set_b}", headers=auth(admin))
    assert r.status_code == 200
    texts = [i["question_text"] for i in r.json()["items"]]
    assert "National animal?" in texts and "Capital of India?" not in texts and len(texts) == 3
    assert all("correct_options" in i for i in r.json()["items"])

    assert client.post(f"/api/reios/admin/exams/{exam_id}/publish", headers=auth(admin)).status_code == 200

    # S001 was moved to Set B: their paper is the common question plus Set B only
    t1 = client.post("/api/reios/auth/login", json={"identifier": "S001", "password": "start1pass",
                                                    "college_code": "SETC"}).json()["access_token"]
    t1 = client.post("/api/reios/auth/change-password", headers=auth(t1),
                     json={"current_password": "start1pass", "new_password": "newpass001"}).json()["access_token"]
    paper = client.post(f"/api/reios/student/exams/{exam_id}/start", headers=auth(t1)).json()
    texts = {i["question_text"]: i for i in paper["items"]}
    assert set(texts) == {"Common: sun rises in the?", "National animal?", "2 + 2 ="}
    hdr = {**auth(t1), "X-Exam-Session": paper["session"]}
    aid = paper["attempt_id"]

    # Answering a question from another set is refused
    set_a_items = client.get(f"/api/reios/admin/exams/{exam_id}/preview?set_id={set_a}",
                             headers=auth(admin)).json()["items"]
    other = next(i for i in set_a_items if i["set_id"] == set_a)
    assert client.put(f"/api/reios/student/attempts/{aid}/mcq/{other['item_id']}", headers=hdr,
                      json={"selected": [0]}).status_code == 404

    correct = {"Common: sun rises in the?": "East", "National animal?": "Tiger", "2 + 2 =": "4"}
    for text, item in texts.items():
        opt = next(o["id"] for o in item["options"] if o["text"] == correct[text])
        assert client.put(f"/api/reios/student/attempts/{aid}/mcq/{item['item_id']}", headers=hdr,
                          json={"selected": [opt]}).status_code == 200
    assert client.post(f"/api/reios/student/attempts/{aid}/submit", headers=hdr).status_code == 200

    # S003 (Set A) submits blank
    t3 = client.post("/api/reios/auth/login", json={"identifier": "S003", "password": "start3pass",
                                                    "college_code": "SETC"}).json()["access_token"]
    t3 = client.post("/api/reios/auth/change-password", headers=auth(t3),
                     json={"current_password": "start3pass", "new_password": "newpass003"}).json()["access_token"]
    p3 = client.post(f"/api/reios/student/exams/{exam_id}/start", headers=auth(t3)).json()
    assert {i["question_text"] for i in p3["items"]} >= {"Capital of India?", "Largest ocean?"}
    client.post(f"/api/reios/student/attempts/{p3['attempt_id']}/submit",
                headers={**auth(t3), "X-Exam-Session": p3["session"]})

    # Sets are locked once students have started
    assert client.delete(f"/api/reios/admin/exams/{exam_id}/sets/{set_a}", headers=auth(admin)).status_code == 409

    # Leaderboards
    rows = client.get(f"/api/reios/admin/leaderboard?exam_id={exam_id}", headers=auth(admin)).json()["rows"]
    assert [x["roll_no"] for x in rows] == ["S001", "S003"] and rows[0]["percentage"] == 100.0
    assert rows[0]["set_name"] == "Set B"
    r = client.get("/api/reios/admin/leaderboard", headers=auth(admin)).json()
    assert r["mode"] == "overall" and r["rows"][0]["roll_no"] == "S001"

    assert client.get(f"/api/reios/student/exams/{exam_id}/leaderboard", headers=auth(t1)).status_code == 404
    exam = client.get(f"/api/reios/admin/exams/{exam_id}", headers=auth(admin)).json()
    upd = {k: exam[k] for k in ("title", "start_at", "end_at", "duration_minutes", "exam_type", "show_answers")}
    r = client.put(f"/api/reios/admin/exams/{exam_id}", headers=auth(admin), json={**upd, "show_leaderboard": True})
    assert r.status_code == 200, r.text
    r = client.get(f"/api/reios/student/exams/{exam_id}/leaderboard", headers=auth(t3))
    assert r.status_code == 200 and r.json()["me"]["rank"] == 2 and r.json()["top"][0]["name"] == "Student 1"

    # Switching to coding-only would strand the MCQs
    assert client.put(f"/api/reios/admin/exams/{exam_id}", headers=auth(admin),
                      json={**upd, "exam_type": "coding"}).status_code == 400

    # Duplicating copies the sets and their questions
    copy = client.post(f"/api/reios/admin/exams/{exam_id}/duplicate", headers=auth(admin)).json()
    copy_sets = client.get(f"/api/reios/admin/exams/{copy['id']}/sets", headers=auth(admin)).json()["sets"]
    assert [(s["name"], s["question_count"]) for s in copy_sets] == [("Set A", 2), ("Set B", 2)]
    assert {s["id"] for s in copy_sets}.isdisjoint({set_a, set_b})

    # Deleting the copy cleans up after itself without touching the original's shared set questions
    assert client.delete(f"/api/reios/admin/exams/{copy['id']}", headers=auth(admin)).status_code == 200
    assert len(client.get(f"/api/reios/admin/exams/{exam_id}/sets/{set_a}", headers=auth(admin)).json()["questions"]) == 2

    # Super admin deletes the finished college: everything it owned goes, global questions stay
    cid = college["id"]
    global_before = client.get("/api/reios/admin/problems?source=global", headers=auth(root)).json()
    assert client.delete(f"/api/reios/super/colleges/{cid}?confirm=WRONG", headers=auth(root)).status_code == 400
    assert client.delete(f"/api/reios/super/colleges/{cid}?confirm=setc", headers=auth(admin)).status_code == 403
    r = client.delete(f"/api/reios/super/colleges/{cid}?confirm=setc", headers=auth(root))
    assert r.status_code == 200 and r.json()["students"] == 5 and r.json()["attempts"] == 2, r.text
    assert all(c["id"] != cid for c in client.get("/api/reios/super/colleges", headers=auth(root)).json())
    assert client.get("/api/reios/admin/exams", headers=auth(admin)).status_code == 401
    assert client.post("/api/reios/auth/login", json={"identifier": "S001", "password": "newpass001",
                                                      "college_code": "SETC"}).status_code in (400, 401, 404)
    assert client.get("/api/reios/admin/problems?source=global", headers=auth(root)).json() == global_before


def test_super_admin_firebase_sign_in(client, setup, monkeypatch):
    import datetime as dt
    import time as _time
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID
    from jose import jwt as jose_jwt
    from app.config import settings
    from app.database import SessionLocal
    from app.reios import firebase_auth
    from app.reios.security import ensure_super_admin

    # Stand in for Google's signing key and certificate
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "securetoken.test")])
    now = dt.datetime.now(dt.timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
            .serial_number(1).not_valid_before(now - dt.timedelta(days=1)).not_valid_after(now + dt.timedelta(days=1))
            .sign(key, hashes.SHA256()))
    pem_cert = cert.public_bytes(serialization.Encoding.PEM).decode()
    pem_key = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                serialization.NoEncryption()).decode()
    monkeypatch.setattr(settings, "FIREBASE_PROJECT_ID", "reios-test")
    monkeypatch.setitem(firebase_auth._cache, "certs", {"k1": pem_cert})
    monkeypatch.setitem(firebase_auth._cache, "expires", _time.time() + 3600)
    monkeypatch.setenv("SUPER_ADMIN_EMAIL", "Boss@Uni.test, second@uni.test")
    db = SessionLocal()
    ensure_super_admin(db)
    db.close()

    def token(email="boss@uni.test", verified=True, aud="reios-test", sub="uid-boss", kid="k1"):
        t = int(_time.time())
        claims = {"iss": f"https://securetoken.google.com/{aud}", "aud": aud, "sub": sub, "auth_time": t,
                  "iat": t, "exp": t + 3600, "email": email, "email_verified": verified}
        return jose_jwt.encode(claims, pem_key, algorithm="RS256", headers={"kid": kid})

    def fb(tok):
        return client.post("/api/reios/auth/firebase", json={"id_token": tok})

    assert client.get("/api/reios/auth/config").json() == {"google_signin": True}

    r = fb(token())
    assert r.status_code == 200 and r.json()["user"]["role"] == "super_admin", r.text
    assert client.get("/api/reios/super/colleges", headers=auth(r.json()["access_token"])).status_code == 200

    assert fb(token(verified=False)).status_code == 403           # unverified email could be anyone's
    assert fb(token(aud="someone-elses-project")).status_code == 401
    assert fb(token(kid="unknown")).status_code == 401
    assert fb(token(email="student@uni.test")).status_code == 403  # not a super admin
    assert fb(token(sub="uid-impostor")).status_code == 403        # same email, different Firebase account
    assert fb(token(email="second@uni.test", sub="uid-2")).status_code == 200

    # Password sign-in is off for super admins while Firebase is on; college admins are unaffected
    r = client.post("/api/reios/auth/login", json={"identifier": "root@reios.test", "password": "RootPass123"})
    assert r.status_code == 401 and r.json()["detail"] == "Invalid credentials"  # same as a wrong password
    r = client.post("/api/reios/auth/login", json={"identifier": "tpo@tec.edu", "password": "TpoSecure99"})
    assert "Firebase" not in r.text


def test_organization_plan_limits(client, setup):
    from datetime import datetime, timedelta, timezone
    root = setup["root"]
    org = client.post("/api/reios/super/colleges", headers=auth(root),
                      json={"name": "Acme Hiring", "code": "ACME", "max_exams": 1}).json()
    assert org["max_exams"] == 1 and org["expired"] is False
    client.post(f"/api/reios/super/colleges/{org['id']}/admins", headers=auth(root),
                json={"name": "Acme HR", "email": "hr@acme.com", "password": "AcmePass1"})
    r = client.post("/api/reios/auth/login", json={"identifier": "hr@acme.com", "password": "AcmePass1"})
    assert r.status_code == 200, r.text
    adm = r.json()["access_token"]
    now = datetime.now(timezone.utc)
    body = {"title": "Round 1", "start_at": now.isoformat(), "end_at": (now + timedelta(hours=1)).isoformat()}
    first = client.post("/api/reios/admin/exams", headers=auth(adm), json=body)
    assert first.status_code == 201
    r = client.post("/api/reios/admin/exams", headers=auth(adm), json=body)
    assert r.status_code == 403 and "plan includes 1" in r.text
    assert client.post(f"/api/reios/admin/exams/{first.json()['id']}/duplicate", headers=auth(adm)).status_code == 403
    assert client.get("/api/reios/admin/stats", headers=auth(adm)).json()["college"]["max_exams"] == 1

    # Access end date in the past: existing sessions and new sign-ins are both refused
    r = client.patch(f"/api/reios/super/colleges/{org['id']}", headers=auth(root),
                     json={"access_until": (now - timedelta(minutes=1)).isoformat()})
    assert r.json()["expired"] is True
    r = client.get("/api/reios/admin/exams", headers=auth(adm))
    assert r.status_code == 403 and "access ended" in r.text
    assert client.post("/api/reios/auth/login", json={"identifier": "hr@acme.com", "password": "AcmePass1"}).status_code == 403
    # Renewing restores access; super admin is never locked out
    client.patch(f"/api/reios/super/colleges/{org['id']}", headers=auth(root),
                 json={"access_until": (now + timedelta(days=30)).isoformat()})
    assert client.get("/api/reios/admin/exams", headers=auth(adm)).status_code == 200


def test_event_add_ons(client, setup, monkeypatch):
    import base64
    from datetime import datetime, timedelta, timezone
    from app.config import settings
    from app.reios import features as feat
    root = setup["root"]
    png = "data:image/png;base64," + base64.b64encode(bytes.fromhex(
        "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
        "1f15c4890000000d49444154789c6360f8cfc0f01f0005fe02fea735819b0000000049454e44ae426082")).decode()

    # A college can't be given add-ons; an event can
    col = client.post("/api/reios/super/colleges", headers=auth(root),
                      json={"name": "Plain College", "code": "PLAIN", "features": ["branding"]}).json()
    assert col["org_type"] == "college" and col["features"] == []
    assert client.post("/api/reios/super/colleges", headers=auth(root), json={
        "name": "Bad", "code": "BADEV", "org_type": "event", "features": ["teleport"]}).status_code == 400
    ev = client.post("/api/reios/super/colleges", headers=auth(root), json={
        "name": "Hack Fest", "code": "HFEST", "org_type": "event", "logo": png, "brand_color": "#0f766e",
        "features": ["branding", "email_results"]}).json()
    assert ev["features"] == ["branding", "email_results"]
    # Event details are kept for events only, and an event can't end before it starts
    r = client.patch(f"/api/reios/super/colleges/{ev['id']}", headers=auth(root), json={
        "organizer": " Acme Corp ", "event_starts_at": "2026-12-10T00:00:00+00:00", "access_until": "2026-12-12T23:59:59+00:00"})
    assert r.status_code == 200 and r.json()["organizer"] == "Acme Corp" and r.json()["event_starts_at"].startswith("2026-12-10")
    assert client.patch(f"/api/reios/super/colleges/{ev['id']}", headers=auth(root),
                        json={"access_until": "2026-12-01T00:00:00+00:00"}).status_code == 400
    client.patch(f"/api/reios/super/colleges/{ev['id']}", headers=auth(root), json={"access_until": None})
    st = client.get(f"/api/reios/admin/stats?college_id={ev['id']}", headers=auth(root)).json()["college"]
    assert st["org_type"] == "event" and st["organizer"] == "Acme Corp"

    assert client.get("/api/reios/auth/branding?code=hfest").json()["color"] == "#0f766e"
    assert client.get("/api/reios/auth/branding?code=PLAIN").json() is None

    client.post(f"/api/reios/super/colleges/{ev['id']}/admins", headers=auth(root),
                json={"name": "Fest HR", "email": "hr@hackfest.com", "password": "FestPass1"})
    adm = client.post("/api/reios/auth/login", json={"identifier": "hr@hackfest.com", "password": "FestPass1"}).json()["access_token"]
    client.post("/api/reios/admin/students", headers=auth(adm), json={
        "roll_no": "HF1", "name": "Priya Winner", "email": "priya@mail.com", "password": "student1"})
    client.post("/api/reios/admin/students", headers=auth(adm), json={"roll_no": "HF2", "name": "No Email", "password": "student2"})
    q = client.post("/api/reios/admin/mcqs", headers=auth(adm), json={
        "section": "GK", "question_text": "2+2?", "options": ["4", "5"], "correct_options": [0]}).json()
    now = datetime.now(timezone.utc)
    exam = client.post("/api/reios/admin/exams", headers=auth(adm), json={
        "title": "Fest Quiz", "exam_type": "mcq", "start_at": (now - timedelta(minutes=1)).isoformat(),
        "end_at": (now + timedelta(hours=1)).isoformat()}).json()
    client.put(f"/api/reios/admin/exams/{exam['id']}/items", headers=auth(adm),
               json={"items": [{"item_type": "mcq", "question_id": q["id"]}]})
    client.post(f"/api/reios/admin/exams/{exam['id']}/publish", headers=auth(adm))

    def take(roll, pw, right):
        t = client.post("/api/reios/auth/login", json={"identifier": roll, "password": pw, "college_code": "HFEST"}).json()
        t = client.post("/api/reios/auth/change-password", headers=auth(t["access_token"]),
                        json={"current_password": pw, "new_password": pw + "xyz1"}).json()["access_token"]
        p = client.post(f"/api/reios/student/exams/{exam['id']}/start", headers=auth(t)).json()
        item = p["items"][0]
        opt = next(o["id"] for o in item["options"] if (o["text"] == "4") == right)
        h = {**auth(t), "X-Exam-Session": p["session"]}
        client.put(f"/api/reios/student/attempts/{p['attempt_id']}/mcq/{item['item_id']}", headers=h, json={"selected": [opt]})
        client.post(f"/api/reios/student/attempts/{p['attempt_id']}/submit", headers=h)
        return t, p["attempt_id"]

    t1, a1 = take("HF1", "student1", True)
    t2, a2 = take("HF2", "student2", False)
    me = client.get("/api/reios/auth/me", headers=auth(t1)).json()
    assert me["college"]["branding"]["color"] == "#0f766e"

    r = client.get(f"/api/reios/student/attempts/{a1}/result", headers=auth(t1)).json()
    assert r["certificate_available"] is False
    assert client.post("/api/reios/super/colleges", headers=auth(root), json={
        "name": "Cert", "code": "CERTX", "org_type": "event", "features": ["certificates"]}).status_code == 400

    # Email results through a stand-in mail server
    sent = []

    class FakeSMTP:
        def __init__(self, *a, **k): pass
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def starttls(self): pass
        def login(self, *a): pass
        def send_message(self, msg): sent.append((msg["To"], msg.get_content()))
    assert client.post(f"/api/reios/admin/exams/{exam['id']}/email-results", headers=auth(adm)).status_code == 503
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr(settings, "SMTP_FROM", "results@reios.app")
    monkeypatch.setattr(feat.smtplib, "SMTP", FakeSMTP)
    r = client.post(f"/api/reios/admin/exams/{exam['id']}/email-results", headers=auth(adm)).json()
    assert r == {"sent": 1, "skipped": 1, "failed": []}
    assert sent[0][0] == "priya@mail.com" and "Rank: 1 of 2" in sent[0][1]

    # Turning the add-on off takes it away
    client.patch(f"/api/reios/super/colleges/{ev['id']}", headers=auth(root), json={"features": ["branding"]})
    assert client.post(f"/api/reios/admin/exams/{exam['id']}/email-results", headers=auth(adm)).status_code == 403
    # Switching to a college clears them
    r = client.patch(f"/api/reios/super/colleges/{ev['id']}", headers=auth(root), json={"org_type": "college"}).json()
    assert r["features"] == []

    # Event students keep the password the organizer gave them; college students still must change theirs
    client.patch(f"/api/reios/super/colleges/{ev['id']}", headers=auth(root), json={"org_type": "event", "features": ["branding"]})
    client.post("/api/reios/admin/students", headers=auth(adm), json={"roll_no": "HF3", "name": "Fresh", "password": "student3"})
    r = client.post("/api/reios/auth/login", json={"identifier": "HF3", "password": "student3", "college_code": "HFEST"}).json()
    assert r["user"]["must_change_password"] is False
    ft = r["access_token"]
    assert client.post(f"/api/reios/student/exams/{exam['id']}/start", headers=auth(ft)).status_code == 200
    college_login = client.post("/api/reios/auth/login", json={"identifier": "21cs001", "password": "student1", "college_code": "tec"})
    assert college_login.status_code in (200, 401)  # college rule is covered by test_full_exam_flow

    # Leaderboard opens right after a student submits, even when results aren't published yet
    now_exam = client.get(f"/api/reios/admin/exams/{exam['id']}", headers=auth(adm)).json()
    upd = {k: now_exam[k] for k in ("title", "start_at", "end_at", "duration_minutes", "exam_type")}
    r = client.put(f"/api/reios/admin/exams/{exam['id']}", headers=auth(adm),
                   json={**upd, "show_leaderboard": True, "show_results": False})
    assert r.status_code == 200, r.text
    r = client.get(f"/api/reios/student/exams/{exam['id']}/leaderboard", headers=auth(t1))
    assert r.status_code == 200 and r.json()["me"]["rank"] == 1
    assert client.get(f"/api/reios/student/exams/{exam['id']}/leaderboard", headers=auth(ft)).status_code == 404  # still writing

    usage = client.get("/api/reios/super/usage", headers=auth(root)).json()
    row = next(o for o in usage["organizations"] if o["code"] == "HFEST")
    assert row["students"] == 3 and row["exams_created"] == 1 and row["attempts"] == 3
    assert client.get("/api/reios/super/usage", headers=auth(adm)).status_code == 403
