"""
Generate coding questions using Grok API
Automatically creates 200+ questions with test cases
"""
import os
import requests
import json
from typing import List, Dict
from app.database import SessionLocal
from app.models import Question, SampleTestCase, HiddenTestCase, DifficultyLevel
from sqlalchemy.orm import Session

# Grok API Configuration
GROK_API_KEY = os.getenv("GROK_API_KEY", "")  # Set in .env file
GROK_API_URL = "https://api.x.ai/v1/chat/completions"


class GrokQuestionGenerator:
    """Generate coding questions using Grok AI"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
    
    def generate_question(self, difficulty: str, topic: str) -> Dict:
        """
        Generate a single coding question using Grok
        
        Args:
            difficulty: 'easy', 'medium', or 'hard'
            topic: Programming topic (e.g., 'arrays', 'strings', 'recursion')
        
        Returns:
            Dictionary with question details
        """
        prompt = f"""Generate a {difficulty} level coding question about {topic}.

Return ONLY a valid JSON object with this exact structure (no markdown, no explanation):
{{
    "title": "Question title (max 100 chars)",
    "prompt_markdown": "Detailed problem description with examples",
    "starter_code_python": "def solution():\\n    pass",
    "time_limit_seconds": 5,
    "memory_limit_mb": 256,
    "sample_test_cases": [
        {{
            "input_data": "sample input",
            "expected_output": "sample output",
            "explanation": "why this is correct"
        }}
    ],
    "hidden_test_cases": [
        {{
            "input_data": "test input 1",
            "expected_output": "test output 1"
        }},
        {{
            "input_data": "test input 2",
            "expected_output": "test output 2"
        }}
    ]
}}

Requirements:
- {difficulty} difficulty appropriate for competitive programming
- Clear problem statement with constraints
- At least 1 sample test case with explanation
- At least 2 hidden test cases for validation
- Python starter code with function signature
- Input/output should be simple strings (one per line if multiple values)
"""
        
        payload = {
            "messages": [
                {
                    "role": "system",
                    "content": "You are an expert competitive programming problem setter. Generate valid JSON only, no markdown formatting."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "model": "grok-beta",
            "stream": False,
            "temperature": 0.7
        }
        
        try:
            response = requests.post(
                GROK_API_URL,
                headers=self.headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code != 200:
                print(f"Grok API error: {response.status_code} - {response.text}")
                return None
            
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            
            # Clean up markdown if present
            content = content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
            
            # Parse JSON
            question_data = json.loads(content)
            question_data["difficulty"] = difficulty
            question_data["topic"] = topic
            
            return question_data
        
        except Exception as e:
            print(f"Error generating question: {e}")
            return None
    
    def generate_multiple_questions(
        self, 
        easy_count: int = 80,
        medium_count: int = 80,
        hard_count: int = 40
    ) -> List[Dict]:
        """
        Generate multiple questions across difficulties
        
        Default: 200 questions total (80 easy, 80 medium, 40 hard)
        Ensures 175 teams get unique sets
        """
        topics = [
            "arrays", "strings", "sorting", "searching", "linked lists",
            "stacks", "queues", "trees", "graphs", "dynamic programming",
            "recursion", "backtracking", "greedy algorithms", "math",
            "bit manipulation", "hash tables", "two pointers", "sliding window"
        ]
        
        questions = []
        
        # Generate easy questions
        print(f"\n🟢 Generating {easy_count} EASY questions...")
        for i in range(easy_count):
            topic = topics[i % len(topics)]
            print(f"  [{i+1}/{easy_count}] Topic: {topic}")
            
            question = self.generate_question("easy", topic)
            if question:
                questions.append(question)
            else:
                print(f"  ❌ Failed to generate question {i+1}")
        
        # Generate medium questions
        print(f"\n🟡 Generating {medium_count} MEDIUM questions...")
        for i in range(medium_count):
            topic = topics[i % len(topics)]
            print(f"  [{i+1}/{medium_count}] Topic: {topic}")
            
            question = self.generate_question("medium", topic)
            if question:
                questions.append(question)
            else:
                print(f"  ❌ Failed to generate question {i+1}")
        
        # Generate hard questions
        print(f"\n🔴 Generating {hard_count} HARD questions...")
        for i in range(hard_count):
            topic = topics[i % len(topics)]
            print(f"  [{i+1}/{hard_count}] Topic: {topic}")
            
            question = self.generate_question("hard", topic)
            if question:
                questions.append(question)
            else:
                print(f"  ❌ Failed to generate question {i+1}")
        
        return questions


def save_questions_to_database(questions: List[Dict], db: Session):
    """
    Save generated questions to database
    """
    marks_map = {
        "easy": 5,
        "medium": 10,
        "hard": 20
    }
    
    saved_count = 0
    
    for q_data in questions:
        try:
            # Create question
            question = Question(
                title=q_data["title"],
                difficulty=DifficultyLevel(q_data["difficulty"]),
                prompt_markdown=q_data["prompt_markdown"],
                starter_code_python=q_data["starter_code_python"],
                starter_code_cpp=None,  # Can extend later
                starter_code_java=None,
                starter_code_javascript=None,
                time_limit_seconds=q_data.get("time_limit_seconds", 5),
                memory_limit_mb=q_data.get("memory_limit_mb", 256),
                marks=marks_map[q_data["difficulty"]],
                is_active=True
            )
            
            db.add(question)
            db.flush()  # Get question.id
            
            # Add sample test cases
            for idx, tc in enumerate(q_data["sample_test_cases"]):
                sample_tc = SampleTestCase(
                    question_id=question.id,
                    input_data=tc["input_data"],
                    expected_output=tc["expected_output"],
                    explanation=tc.get("explanation", ""),
                    order=idx
                )
                db.add(sample_tc)
            
            # Add hidden test cases
            for idx, tc in enumerate(q_data["hidden_test_cases"]):
                hidden_tc = HiddenTestCase(
                    question_id=question.id,
                    input_data=tc["input_data"],
                    expected_output=tc["expected_output"],
                    order=idx
                )
                db.add(hidden_tc)
            
            db.commit()
            saved_count += 1
            print(f"✅ Saved: {question.title} ({question.difficulty.value})")
        
        except Exception as e:
            print(f"❌ Error saving question '{q_data.get('title', 'Unknown')}': {e}")
            db.rollback()
    
    return saved_count


def main():
    """Main execution"""
    print("=" * 70)
    print("  GROK-POWERED QUESTION GENERATOR")
    print("=" * 70)
    
    # Check API key
    api_key = os.getenv("GROK_API_KEY")
    if not api_key:
        print("\n❌ ERROR: GROK_API_KEY not found in environment variables!")
        print("\nPlease add to your .env file:")
        print("GROK_API_KEY=your_api_key_here")
        return
    
    print(f"\n✅ API Key found: {api_key[:10]}...")
    
    # Ask user for quantity
    print("\n📊 How many questions do you want to generate?")
    print("   Recommended: 200+ (80 easy, 80 medium, 40 hard)")
    print("   Minimum: 175 for unique sets across all teams")
    
    try:
        easy = int(input("\nEasy questions (default 80): ") or "80")
        medium = int(input("Medium questions (default 80): ") or "80")
        hard = int(input("Hard questions (default 40): ") or "40")
    except ValueError:
        print("Invalid input, using defaults...")
        easy, medium, hard = 80, 80, 40
    
    total = easy + medium + hard
    print(f"\n🎯 Generating {total} questions ({easy} easy, {medium} medium, {hard} hard)")
    print("⏱️  This will take approximately {:.1f} minutes...".format(total * 5 / 60))
    
    confirm = input("\nContinue? (yes/no): ").lower()
    if confirm != "yes":
        print("Cancelled.")
        return
    
    # Generate questions
    generator = GrokQuestionGenerator(api_key)
    questions = generator.generate_multiple_questions(easy, medium, hard)
    
    print(f"\n✅ Successfully generated {len(questions)}/{total} questions")
    
    if len(questions) == 0:
        print("❌ No questions generated. Check your API key and network connection.")
        return
    
    # Save to database
    print("\n💾 Saving questions to database...")
    db = SessionLocal()
    try:
        saved = save_questions_to_database(questions, db)
        print(f"\n✅ Saved {saved} questions to database!")
        
        # Show summary
        from sqlalchemy import func
        counts = db.query(
            Question.difficulty,
            func.count(Question.id)
        ).filter(
            Question.is_active == True
        ).group_by(Question.difficulty).all()
        
        print("\n📊 Question Bank Summary:")
        print("-" * 40)
        for difficulty, count in counts:
            print(f"  {difficulty.value.upper():8} : {count} questions")
        print("-" * 40)
        
        total_in_db = sum(count for _, count in counts)
        print(f"  TOTAL   : {total_in_db} questions")
        
        if total_in_db >= 175:
            print("\n✅ You have enough questions for 175 unique team sets!")
        else:
            print(f"\n⚠️  WARNING: Need {175 - total_in_db} more questions for full uniqueness")
    
    finally:
        db.close()
    
    print("\n" + "=" * 70)
    print("  DONE! Questions ready for tomorrow's test.")
    print("=" * 70)


if __name__ == "__main__":
    main()
