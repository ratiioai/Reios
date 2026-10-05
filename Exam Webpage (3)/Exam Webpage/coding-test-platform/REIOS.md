# Reios

Reios is a multi-college assessment platform for placement training: MCQ sections, live coding,
proctoring and results. It runs alongside the older team contest in this backend; its tables are
prefixed `reios_` and its API lives under `/api/reios/`.

## Roles

| Role | Who | Can do |
|---|---|---|
| **Super Admin** | Platform owner | Add/disable colleges, create college admins, reset their passwords, manage the **global question bank** shared by all colleges, post announcements to every college, and act inside any college. |
| **College Admin** | Placement officer (TPO) of one college | Add students (form or CSV import), reset passwords, build the college's own MCQ and coding bank, create and schedule exams, watch them live, view results, export CSV, check code similarity. Can only see their own college. |
| **Student** | Signs in with **college code + roll number** | Sees exams for their branch/batch/section, takes proctored exams, sees scores, section-wise analysis and answer review. |

## Features

- **Exams with mixed sections**: Quantitative Aptitude, Logical Reasoning, Verbal Ability, Technical (MCQ) and Coding.
- **MCQs**: single or multiple correct answers, per-question marks, optional negative marking, explanations, CSV import, random pick from the bank by section and difficulty.
- **Coding**: Python, C++, C, Java and JavaScript; sample tests students can run, hidden tests for scoring (partial marks per test passed), custom input, starter code, and a "test with reference solution" check for admins.
- **Scheduling**: open and close window, per-student duration (capped at the close time), audience filters by branch, batch and section, publish or unpublish, duplicate an exam.
- **Anti-cheat**:
  - fullscreen enforcement, with a blocking overlay when the student leaves fullscreen
  - tab or window switch detection
  - copy, paste, right-click and developer-tool shortcuts blocked (pasting into the code editor is cancelled)
  - auto-submit after N violations
  - one active session per attempt: opening the exam elsewhere locks the old tab
  - timer enforced on the server, so the exam auto-submits when time runs out even if the browser is closed
  - question and option shuffling per student
  - multi-monitor check before start, and a roll-number watermark on the exam screen
  - IP and browser logged, and a full proctoring event log per attempt
  - code similarity report across students
- **Live monitor**: who's writing, online status, progress, violations and time left. Admins can extend time, forgive violations or force-submit.
- **Results**: ranked list, section-wise scores, pass/fail, absentees, per-student answer and event review, CSV export, student history report.
- **Accounts**: temporary passwords that must be changed at first login, lockout after 5 failed logins, bulk password reset with a credentials CSV, and disabling a college blocks all its users.

## Quick start

```bash
cd backend
pip install -r requirements.txt
# .env: set SECRET_KEY, DATABASE_URL, SUPER_ADMIN_EMAIL, SUPER_ADMIN_PASSWORD
python seed_demo.py              # optional demo college, students and a mock test
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Open **http://localhost:8000/app/reios/**. The backend serves the frontend too.

Demo logins (from `seed_demo.py`; delete them before real use):
- College admin: `tpo@demo.edu` / `DemoAdmin@123` (Staff tab)
- Students: college code `DEMO`, roll `21DEMO001` … `21DEMO004`, password `Student@123`

## CSV formats

Students: `roll_no,name,email,phone,branch,section,batch_year,password` (only roll_no and name required).

MCQs: `section,topic,difficulty,question,option_a,option_b,option_c,option_d,correct,marks,negative_marks,explanation`
(`correct` is a letter, or several like `A,C`; option_e … option_h are optional).

Both templates can be downloaded from the console.

## Important for production

- **Code runs on the server itself** (`code_compiler_tester.py`) without a sandbox. For a real exam, run the
  backend in a container or VM with no secrets on it, or switch execution to an isolated runner such as Piston.
- Use PostgreSQL (`DATABASE_URL`) for more than a few dozen simultaneous students; SQLite is fine for testing.
- Browser anti-cheat deters casual cheating but can't stop a second device. Use it together with invigilation.

## Tests

```bash
cd backend
python -m pytest tests/test_reios.py -q
```
