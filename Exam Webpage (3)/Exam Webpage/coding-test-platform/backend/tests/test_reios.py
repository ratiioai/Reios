"""
End-to-end tests for the Reios module: super admin -> college -> college admin -> students -> exam -> results.
Run from the backend folder:  python -m pytest tests/test_reios.py -q
"""
import os
import tempfile
from datetime import datetime, timedelta, timezone

_DB = os.path.join(tempfile.mkdtemp(), "reios_test.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_DB}"
os.environ["SUPER_ADMIN_EMAIL"] = "root@reios.test"
os.environ["SUPER_ADMIN_PASSWORD"] = "RootPass123"
os.environ.setdefault("ADMIN_PASSWORD", "legacy-admin-pass")

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
    assert client.post("/api/reios/auth/login", json={"identifier": "21CS001", "password": "student1"}).status_code == 400
    assert client.post("/api/reios/auth/login", json={"identifier": "21CS001", "password": "wrong",
                                                    "college_code": "TEC"}).status_code == 401


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
