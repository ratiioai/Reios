# Coding Test Platform - 175 Teams

Production-ready coding test platform for 175 teams with auto-grading and unique question sets.

**Project Status:** Foundation Complete (23%) → Backend Implementation Phase

📋 **[View Implementation Roadmap](./IMPLEMENTATION_ROADMAP.md)**  
📐 **[View Design Spec](./.kiro/specs/platform-implementation/design.md)**  
✅ **[View Tasks](./.kiro/specs/platform-implementation/tasks.md)**

## Features

- **CSV Team Provisioning**: Upload 175 teams at once, auto-generate credentials
- **Unique Question Sets**: Each team gets 10 easy + 10 medium + 5 hard questions (no duplicates)
- **Auto-Grading**: Code execution against hidden test cases (no Docker required)
- **Live Leaderboard**: Score DESC, then time taken ASC for tiebreaking
- **Admin Controls**: Question bank management, manual grade override, audit logging
- **Secure**: OS-level sandboxing for code execution, rate limiting, JWT auth

## Architecture

- **Backend**: FastAPI (Python 3.11+)
- **Database**: PostgreSQL 15+
- **Frontend**: Next.js 14 + TypeScript + Tailwind CSS
- **Code Execution**: Piston API (hosted) or OS-level sandboxing
- **Auth**: JWT tokens with team name + phone hash

## Quick Start

See `docs/SETUP.md` for detailed instructions.

## Scoring

- Easy questions: 5 marks each (10 questions = 50 marks)
- Medium questions: 10 marks each (10 questions = 100 marks)  
- Hard questions: 20 marks each (5 questions = 100 marks)
- **Total**: 250 marks maximum per team

## Test Structure

- 25 questions per team (unique set for each team)
- 120 minutes (configurable)
- Auto-submit on timer expiry
- Single attempt only

## Development

```bash
# Backend
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload

# Frontend
cd frontend
npm install
npm run dev
```

## Production Deployment

- Railway (recommended)
- Render
- Any VPS with PostgreSQL

No Docker required for deployment or code execution.
