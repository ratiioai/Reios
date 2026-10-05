import sqlite3
import re
import os
import populate_all_350_direct as pop

DB_PATH = os.path.join(os.path.dirname(__file__), 'coding_test.db')
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()
cursor.execute("SELECT id, title, prompt_markdown FROM questions WHERE id BETWEEN 26 AND 50 ORDER BY id")
questions = cursor.fetchall()

for idx, (q_id, title, prompt) in enumerate(questions, 1):
    clean_title = re.sub(r'^\[.*?\]\s*', '', title).strip()
    print(f"Testing Q{q_id}: {clean_title}...", flush=True)
    sample_inps, hidden_inps = pop.get_inputs(clean_title)
    for inp, note in sample_inps:
        out = pop.solve_fast(clean_title, prompt, inp)
    for inp in hidden_inps:
        out = pop.solve_fast(clean_title, prompt, inp)
    print(f"  Q{q_id} OK -> Sample: {out}", flush=True)

print("Q26-50 DONE!")
