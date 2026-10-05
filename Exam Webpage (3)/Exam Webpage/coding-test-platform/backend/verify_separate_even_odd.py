import sqlite3
import os
from code_compiler_tester import CodeCompilerTester

DB_PATH = os.path.join(os.path.dirname(__file__), 'coding_test.db')
conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

c.execute("SELECT id, title, prompt_markdown FROM questions WHERE title LIKE '%Separate Even and Odd%'")
q_list = c.fetchall()

for q_id, title, prompt in q_list:
    print(f"\n=========================================")
    print(f"VERIFYING Q{q_id}: {title}")
    print(f"=========================================")
    c.execute("SELECT input_data, expected_output FROM sample_test_cases WHERE question_id = ?", (q_id,))
    samples = [{"input": r[0], "expected_output": r[1]} for r in c.fetchall()]
    
    c.execute("SELECT input_data, expected_output FROM hidden_test_cases WHERE question_id = ?", (q_id,))
    hidden = [{"input": r[0], "expected_output": r[1]} for r in c.fetchall()]
    
    all_tests = samples + hidden
    
    # User's Python Solution
    code = """import sys

def solve():
    input_data = sys.stdin.read().split()
    if not input_data:
        return
    if len(input_data) > 1 and int(input_data[0]) == len(input_data) - 1:
        arr = [int(x) for x in input_data[1:]]
    else:
        arr = [int(x) for x in input_data]
    evens = [str(x) for x in arr if x % 2 == 0]
    odds = [str(x) for x in arr if x % 2 != 0]
    result = evens + odds
    print(*result)

if __name__ == '__main__':
    solve()
"""
    res = CodeCompilerTester.test_solution(code, "python", all_tests)
    print(f"Pass Rate: {res['passed']}/{res['total']} (All Passed: {res['all_passed']})")
    for r in res['results']:
        inp_str = r['input'].replace('\n', ' ')
        print(f"  Input: '{inp_str}' -> Exp: '{r['expected']}', Got: '{r['actual']}' | Passed: {r['passed']}")
