import sqlite3
import os
from code_compiler_tester import CodeCompilerTester

DB_PATH = os.path.join(os.path.dirname(__file__), 'coding_test.db')
conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

c.execute("SELECT id, title, prompt_markdown FROM questions WHERE id = 1")
q = c.fetchone()
q_id, title, prompt = q

c.execute("SELECT input_data, expected_output FROM hidden_test_cases WHERE question_id = 1")
hidden = [{"input": r[0], "expected_output": r[1]} for r in c.fetchall()]

print("=" * 60)
print(f"QUESTION: {title}")
print("=" * 60)

print("\n1. HARDCODED ATTEMPT: 'print(8)'")
res_fake = CodeCompilerTester.test_solution("print(8)", "python", hidden)
print(f"   Hidden Tests Passed: {res_fake['passed']}/{res_fake['total']}")
print(f"   Result: {'ACCEPTED' if res_fake['all_passed'] else 'REJECTED (0 MARKS)'}")
for idx, r in enumerate(res_fake['results'], 1):
    print(f"   - Test #{idx}: Input '{r['input']}' -> Expected '{r['expected']}', Got '{r['actual']}' -> {'PASS' if r['passed'] else 'FAIL'}")

print("\n2. GENUINE LOGIC: 'a, b = map(int, input().split()); print(a + b)'")
res_real = CodeCompilerTester.test_solution("a, b = map(int, input().split())\nprint(a + b)", "python", hidden)
print(f"   Hidden Tests Passed: {res_real['passed']}/{res_real['total']}")
print(f"   Result: {'ACCEPTED (FULL MARKS)' if res_real['all_passed'] else 'REJECTED'}")
for idx, r in enumerate(res_real['results'], 1):
    print(f"   - Test #{idx}: Input '{r['input']}' -> Expected '{r['expected']}', Got '{r['actual']}' -> {'PASS' if r['passed'] else 'FAIL'}")

print("\n3. DIFFERENT CODE STRUCTURE (Function & Multiple lines):")
fn_code = """def calculate_sum(num1, num2):
    return num1 + num2

if __name__ == '__main__':
    x, y = map(int, input().split())
    print(calculate_sum(x, y))
"""
res_fn = CodeCompilerTester.test_solution(fn_code, "python", hidden)
print(f"   Hidden Tests Passed: {res_fn['passed']}/{res_fn['total']}")
print(f"   Result: {'ACCEPTED (FULL MARKS)' if res_fn['all_passed'] else 'REJECTED'}")
