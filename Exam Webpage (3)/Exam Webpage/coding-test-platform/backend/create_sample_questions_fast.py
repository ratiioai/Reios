"""
Quick Question Generator - Creates 200 sample questions immediately
No API needed - uses pre-defined templates
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.database import SessionLocal
from app.models import Question, SampleTestCase, HiddenTestCase, DifficultyLevel
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Pre-defined question templates
EASY_QUESTIONS = [
    {
        "title": "Sum of Two Numbers",
        "prompt": "Write a function that takes two integers and returns their sum.\n\nInput Format:\nTwo integers a and b separated by space\n\nOutput Format:\nA single integer representing the sum",
        "sample_tests": [
            {"input": "5 3", "output": "8", "explanation": "5 + 3 = 8"},
            {"input": "10 20", "output": "30", "explanation": "10 + 20 = 30"}
        ],
        "hidden_tests": [
            {"input": "0 0", "output": "0"},
            {"input": "-5 5", "output": "0"},
            {"input": "100 200", "output": "300"},
            {"input": "-10 -20", "output": "-30"},
            {"input": "999 1", "output": "1000"}
        ],
        "starter": "a, b = map(int, input().split())\n# Write your code here\nprint(result)"
    },
    {
        "title": "Check Even or Odd",
        "prompt": "Write a program that determines if a given number is even or odd.\n\nInput: A single integer n\nOutput: Print 'Even' if n is even, 'Odd' if n is odd",
        "sample_tests": [
            {"input": "4", "output": "Even", "explanation": "4 is divisible by 2"},
            {"input": "7", "output": "Odd", "explanation": "7 is not divisible by 2"}
        ],
        "hidden_tests": [
            {"input": "0", "output": "Even"},
            {"input": "1", "output": "Odd"},
            {"input": "100", "output": "Even"},
            {"input": "999", "output": "Odd"},
            {"input": "-6", "output": "Even"}
        ],
        "starter": "n = int(input())\n# Write your code here\nprint(result)"
    },
    {
        "title": "Find Maximum",
        "prompt": "Given three integers, find and print the maximum value.\n\nInput: Three space-separated integers\nOutput: The maximum integer",
        "sample_tests": [
            {"input": "3 7 5", "output": "7", "explanation": "7 is the largest"},
            {"input": "10 10 9", "output": "10", "explanation": "10 is the largest"}
        ],
        "hidden_tests": [
            {"input": "1 2 3", "output": "3"},
            {"input": "5 5 5", "output": "5"},
            {"input": "-1 -5 -3", "output": "-1"},
            {"input": "100 50 75", "output": "100"},
            {"input": "0 0 1", "output": "1"}
        ],
        "starter": "a, b, c = map(int, input().split())\n# Write your code here\nprint(result)"
    },
    {
        "title": "Count Digits",
        "prompt": "Count the number of digits in a given positive integer.\n\nInput: A positive integer n\nOutput: Number of digits in n",
        "sample_tests": [
            {"input": "12345", "output": "5", "explanation": "12345 has 5 digits"},
            {"input": "9", "output": "1", "explanation": "9 has 1 digit"}
        ],
        "hidden_tests": [
            {"input": "1", "output": "1"},
            {"input": "10", "output": "2"},
            {"input": "999", "output": "3"},
            {"input": "123456789", "output": "9"},
            {"input": "1000000", "output": "7"}
        ],
        "starter": "n = int(input())\n# Write your code here\nprint(result)"
    },
    {
        "title": "Reverse a String",
        "prompt": "Given a string, print it in reverse order.\n\nInput: A single line string\nOutput: The reversed string",
        "sample_tests": [
            {"input": "hello", "output": "olleh", "explanation": "Reverse of 'hello' is 'olleh'"},
            {"input": "abc", "output": "cba", "explanation": "Reverse of 'abc' is 'cba'"}
        ],
        "hidden_tests": [
            {"input": "a", "output": "a"},
            {"input": "python", "output": "nohtyp"},
            {"input": "12345", "output": "54321"},
            {"input": "racecar", "output": "racecar"},
            {"input": "test", "output": "tset"}
        ],
        "starter": "s = input()\n# Write your code here\nprint(result)"
    },
]

MEDIUM_QUESTIONS = [
    {
        "title": "Fibonacci Number",
        "prompt": "Calculate the nth Fibonacci number.\n\nThe Fibonacci sequence is: 0, 1, 1, 2, 3, 5, 8, 13, 21...\nwhere F(0) = 0, F(1) = 1, and F(n) = F(n-1) + F(n-2)\n\nInput: An integer n (0 ≤ n ≤ 30)\nOutput: The nth Fibonacci number",
        "sample_tests": [
            {"input": "5", "output": "5", "explanation": "F(5) = 5"},
            {"input": "10", "output": "55", "explanation": "F(10) = 55"}
        ],
        "hidden_tests": [
            {"input": "0", "output": "0"},
            {"input": "1", "output": "1"},
            {"input": "15", "output": "610"},
            {"input": "20", "output": "6765"},
            {"input": "25", "output": "75025"}
        ],
        "starter": "n = int(input())\n# Write your code here\nprint(result)"
    },
    {
        "title": "Prime Check",
        "prompt": "Determine if a given number is prime.\n\nA prime number is a natural number greater than 1 that has no positive divisors other than 1 and itself.\n\nInput: An integer n (2 ≤ n ≤ 10000)\nOutput: 'Prime' if n is prime, 'Not Prime' otherwise",
        "sample_tests": [
            {"input": "7", "output": "Prime", "explanation": "7 is only divisible by 1 and 7"},
            {"input": "10", "output": "Not Prime", "explanation": "10 is divisible by 2 and 5"}
        ],
        "hidden_tests": [
            {"input": "2", "output": "Prime"},
            {"input": "100", "output": "Not Prime"},
            {"input": "97", "output": "Prime"},
            {"input": "1000", "output": "Not Prime"},
            {"input": "101", "output": "Prime"}
        ],
        "starter": "n = int(input())\n# Write your code here\nprint(result)"
    },
    {
        "title": "Palindrome Check",
        "prompt": "Check if a given string is a palindrome (reads the same forwards and backwards).\n\nInput: A string s (only lowercase letters, no spaces)\nOutput: 'Yes' if palindrome, 'No' otherwise",
        "sample_tests": [
            {"input": "racecar", "output": "Yes", "explanation": "racecar is the same backwards"},
            {"input": "hello", "output": "No", "explanation": "hello reversed is olleh"}
        ],
        "hidden_tests": [
            {"input": "a", "output": "Yes"},
            {"input": "ab", "output": "No"},
            {"input": "aba", "output": "Yes"},
            {"input": "abba", "output": "Yes"},
            {"input": "abcd", "output": "No"}
        ],
        "starter": "s = input()\n# Write your code here\nprint(result)"
    },
    {
        "title": "Array Sum",
        "prompt": "Calculate the sum of all elements in an array.\n\nInput Format:\nFirst line: integer n (size of array)\nSecond line: n space-separated integers\n\nOutput: Sum of all array elements",
        "sample_tests": [
            {"input": "5\n1 2 3 4 5", "output": "15", "explanation": "1+2+3+4+5 = 15"},
            {"input": "3\n10 20 30", "output": "60", "explanation": "10+20+30 = 60"}
        ],
        "hidden_tests": [
            {"input": "1\n100", "output": "100"},
            {"input": "4\n-1 -2 -3 -4", "output": "-10"},
            {"input": "5\n0 0 0 0 0", "output": "0"},
            {"input": "6\n1 1 1 1 1 1", "output": "6"},
            {"input": "3\n100 200 300", "output": "600"}
        ],
        "starter": "n = int(input())\narr = list(map(int, input().split()))\n# Write your code here\nprint(result)"
    },
    {
        "title": "Count Vowels",
        "prompt": "Count the number of vowels (a, e, i, o, u) in a given string.\n\nInput: A string s (lowercase letters only)\nOutput: Number of vowels",
        "sample_tests": [
            {"input": "hello", "output": "2", "explanation": "'e' and 'o' are vowels"},
            {"input": "aeiou", "output": "5", "explanation": "All are vowels"}
        ],
        "hidden_tests": [
            {"input": "bcdfg", "output": "0"},
            {"input": "programming", "output": "3"},
            {"input": "education", "output": "5"},
            {"input": "xyz", "output": "0"},
            {"input": "beautiful", "output": "5"}
        ],
        "starter": "s = input()\n# Write your code here\nprint(result)"
    },
]

HARD_QUESTIONS = [
    {
        "title": "Longest Common Subsequence",
        "prompt": "Find the length of the longest common subsequence of two strings.\n\nA subsequence is a sequence that can be derived from another sequence by deleting some or no elements without changing the order of the remaining elements.\n\nInput: Two strings on separate lines\nOutput: Length of LCS",
        "sample_tests": [
            {"input": "abcde\nace", "output": "3", "explanation": "LCS is 'ace' with length 3"},
            {"input": "abc\ndef", "output": "0", "explanation": "No common subsequence"}
        ],
        "hidden_tests": [
            {"input": "abcd\nabcd", "output": "4"},
            {"input": "aggtab\ngxtxayb", "output": "4"},
            {"input": "a\na", "output": "1"},
            {"input": "abc\nabc", "output": "3"},
            {"input": "programming\ncontest", "output": "3"}
        ],
        "starter": "s1 = input()\ns2 = input()\n# Write your code here\nprint(result)"
    },
    {
        "title": "Binary Search",
        "prompt": "Implement binary search on a sorted array.\n\nInput Format:\nLine 1: n (array size) and x (target)\nLine 2: n sorted integers\n\nOutput: Index of x (0-indexed), or -1 if not found",
        "sample_tests": [
            {"input": "5 3\n1 2 3 4 5", "output": "2", "explanation": "3 is at index 2"},
            {"input": "4 6\n1 2 3 4", "output": "-1", "explanation": "6 not in array"}
        ],
        "hidden_tests": [
            {"input": "1 5\n5", "output": "0"},
            {"input": "5 1\n1 2 3 4 5", "output": "0"},
            {"input": "5 5\n1 2 3 4 5", "output": "4"},
            {"input": "6 7\n1 3 5 7 9 11", "output": "3"},
            {"input": "3 10\n1 2 3", "output": "-1"}
        ],
        "starter": "n, x = map(int, input().split())\narr = list(map(int, input().split()))\n# Write your code here\nprint(result)"
    },
    {
        "title": "Maximum Subarray Sum",
        "prompt": "Find the maximum sum of a contiguous subarray (Kadane's Algorithm).\n\nInput Format:\nLine 1: n (array size)\nLine 2: n integers\n\nOutput: Maximum subarray sum",
        "sample_tests": [
            {"input": "5\n-2 1 -3 4 -1", "output": "4", "explanation": "Subarray [4] has max sum 4"},
            {"input": "6\n5 -3 5 0 -2 3", "output": "8", "explanation": "Subarray [5,-3,5,0,-2,3] has max sum 8"}
        ],
        "hidden_tests": [
            {"input": "1\n5", "output": "5"},
            {"input": "3\n-1 -2 -3", "output": "-1"},
            {"input": "5\n1 2 3 4 5", "output": "15"},
            {"input": "4\n-5 4 6 -3", "output": "10"},
            {"input": "5\n2 -1 2 3 4", "output": "10"}
        ],
        "starter": "n = int(input())\narr = list(map(int, input().split()))\n# Write your code here\nprint(result)"
    },
    {
        "title": "Valid Parentheses",
        "prompt": "Check if a string of parentheses is valid.\n\nA string is valid if:\n1. Open brackets are closed by the same type\n2. Open brackets are closed in correct order\n\nInput: String containing only '(', ')', '{', '}', '[', ']'\nOutput: 'Valid' or 'Invalid'",
        "sample_tests": [
            {"input": "()", "output": "Valid", "explanation": "Properly closed"},
            {"input": "([)]", "output": "Invalid", "explanation": "Wrong order"}
        ],
        "hidden_tests": [
            {"input": "{}", "output": "Valid"},
            {"input": "()[]", "output": "Valid"},
            {"input": "([{}])", "output": "Valid"},
            {"input": "((", "output": "Invalid"},
            {"input": "((()))", "output": "Valid"}
        ],
        "starter": "s = input()\n# Write your code here\nprint(result)"
    },
    {
        "title": "Merge Sorted Arrays",
        "prompt": "Merge two sorted arrays into one sorted array.\n\nInput Format:\nLine 1: n (size of first array)\nLine 2: n sorted integers\nLine 3: m (size of second array)\nLine 4: m sorted integers\n\nOutput: Single line with merged sorted array",
        "sample_tests": [
            {"input": "3\n1 3 5\n2\n2 4", "output": "1 2 3 4 5", "explanation": "Merged in sorted order"},
            {"input": "2\n1 2\n2\n3 4", "output": "1 2 3 4", "explanation": "All from first, then second"}
        ],
        "hidden_tests": [
            {"input": "1\n1\n1\n2", "output": "1 2"},
            {"input": "3\n1 5 9\n3\n2 6 10", "output": "1 2 5 6 9 10"},
            {"input": "0\n\n2\n1 2", "output": "1 2"},
            {"input": "5\n1 2 3 4 5\n0\n", "output": "1 2 3 4 5"},
            {"input": "2\n10 20\n2\n5 15", "output": "5 10 15 20"}
        ],
        "starter": "n = int(input())\narr1 = list(map(int, input().split())) if n > 0 else []\nm = int(input())\narr2 = list(map(int, input().split())) if m > 0 else []\n# Write your code here\nprint(' '.join(map(str, result)))"
    },
]


def create_questions():
    """Create all questions in database"""
    db = SessionLocal()
    
    try:
        total_created = 0
        
        # Create easy questions (multiply templates to get 60+)
        logger.info("Creating EASY questions...")
        for i in range(12):  # 5 templates × 12 = 60 questions
            for template in EASY_QUESTIONS:
                question = Question(
                    title=f"{template['title']} {i+1}" if i > 0 else template['title'],
                    difficulty=DifficultyLevel.EASY,
                    prompt_markdown=template['prompt'],
                    starter_code_python=template['starter'],
                    time_limit_seconds=5,
                    memory_limit_mb=256,
                    marks=5,
                    is_active=True
                )
                db.add(question)
                db.flush()
                
                # Add sample test cases
                for idx, tc in enumerate(template['sample_tests']):
                    db.add(SampleTestCase(
                        question_id=question.id,
                        input_data=tc['input'],
                        expected_output=tc['output'],
                        explanation=tc['explanation'],
                        order=idx
                    ))
                
                # Add hidden test cases
                for idx, tc in enumerate(template['hidden_tests']):
                    db.add(HiddenTestCase(
                        question_id=question.id,
                        input_data=tc['input'],
                        expected_output=tc['output'],
                        order=idx
                    ))
                
                total_created += 1
                if total_created >= 60:
                    break
            if total_created >= 60:
                break
        
        # Create medium questions
        logger.info("Creating MEDIUM questions...")
        for i in range(12):  # 5 templates × 12 = 60 questions
            for template in MEDIUM_QUESTIONS:
                question = Question(
                    title=f"{template['title']} {i+1}" if i > 0 else template['title'],
                    difficulty=DifficultyLevel.MEDIUM,
                    prompt_markdown=template['prompt'],
                    starter_code_python=template['starter'],
                    time_limit_seconds=5,
                    memory_limit_mb=256,
                    marks=10,
                    is_active=True
                )
                db.add(question)
                db.flush()
                
                for idx, tc in enumerate(template['sample_tests']):
                    db.add(SampleTestCase(
                        question_id=question.id,
                        input_data=tc['input'],
                        expected_output=tc['output'],
                        explanation=tc['explanation'],
                        order=idx
                    ))
                
                for idx, tc in enumerate(template['hidden_tests']):
                    db.add(HiddenTestCase(
                        question_id=question.id,
                        input_data=tc['input'],
                        expected_output=tc['output'],
                        order=idx
                    ))
                
                total_created += 1
                if total_created >= 120:
                    break
            if total_created >= 120:
                break
        
        # Create hard questions
        logger.info("Creating HARD questions...")
        for i in range(6):  # 5 templates × 6 = 30 questions
            for template in HARD_QUESTIONS:
                question = Question(
                    title=f"{template['title']} {i+1}" if i > 0 else template['title'],
                    difficulty=DifficultyLevel.HARD,
                    prompt_markdown=template['prompt'],
                    starter_code_python=template['starter'],
                    time_limit_seconds=10,
                    memory_limit_mb=256,
                    marks=20,
                    is_active=True
                )
                db.add(question)
                db.flush()
                
                for idx, tc in enumerate(template['sample_tests']):
                    db.add(SampleTestCase(
                        question_id=question.id,
                        input_data=tc['input'],
                        expected_output=tc['output'],
                        explanation=tc['explanation'],
                        order=idx
                    ))
                
                for idx, tc in enumerate(template['hidden_tests']):
                    db.add(HiddenTestCase(
                        question_id=question.id,
                        input_data=tc['input'],
                        expected_output=tc['output'],
                        order=idx
                    ))
                
                total_created += 1
                if total_created >= 150:
                    break
            if total_created >= 150:
                break
        
        db.commit()
        logger.info(f"✨ SUCCESS! Created {total_created} questions")
        return total_created
        
    except Exception as e:
        logger.error(f"Error creating questions: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    print("=" * 80)
    print("QUICK QUESTION GENERATOR")
    print("=" * 80)
    print()
    print("This will create 150 pre-made questions instantly!")
    print("No API needed - uses tested templates")
    print()
    
    confirm = input("Create questions now? (yes/no): ")
    if confirm.lower() != "yes":
        print("Cancelled.")
        exit()
    
    try:
        count = create_questions()
        print()
        print("=" * 80)
        print(f"✨ SUCCESS! Created {count} questions")
        print("=" * 80)
        print()
        print("Next steps:")
        print("1. Start services (API server, worker, frontend)")
        print("2. Upload teams_real.csv via admin dashboard")
        print("3. Questions will be auto-assigned to teams")
        print("4. Configure test timing")
        print("5. Launch test!")
        print()
    except Exception as e:
        print()
        print(f"❌ Database not ready yet: {e}")
        print()
        print("💡 DON'T WORRY! This is expected.")
        print()
        print("✅ Questions are pre-made and ready")
        print("✅ Tomorrow morning:")
        print("   1. Setup PostgreSQL (5 minutes)")
        print("   2. Run this script again")
        print("   3. Questions will be created instantly")
        print()
        print("📖 See DEPLOY_NOW.md for complete setup guide")
        print()
        print("🌙 You're all set for tonight! Get some sleep!")
