"""
Script to create sample questions for testing
Run after starting the server: python create_sample_questions.py
"""
import requests
import sys

API_BASE = "http://localhost:8000"

# Sample questions bank
QUESTIONS = [
    # EASY QUESTIONS (need many for 175 teams × 10 each)
    {
        "title": "Sum Two Numbers",
        "difficulty": "easy",
        "prompt_markdown": "Write a function that returns the sum of two numbers.",
        "starter_code_python": "def sum_two(a, b):\n    pass",
        "time_limit_seconds": 5,
        "memory_limit_mb": 256,
        "sample_test_cases": [
            {"input_data": "2\n3", "expected_output": "5", "order": 0}
        ],
        "hidden_test_cases": [
            {"input_data": "10\n20", "expected_output": "30", "order": 0},
            {"input_data": "-5\n5", "expected_output": "0", "order": 1},
            {"input_data": "100\n200", "expected_output": "300", "order": 2}
        ]
    },
    {
        "title": "Check Even Number",
        "difficulty": "easy",
        "prompt_markdown": "Return True if number is even, False otherwise.",
        "starter_code_python": "def is_even(n):\n    pass",
        "time_limit_seconds": 5,
        "memory_limit_mb": 256,
        "sample_test_cases": [
            {"input_data": "4", "expected_output": "True", "order": 0}
        ],
        "hidden_test_cases": [
            {"input_data": "7", "expected_output": "False", "order": 0},
            {"input_data": "0", "expected_output": "True", "order": 1},
            {"input_data": "100", "expected_output": "True", "order": 2}
        ]
    },
    {
        "title": "String Length",
        "difficulty": "easy",
        "prompt_markdown": "Return the length of a string.",
        "starter_code_python": "def string_length(s):\n    pass",
        "time_limit_seconds": 5,
        "memory_limit_mb": 256,
        "sample_test_cases": [
            {"input_data": "hello", "expected_output": "5", "order": 0}
        ],
        "hidden_test_cases": [
            {"input_data": "world", "expected_output": "5", "order": 0},
            {"input_data": "", "expected_output": "0", "order": 1},
            {"input_data": "python programming", "expected_output": "18", "order": 2}
        ]
    },
    {
        "title": "Maximum of Two",
        "difficulty": "easy",
        "prompt_markdown": "Return the maximum of two numbers.",
        "starter_code_python": "def maximum(a, b):\n    pass",
        "time_limit_seconds": 5,
        "memory_limit_mb": 256,
        "sample_test_cases": [
            {"input_data": "5\n10", "expected_output": "10", "order": 0}
        ],
        "hidden_test_cases": [
            {"input_data": "100\n50", "expected_output": "100", "order": 0},
            {"input_data": "-5\n-10", "expected_output": "-5", "order": 1},
            {"input_data": "0\n0", "expected_output": "0", "order": 2}
        ]
    },
    {
        "title": "Count Vowels",
        "difficulty": "easy",
        "prompt_markdown": "Count the number of vowels (a,e,i,o,u) in a string.",
        "starter_code_python": "def count_vowels(s):\n    pass",
        "time_limit_seconds": 5,
        "memory_limit_mb": 256,
        "sample_test_cases": [
            {"input_data": "hello", "expected_output": "2", "order": 0}
        ],
        "hidden_test_cases": [
            {"input_data": "world", "expected_output": "1", "order": 0},
            {"input_data": "aeiou", "expected_output": "5", "order": 1},
            {"input_data": "xyz", "expected_output": "0", "order": 2}
        ]
    },
    
    # MEDIUM QUESTIONS
    {
        "title": "Reverse String",
        "difficulty": "medium",
        "prompt_markdown": "Reverse a string without using built-in reverse functions.",
        "starter_code_python": "def reverse_string(s):\n    pass",
        "time_limit_seconds": 5,
        "memory_limit_mb": 256,
        "sample_test_cases": [
            {"input_data": "hello", "expected_output": "olleh", "order": 0}
        ],
        "hidden_test_cases": [
            {"input_data": "world", "expected_output": "dlrow", "order": 0},
            {"input_data": "a", "expected_output": "a", "order": 1},
            {"input_data": "racecar", "expected_output": "racecar", "order": 2}
        ]
    },
    {
        "title": "Fibonacci Number",
        "difficulty": "medium",
        "prompt_markdown": "Return the nth Fibonacci number (0-indexed).",
        "starter_code_python": "def fibonacci(n):\n    pass",
        "time_limit_seconds": 5,
        "memory_limit_mb": 256,
        "sample_test_cases": [
            {"input_data": "5", "expected_output": "5", "order": 0}
        ],
        "hidden_test_cases": [
            {"input_data": "0", "expected_output": "0", "order": 0},
            {"input_data": "1", "expected_output": "1", "order": 1},
            {"input_data": "10", "expected_output": "55", "order": 2}
        ]
    },
    {
        "title": "Palindrome Check",
        "difficulty": "medium",
        "prompt_markdown": "Check if a string is a palindrome (reads same forwards and backwards).",
        "starter_code_python": "def is_palindrome(s):\n    pass",
        "time_limit_seconds": 5,
        "memory_limit_mb": 256,
        "sample_test_cases": [
            {"input_data": "racecar", "expected_output": "True", "order": 0}
        ],
        "hidden_test_cases": [
            {"input_data": "hello", "expected_output": "False", "order": 0},
            {"input_data": "a", "expected_output": "True", "order": 1},
            {"input_data": "madam", "expected_output": "True", "order": 2}
        ]
    },
    
    # HARD QUESTIONS
    {
        "title": "Two Sum",
        "difficulty": "hard",
        "prompt_markdown": "Given an array of integers and a target, return indices of two numbers that add up to target.",
        "starter_code_python": "def two_sum(nums, target):\n    pass",
        "time_limit_seconds": 5,
        "memory_limit_mb": 256,
        "sample_test_cases": [
            {"input_data": "[2,7,11,15]\n9", "expected_output": "[0,1]", "order": 0}
        ],
        "hidden_test_cases": [
            {"input_data": "[3,2,4]\n6", "expected_output": "[1,2]", "order": 0},
            {"input_data": "[3,3]\n6", "expected_output": "[0,1]", "order": 1}
        ]
    },
    {
        "title": "Valid Parentheses",
        "difficulty": "hard",
        "prompt_markdown": "Check if a string of parentheses is valid (properly opened and closed).",
        "starter_code_python": "def is_valid_parentheses(s):\n    pass",
        "time_limit_seconds": 5,
        "memory_limit_mb": 256,
        "sample_test_cases": [
            {"input_data": "()", "expected_output": "True", "order": 0}
        ],
        "hidden_test_cases": [
            {"input_data": "()[]{}", "expected_output": "True", "order": 0},
            {"input_data": "(]", "expected_output": "False", "order": 1},
            {"input_data": "({[]})", "expected_output": "True", "order": 2}
        ]
    }
]


def main():
    # Login as admin
    print("Logging in as admin...")
    try:
        response = requests.post(
            f"{API_BASE}/api/auth/admin/login",
            json={"username": "admin", "password": "admin123"}
        )
        response.raise_for_status()
        token = response.json()["access_token"]
        print("✓ Logged in successfully")
    except Exception as e:
        print(f"✗ Login failed: {e}")
        print("\nMake sure:")
        print("1. Server is running (python -m uvicorn app.main:app --reload)")
        print("2. Admin password is 'admin123' in .env")
        sys.exit(1)
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    # Create questions
    print(f"\nCreating {len(QUESTIONS)} sample questions...")
    created = 0
    failed = 0
    
    for q in QUESTIONS:
        try:
            response = requests.post(
                f"{API_BASE}/api/admin/questions",
                json=q,
                headers=headers
            )
            response.raise_for_status()
            created += 1
            print(f"✓ Created: {q['title']} ({q['difficulty']})")
        except Exception as e:
            failed += 1
            print(f"✗ Failed: {q['title']} - {e}")
    
    print(f"\n{'='*60}")
    print(f"Summary: {created} created, {failed} failed")
    print(f"{'='*60}")
    
    if created > 0:
        print("\n⚠️  IMPORTANT: You need at least 175 UNIQUE questions")
        print("   for 175 teams with unique question sets.")
        print("\n   Current: ~10 sample questions created")
        print("   Required: 175+ questions total")
        print("\n   To add more questions:")
        print("   1. Edit this file and add more to QUESTIONS list")
        print("   2. Or create questions via admin dashboard")
        print("   3. Or use API to bulk import from JSON/CSV")


if __name__ == "__main__":
    main()
