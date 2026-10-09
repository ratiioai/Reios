#!/bin/bash
# run_load.sh <name> <base_url> <teams> [extra loadtest args...]
# Creates a fresh exam, runs the realistic load test, and records the time window for later analysis.
PY="/c/Users/Dell/Downloads/reios/Reios/Exam Webpage (3)/Exam Webpage/coding-test-platform/backend/venv/Scripts/python.exe"
NAME=$1; BASE=$2; TEAMS=$3; shift 3
cd /c/reios-server/tests
EXAM=$("$PY" loadtest.py newexam gk10.docx 2>&1 | tail -1 | awk '{print $3}')
START=$(date +%H:%M:%S)
LT_BASE=$BASE PYTHONIOENCODING=utf-8 "$PY" loadtest.py run "$EXAM" "$TEAMS" 120 1000000 0 8 20 150 > "/c/reios-server/qa/results/load_${NAME}.txt" 2>&1
END=$(date +%H:%M:%S)
echo "{\"name\": \"$NAME\", \"base\": \"$BASE\", \"teams\": $TEAMS, \"exam\": $EXAM, \"start\": \"$START\", \"end\": \"$END\"}" > "/c/reios-server/qa/results/load_${NAME}.meta.json"
echo "done $NAME"
