"""
SIMPLE QUESTION GENERATOR - RUN THIS DIRECTLY!
No virtual environment needed - uses your system Python
"""
import subprocess
import sys

print("=" * 80)
print("INSTALLING DEPENDENCIES...")
print("=" * 80)

# Install required packages
packages = [
    "openai",
    "requests",
    "sqlalchemy",
    "psycopg2-binary",
    "pydantic",
    "pydantic-settings",
    "python-dotenv"
]

for package in packages:
    print(f"Installing {package}...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package, "-q"])
    except subprocess.CalledProcessError:
        print(f"   {package} may already be installed or failed, continuing...")

print("\n" + "=" * 80)
print("DEPENDENCIES INSTALLED! STARTING QUESTION GENERATION...")
print("=" * 80)
print()

# Now run the actual generator with proper encoding
with open("ai_question_generator.py", "r", encoding="utf-8") as f:
    exec(f.read())
