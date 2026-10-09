"""Static review: file/LOC inventory, every API endpoint, risky code patterns, secrets in the repo."""
import json
import re
import subprocess
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(r"C:\Users\Dell\Downloads\reios\Reios")
APP = REPO / "Exam Webpage (3)" / "Exam Webpage" / "coding-test-platform"
OUT = Path(r"C:\reios-server\qa\results\code_inventory.json")

tracked = subprocess.run(["git", "-C", str(REPO), "ls-files"], capture_output=True, text=True).stdout.splitlines()
ext_lang = {".py": "Python", ".jsx": "React (JSX)", ".js": "JavaScript", ".css": "CSS", ".ps1": "PowerShell",
            ".md": "Docs", ".html": "HTML", ".yaml": "Config", ".yml": "Config", ".json": "Config", ".conf": "Config"}
loc = Counter(); files = Counter()
for rel in tracked:
    p = REPO / rel
    lang = ext_lang.get(p.suffix.lower())
    if not lang or "node_modules" in rel or not p.is_file():
        continue
    try:
        n = sum(1 for _ in p.open(encoding="utf-8", errors="ignore"))
    except OSError:
        continue
    loc[lang] += n; files[lang] += 1

# Every API route
routes = []
prefixes = {}
for f in sorted((APP / "backend" / "app" / "reios").glob("routes_*.py")):
    src = f.read_text(encoding="utf-8")
    m = re.search(r'APIRouter\(prefix="([^"]+)"', src)
    prefix = m.group(1) if m else ""
    for meth, path in re.findall(r'@router\.(get|post|put|patch|delete)\("([^"]*)"', src):
        auth = "public"
        body = src[src.find(f'@router.{meth}("{path}"'):][:600]
        if "require_super_admin" in body: auth = "super admin"
        elif "scoped_college_id" in body or "require_admin" in body or "bank_scope" in body: auth = "admin"
        elif "require_student" in body: auth = "student"
        elif "get_current_user" in body: auth = "any signed-in"
        routes.append({"method": meth.upper(), "path": prefix + path, "file": f.name, "auth": auth})
main_src = (APP / "backend" / "app" / "main.py").read_text(encoding="utf-8")
for path in re.findall(r'@app\.get\("([^"]+)"', main_src):
    routes.append({"method": "GET", "path": path, "file": "main.py", "auth": "public"})

# Risky patterns in backend code (excluding tests)
patterns = {
    "raw SQL (text())": r"\btext\(",
    "subprocess / process spawn": r"subprocess\.|Popen\(",
    "eval/exec": r"\beval\(|\bexec\(",
    "pickle/yaml load": r"pickle\.loads|yaml\.load\(",
    "shell=True": r"shell\s*=\s*True",
    "hard-coded password-looking literal": r"(password|secret)\s*=\s*['\"][^'\"]{6,}['\"]",
}
findings = defaultdict(list)
for f in (APP / "backend").rglob("*.py"):
    if "venv" in f.parts or "tests" in f.parts or "__pycache__" in f.parts:
        continue
    for i, line in enumerate(f.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
        for name, rx in patterns.items():
            if re.search(rx, line, re.I):
                findings[name].append(f"{f.relative_to(APP)}:{i}: {line.strip()[:110]}")

# Secrets that must never be in git
secret_rx = re.compile(r"postgresql://[^:\s]+:[^@\s]{8,}@|BEGIN (RSA|EC|OPENSSH) PRIVATE KEY|AKIA[0-9A-Z]{16}")
leaks = []
for rel in tracked:
    p = REPO / rel
    if p.suffix.lower() in {".png", ".jpg", ".pdf", ".docx", ".xlsx", ".ico"} or not p.is_file():
        continue
    try:
        for i, line in enumerate(p.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
            if secret_rx.search(line):
                leaks.append(f"{rel}:{i}")
    except OSError:
        pass
env_tracked = [r for r in tracked if Path(r).name in (".env", "server.env", "db-passwords.txt", ".secret_key")]

result = {
    "files_by_language": dict(files), "lines_by_language": dict(loc),
    "total_files": sum(files.values()), "total_lines": sum(loc.values()),
    "routes": routes, "route_count": len(routes),
    "routes_by_auth": dict(Counter(r["auth"] for r in routes)),
    "risky_patterns": {k: v for k, v in findings.items()},
    "secret_leaks": leaks, "env_files_tracked": env_tracked,
}
OUT.write_text(json.dumps(result, indent=1))
print(f"{result['total_files']} source files, {result['total_lines']} lines: {dict(loc)}")
print(f"{len(routes)} API endpoints by protection: {result['routes_by_auth']}")
for k, v in findings.items():
    print(f"\n{k} ({len(v)}):"); [print("  ", x) for x in v[:8]]
print("\nsecrets in git:", leaks or "none", "| env files tracked:", env_tracked or "none")
