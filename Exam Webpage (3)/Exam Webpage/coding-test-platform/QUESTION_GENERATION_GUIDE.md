# AI Question Generation Guide

## 🤖 Auto-Generate 150+ Questions with Grok AI

Your Grok API key has been integrated to automatically create coding questions!

---

## Quick Start

### Step 1: Install Python Requirements

```bash
cd backend
venv\Scripts\activate
pip install openai  # Grok API uses OpenAI-compatible interface
```

### Step 2: Run the Generator

**Option A: Using Batch Script (Windows)**
```bash
cd backend
generate_questions_with_ai.bat
```

**Option B: Direct Python**
```bash
cd backend
venv\Scripts\activate
python ai_question_generator.py
```

### Step 3: Wait for Generation

- Generates **60 Easy** questions (5 marks each)
- Generates **60 Medium** questions (10 marks each)
- Generates **30 Hard** questions (20 marks each)
- **Total: 150 questions** (more than enough for 175 teams)
- Takes approximately **20-30 minutes**

Each question includes:
- Problem statement
- 2 sample test cases with explanations
- 5 hidden test cases
- Python starter code
- Time and memory limits

---

## Local Code Compiler (Alternative to Piston)

We've added a **local code compiler** that runs on your machine!

### Benefits:
- ✅ **No rate limits** (unlimited submissions/second)
- ✅ **Faster execution** (no network latency)
- ✅ **No internet required** during test
- ✅ **Supports Python, C++, Java, JavaScript**

### How to Enable:

1. **Edit `.env` file:**
```env
USE_LOCAL_COMPILER=true
```

2. **Install compilers on your system:**
   - **Python**: Already installed ✓
   - **C++**: Install MinGW or Visual Studio (for g++)
   - **Java**: Install JDK
   - **Node.js**: Install Node.js (for JavaScript)

3. **Test the compiler:**
```bash
cd backend
test_compiler.bat
```

### When to Use Each Method:

| Method | Best For | Speed | Rate Limit |
|--------|----------|-------|------------|
| **Local Compiler** | High traffic, offline testing | Very Fast | None ✓ |
| **Piston API** | Quick setup, no installs needed | Fast | 10 req/sec |

**Recommendation:** Use **local compiler** for tomorrow's test (175 teams = high load)

---

## Generated Question Structure

Each AI-generated question looks like:

```json
{
  "title": "Two Sum",
  "difficulty": "easy",
  "prompt": "Given an array of integers nums and an integer target...",
  "sample_test_cases": [
    {
      "input": "[2,7,11,15]\\n9",
      "output": "[0,1]",
      "explanation": "nums[0] + nums[1] = 2 + 7 = 9"
    }
  ],
  "hidden_test_cases": [
    {"input": "[3,2,4]\\n6", "output": "[1,2]"},
    {"input": "[3,3]\\n6", "output": "[0,1]"},
    ...
  ],
  "starter_code_python": "def two_sum(nums, target):\\n    pass",
  "marks": 5
}
```

---

## Troubleshooting

### Error: "Grok API key invalid"
- Check your API key in `.env` file
- Ensure `GROK_API_KEY` is set correctly
- Verify key is active at https://console.x.ai

### Error: "Rate limit exceeded"
- Grok has rate limits on API calls
- Script automatically retries with delays
- If persistent, reduce question count in script

### Error: "Local compiler not found"
- Install missing compilers:
  - Python: https://www.python.org/downloads/
  - C++: https://www.mingw-w64.org/
  - Java: https://www.oracle.com/java/technologies/downloads/
  - Node.js: https://nodejs.org/

### Questions not saving to database
- Ensure database is running (PostgreSQL)
- Check `DATABASE_URL` in `.env`
- Run: `python -c "from app.database import create_tables; create_tables()"`

---

## Manual Question Creation (Fallback)

If AI generation fails, you can create questions manually via Admin Dashboard:

1. Login as admin
2. Navigate to "Questions" section
3. Click "Add Question"
4. Fill in details:
   - Title
   - Difficulty
   - Problem statement
   - Test cases
   - Starter code

---

## After Question Generation

Once questions are generated:

1. ✅ **Verify count:**
   ```bash
   curl http://localhost:8000/api/admin/questions -H "Authorization: Bearer ADMIN_TOKEN"
   ```

2. ✅ **Upload teams:**
   - Go to admin dashboard
   - Upload `teams_real.csv`
   - System will automatically assign unique 25-question sets

3. ✅ **Start test:**
   - Configure test timing
   - Teams login and start

---

## API Key Security

🔒 **Important:** Never commit `.env` file to git!

The `.gitignore` already excludes:
- `.env`
- `.env.local`
- `.env.production`

Your Grok API key is safe in the `.env` file.

---

## Cost Estimate

Grok API pricing (as of 2024):
- ~150 questions × 2000 tokens each = ~300,000 tokens
- Estimated cost: **$1-3 USD** (very affordable)

---

## Next Steps

1. Run `generate_questions_with_ai.bat`
2. Wait for completion (20-30 min)
3. Upload `teams_real.csv`
4. Configure test timing
5. Launch test! 🚀

---

**Questions?** Check the logs in `backend/` directory or the API docs at http://localhost:8000/api/docs

