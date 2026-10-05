import urllib.request
import json

# 1. Login as SynX
login_url = 'https://partner-fabric-observations-automatic.trycloudflare.com/api/auth/team/login'
req = urllib.request.Request(login_url, data=json.dumps({'team_name':'SynX','leader_phone':'9655207578'}).encode('utf-8'), headers={'Content-Type':'application/json'})
token = json.loads(urllib.request.urlopen(req).read().decode('utf-8'))['access_token']

# 2. Run Code with float division
code = """import sys

def solve():
    A, B, C = map(int, sys.stdin.readline().split())
    average = (A + B + C) / 3
    print(average)

if __name__ == '__main__':
    solve()
"""

run_url = 'https://partner-fabric-observations-automatic.trycloudflare.com/api/teams/run-code'
run_req = urllib.request.Request(
    run_url,
    data=json.dumps({'code': code, 'language': 'python', 'question_id': 51}).encode('utf-8'),
    headers={'Content-Type':'application/json', 'Authorization': f'Bearer {token}'}
)
res = json.loads(urllib.request.urlopen(run_req).read().decode('utf-8'))

print("========================================")
print(f"RUN SUCCESS: {res['success']}")
print(f"ERROR: {res['error']}")
print("========================================")
for r in res.get('sample_test_results', []):
    print(f"Sample #{r['test_case']}: Passed={r['passed']} | Actual: {repr(r['actual_output'].strip())} vs Expected: {repr(r['expected_output'].strip())}")
