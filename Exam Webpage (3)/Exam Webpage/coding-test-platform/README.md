# Reios

Proctored assessment platform for colleges: MCQ and coding exams, question sets uploaded from
Word / PDF / Excel, live monitoring, results and leaderboards. Full guide: **[REIOS.md](./REIOS.md)**.

## Run it

- **Exam day (Windows):** double-click `START_REIOS.bat`, then open http://localhost:8000/app/
  (other machines on the network: `http://<this-PC's-IP>:8000/app/`).
- **Development:** see "Quick start" in REIOS.md.

## Layout

| Folder | What it is |
|---|---|
| `web/` | React frontend (Vite). `npm run build` -> `web/dist`, served by the backend at `/app/` |
| `backend/app/reios/` | Reios API, exam engine, document parsers, Firebase sign-in check |
| `backend/compilers/` | C/C++ compilers used to run students' code on Windows |
| `backend/tests/` | `python -m pytest tests -q` |
| `samples/` | Question-set and student-list files that import correctly |
