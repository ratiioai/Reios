import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from code_compiler_tester import CodeCompilerTester
from app.database import SessionLocal
from app.models import Question

db = SessionLocal()
q = db.query(Question).filter(Question.id == 51).first()

code = """import sys

def solve():
    A, B, C = map(int, sys.stdin.readline().split())
    average = (A + B + C) // 3
    print(average)

if __name__ == '__main__':
    solve()
"""

tests = [{"input": s.input_data, "expected_output": s.expected_output} for s in q.sample_test_cases] + \
        [{"input": h.input_data, "expected_output": h.expected_output} for h in q.hidden_test_cases]

res = CodeCompilerTester.test_solution(code, "python", tests)
print(f"Passed: {res['passed']}/{res['total']} (All passed: {res['all_passed']})")
for r in res['results']:
    print(f"  Input: {repr(r['input'])} -> Expected: {repr(r['expected'])}, Got: {repr(r['actual'])} -> {'PASS' if r['passed'] else 'FAIL'}")
