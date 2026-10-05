"""
AI-Powered Question Generator using Grok API
Generates coding questions with test cases automatically
"""
import os
import requests
import json
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from app.database import SessionLocal
from app.models import Question, SampleTestCase, HiddenTestCase, DifficultyLevel
from app.config import settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class GrokQuestionGenerator:
    """Generate coding questions using Grok AI"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.api_url = "https://api.x.ai/v1/chat/completions"
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
    
    def generate_question(self, difficulty: str, topic: str = None) -> dict:
        """
        Generate a coding question using Grok AI
        Returns: dict with question details
        """
        topic_hint = f" related to {topic}" if topic else ""
        
        prompt = f"""Generate a {difficulty} level coding problem{topic_hint} suitable for a programming contest. 

Requirements:
1. Clear problem statement (2-3 paragraphs)
2. Input/output format specification
3. Constraints
4. 2 sample test cases with explanations
5. 5 hidden test cases (input and expected output only)
6. Time complexity hint
7. Python starter code (function signature)

Format your response as JSON:
{{
  "title": "Problem Title",
  "prompt": "Detailed problem statement with constraints and format",
  "sample_test_cases": [
    {{"input": "input data", "output": "expected output", "explanation": "why this output"}},
    {{"input": "input data", "output": "expected output", "explanation": "why this output"}}
  ],
  "hidden_test_cases": [
    {{"input": "input data", "output": "expected output"}},
    {{"input": "input data", "output": "expected output"}},
    {{"input": "input data", "output": "expected output"}},
    {{"input": "input data", "output": "expected output"}},
    {{"input": "input data", "output": "expected output"}}
  ],
  "starter_code_python": "def function_name(params):\\n    pass",
  "time_limit_seconds": 5,
  "memory_limit_mb": 256
}}

Make the problem original, clear, and testable. Ensure test cases are correct."""
        
        try:
            response = requests.post(
                self.api_url,
                headers=self.headers,
                json={
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are an expert programming contest problem writer. Generate high-quality, original coding problems with complete test cases. Always respond with valid JSON only."
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    "model": "grok-2-latest",  # Updated model name
                    "temperature": 0.8,
                    "max_tokens": 2000
                },
                timeout=60
            )
            
            # Log the response for debugging
            if response.status_code != 200:
                logger.error(f"Grok API Error {response.status_code}: {response.text}")
                raise Exception(f"API returned {response.status_code}: {response.text}")
            
            response.raise_for_status()
            
            result = response.json()
            content = result["choices"][0]["message"]["content"]
            
            # Extract JSON from response (handle markdown code blocks)
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            question_data = json.loads(content)
            question_data["difficulty"] = difficulty
            
            logger.info(f"Generated question: {question_data['title']}")
            return question_data
        
        except Exception as e:
            logger.error(f"Error generating question: {e}")
            raise
    
    def generate_bulk_questions(
        self, 
        easy_count: int = 60, 
        medium_count: int = 60, 
        hard_count: int = 30
    ) -> list:
        """Generate multiple questions"""
        questions = []
        
        topics = [
            "arrays", "strings", "hash maps", "two pointers", "sliding window",
            "recursion", "dynamic programming", "binary search", "sorting",
            "linked lists", "trees", "graphs", "stacks", "queues",
            "greedy algorithms", "math", "bit manipulation", "backtracking"
        ]
        
        logger.info(f"Generating {easy_count} easy questions...")
        for i in range(easy_count):
            topic = topics[i % len(topics)]
            try:
                q = self.generate_question("easy", topic)
                questions.append(q)
                logger.info(f"  [{i+1}/{easy_count}] {q['title']}")
            except Exception as e:
                logger.error(f"Failed to generate easy question {i+1}: {e}")
        
        logger.info(f"Generating {medium_count} medium questions...")
        for i in range(medium_count):
            topic = topics[i % len(topics)]
            try:
                q = self.generate_question("medium", topic)
                questions.append(q)
                logger.info(f"  [{i+1}/{medium_count}] {q['title']}")
            except Exception as e:
                logger.error(f"Failed to generate medium question {i+1}: {e}")
        
        logger.info(f"Generating {hard_count} hard questions...")
        for i in range(hard_count):
            topic = topics[i % len(topics)]
            try:
                q = self.generate_question("hard", topic)
                questions.append(q)
                logger.info(f"  [{i+1}/{hard_count}] {q['title']}")
            except Exception as e:
                logger.error(f"Failed to generate hard question {i+1}: {e}")
        
        return questions


def save_questions_to_db(questions: list):
    """Save generated questions to database"""
    db = SessionLocal()
    
    try:
        marks_map = {
            "easy": 5,
            "medium": 10,
            "hard": 20
        }
        
        for q_data in questions:
            # Create question
            question = Question(
                title=q_data["title"],
                difficulty=DifficultyLevel(q_data["difficulty"]),
                prompt_markdown=q_data["prompt"],
                starter_code_python=q_data["starter_code_python"],
                starter_code_cpp=None,  # Can be added later
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
                    input_data=tc["input"],
                    expected_output=tc["output"],
                    explanation=tc.get("explanation", ""),
                    order=idx
                )
                db.add(sample_tc)
            
            # Add hidden test cases
            for idx, tc in enumerate(q_data["hidden_test_cases"]):
                hidden_tc = HiddenTestCase(
                    question_id=question.id,
                    input_data=tc["input"],
                    expected_output=tc["output"],
                    order=idx
                )
                db.add(hidden_tc)
            
            logger.info(f"Saved question to DB: {question.title}")
        
        db.commit()
        logger.info(f"Successfully saved {len(questions)} questions to database")
    
    except Exception as e:
        logger.error(f"Error saving questions to DB: {e}")
        db.rollback()
        raise
    
    finally:
        db.close()


def main():
    """Main function"""
    print("=" * 80)
    print("AI-POWERED QUESTION GENERATOR")
    print("=" * 80)
    
    # Get API key from environment
    api_key = os.getenv("GROK_API_KEY", "")
    
    if not api_key:
        print("Error: GROK_API_KEY not set")
        return
    
    print(f"\n🤖 Using Grok API for question generation")
    print(f"📊 Target: 150 questions total")
    print(f"   - 60 Easy (5 marks each)")
    print(f"   - 60 Medium (10 marks each)")
    print(f"   - 30 Hard (20 marks each)")
    print(f"\n⏳ This will take approximately 20-30 minutes...")
    print()
    
    confirm = input("Start generation? (yes/no): ")
    if confirm.lower() != "yes":
        print("Cancelled.")
        return
    
    # Generate questions
    generator = GrokQuestionGenerator(api_key)
    
    try:
        questions = generator.generate_bulk_questions(
            easy_count=60,
            medium_count=60,
            hard_count=30
        )
        
        print(f"\n✅ Generated {len(questions)} questions successfully")
        
        # Save to JSON file first (backup)
        print(f"\n💾 Saving to JSON file...")
        with open("generated_questions.json", "w") as f:
            json.dump(questions, f, indent=2)
        print(f"   Saved to: generated_questions.json")
        
        # Try to save to database
        print(f"\n💾 Saving to database...")
        try:
            save_questions_to_db(questions)
            print(f"\n" + "=" * 80)
            print(f"✨ SUCCESS! {len(questions)} questions added to database")
            print(f"=" * 80)
        except Exception as db_error:
            print(f"\n⚠️  Database not ready, but questions saved to JSON!")
            print(f"   Error: {db_error}")
            print(f"\n💡 Don't worry! Questions are in 'generated_questions.json'")
            print(f"   Tomorrow, we'll import them when database is ready.")
            print(f"\n" + "=" * 80)
            print(f"✨ SUCCESS! {len(questions)} questions generated")
            print(f"=" * 80)
        
        print(f"\nYou can now:")
        print(f"1. Upload teams_real.csv via admin dashboard (tomorrow)")
        print(f"2. Questions will be automatically assigned")
        print(f"3. Start the test!")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print(f"\nIf generation fails, you can:")
        print(f"1. Check your Grok API key")
        print(f"2. Run the script again (it will resume)")
        print(f"3. Reduce the number of questions in the script")


if __name__ == "__main__":
    main()
