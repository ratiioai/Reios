# Reios

Reios is a multi-college assessment platform for placement training and any other MCQ or coding
test: proctored exams, question sets uploaded from Word / PDF / Excel, live monitoring, results and
leaderboards. The API is FastAPI (`backend/`, routes under `/api/reios/`); the UI is React (`web/`).

## Roles

| Role | Who | Can do |
|---|---|---|
| **Super Admin** | Platform owner. Signs in with **Firebase** (Google or Firebase email/password) when it's set up | Add, disable and **delete** colleges, create college admins and reset their passwords, manage the **global question bank** shared by all colleges, post announcements to every college, and act inside any college. |
| **College Admin** | Placement officer (TPO) of one college | Upload students, build the college's own question bank, create exams, upload question sets, watch exams live, view results and leaderboards. Can only see their own college. |
| **Student** | Signs in with **college code + roll number** | Sees exams for their branch/batch/section, takes proctored exams, sees scores, section-wise analysis, answer review and (if enabled) the leaderboard. |

## Features

- **Exam types**: MCQ only, Coding only, or MCQ + Coding. Section names are free text (GK, Physics, English, …).
- **Question sets**: one exam can have many paper variants. Upload **one file holding every set** (start
  each with a heading like `Set 1` or `Section: General Knowledge – Set 1`) or **one file per set**; they
  become Set 1, Set 2, … automatically. Review what was read, fix answers, save. Every student sits the
  exam's common questions (if any) plus one set.
- **Automatic set assignment** (on by default): in roll-number order students 1–10 get Sets 1–10, then it
  repeats (300 students and 10 sets → 30 per set). Re-applied whenever a set is added or removed. Changing
  a student by hand, or uploading a `roll_no,set` sheet, turns it off so your choices stay.
- **Uploads**: MCQs from Word / PDF / Excel / CSV / text; student logins from Excel / CSV / Word tables
  (PDF tables when columns are clearly separated). `samples/` has files that import correctly, including
  `gk_10_sets_in_one_file.docx`.
- **Preview test**: admins see the paper exactly as students do, per set, with an optional show-answers toggle.
- **Leaderboard**: per exam or overall (average % across exams), filter by branch, export CSV. Each exam
  can also show students the top 10 and their own rank. Ranking uses percentage, so different sets compare fairly.
- **MCQs**: single or multiple correct answers, per-question marks, optional negative marking, explanations, random pick from the bank.
- **Coding**: Python, C++, C, Java and JavaScript; sample tests students can run, hidden tests for scoring
  (partial marks per test passed), custom input, starter code, and a "test with reference solution" check.
- **Scheduling**: open and close window, per-student duration (capped at the close time), audience filters
  by branch, batch and section, publish or unpublish, duplicate an exam (with its sets).
- **Anti-cheat**: fullscreen enforcement, tab/window-switch detection, blocked copy/paste/right-click/dev
  tools, auto-submit after N violations, one session per attempt, server-side timer, question and option
  shuffling, multi-monitor check, roll-number watermark, IP/browser log, proctoring event log, code similarity report.
- **Live monitor**: who's writing, online status, progress, violations and time left; extend time, forgive violations, force-submit.
- **Results**: ranked list, set and section-wise scores, pass/fail, absentees, answer and event review, CSV export.
- **Accounts**: temporary passwords changed at first login, lockout after 5 failed logins, bulk password
  reset, disabling a college blocks its users, deleting a college removes all its data.

## Exam day

Double-click **`START_REIOS.bat`** (4 server processes; tested with 300 students starting together).
Students open `http://<server-IP>:8000/app/`.

Load test (300 students, 10 sets, one Windows laptop running both the server and the test):
- every student started and submitted; answer saves took ~60 ms (95% under 135 ms) with no errors
- the opening rush (everyone signs in and presses Start within 2 seconds) took ~30 s to clear;
  students who sign in a few minutes early only wait for Start (~4 s)

For larger exams or a public server, prefer **Linux** (Windows 11 Home limits simultaneous incoming
connections) and **PostgreSQL** (`DATABASE_URL`), with `--workers` set to the CPU core count.

## Setup

```bash
# 1. Frontend
cd web
cp .env.example .env            # optional: Firebase web config for super admin sign-in
npm install
npm run build                   # outputs web/dist, served by the backend at /app/

# 2. Backend
cd ../backend
cp .env.example .env            # SECRET_KEY, SUPER_ADMIN_EMAIL, and FIREBASE_PROJECT_ID or SUPER_ADMIN_PASSWORD
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

Open **http://localhost:8000/app/**, sign in as the super admin, add a college and its admin.
`python seed_demo.py` loads an optional demo college if you want something to click through.

### Super admin sign-in with Firebase

1. Firebase console → **Authentication → Sign-in method**: enable **Google** and/or **Email/Password**.
2. `web/.env`: your web app config (`VITE_FIREBASE_API_KEY`, `_AUTH_DOMAIN`, `_PROJECT_ID`, `_APP_ID`), then `npm run build`.
3. `backend/.env`: `FIREBASE_PROJECT_ID=<project id>` and `SUPER_ADMIN_EMAIL=you@gmail.com` (comma-separate several).
4. If people reach Reios at an address other than `localhost` (a LAN IP or a domain), add it in Firebase →
   **Authentication → Settings → Authorized domains**.

Only emails in `SUPER_ADMIN_EMAIL` get in, the email must be verified, and the first Firebase account to
sign in is bound to that super admin. While Firebase is on, super admin password sign-in is refused.
Firestore isn't used; all data is in the Reios database. To fall back to passwords (e.g. no internet on
exam day), remove `FIREBASE_PROJECT_ID` and run `python create_super_admin.py`.

### Frontend development and Vercel

Run the backend, then `npm run dev` in `web/` and open http://localhost:5173/app/ (it proxies `/api`).
To host the frontend on Vercel, point a project at `web/` and set `VITE_BASE=/` and
`VITE_API_BASE=https://your-backend.example.com`. The backend can't run on Vercel: it compiles student
code and needs a persistent database, so host it on a real server (Render, Railway, Fly.io or a VPS).

## Sheet formats

Students: `roll_no,name,email,phone,branch,section,batch_year,password` (only roll number and name
required; headers like "Roll Number", "Username", "Student Name", "Department" also work).

MCQs (Excel/CSV): `section,topic,difficulty,question,option_a,option_b,option_c,option_d,correct,marks,negative_marks,explanation`
(`correct` is a letter, or several like `A,C`; option_e … option_h are optional). Templates download from the console.

## Important for production

- **Student code runs on the server itself** without a sandbox. Run the backend in a container or VM with
  no secrets on it, or switch execution to an isolated runner such as Piston.
- Browser anti-cheat deters casual cheating but can't stop a second device. Use it with invigilation.

## Tests

```bash
cd backend
python -m pytest tests -q
```
