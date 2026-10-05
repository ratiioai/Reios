"""
Test code execution using Grok API for validation
Alternative/supplement to Piston API
"""
import os
import requests
import json
import subprocess
import tempfile
import sys
from typing import Dict, Any


class GrokCodeTester:
    """
    Test and validate code using Grok API
    Can analyze code, suggest fixes, and validate logic
    """
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        self.api_url = "https://api.x.ai/v1/chat/completions"
    
    def analyze_code(self, code: str, language: str = "python") -> Dict[str, Any]:
        """
        Analyze code for syntax errors, logic issues, and potential improvements
        """
        prompt = f"""Analyze this {language} code for errors and issues:

```{language}
{code}
```

Return JSON with:
{{
    "has_syntax_errors": boolean,
    "syntax_errors": ["list of syntax errors"],
    "has_logic_errors": boolean,
    "logic_errors": ["list of potential logic errors"],
    "suggestions": ["list of improvements"],
    "complexity": "O(n) time, O(1) space"
}}
"""
        
        payload = {
            "messages": [
                {
                    "role": "system",
                    "content": "You are a code analyzer. Return only valid JSON."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "model": "grok-beta",
            "stream": False,
            "temperature": 0.3
        }
        
        try:
            response = requests.post(self.api_url, headers=self.headers, json=payload, timeout=20)
            
            if response.status_code != 200:
                return {"error": f"API error: {response.status_code}"}
            
            content = response.json()["choices"][0]["message"]["content"]
            
            # Clean and parse JSON
            content = content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            
            return json.loads(content.strip())
        
        except Exception as e:
            return {"error": str(e)}
    
    def validate_solution(
        self, 
        code: str, 
        test_input: str, 
        expected_output: str,
        language: str = "python"
    ) -> Dict[str, Any]:
        """
        Validate if code produces expected output for given input
        Uses Grok to predict behavior and local execution to verify
        """
        # First, ask Grok to predict the output
        prompt = f"""Given this {language} code:

```{language}
{code}
```

And this input:
```
{test_input}
```

What will be the output? Reply with ONLY the exact output, nothing else."""
        
        payload = {
            "messages": [
                {
                    "role": "system",
                    "content": "You are a code execution simulator. Provide only the exact output."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "model": "grok-beta",
            "stream": False,
            "temperature": 0.1
        }
        
        try:
            # Grok prediction
            response = requests.post(self.api_url, headers=self.headers, json=payload, timeout=20)
            predicted_output = response.json()["choices"][0]["message"]["content"].strip()
            
            # Local execution (safer for simple code)
            actual_output = self._execute_locally(code, test_input, language)
            
            return {
                "predicted_output": predicted_output,
                "actual_output": actual_output,
                "expected_output": expected_output,
                "prediction_matches": predicted_output.strip() == expected_output.strip(),
                "execution_matches": actual_output.strip() == expected_output.strip(),
                "passed": actual_output.strip() == expected_output.strip()
            }
        
        except Exception as e:
            return {"error": str(e), "passed": False}
    
    def _execute_locally(self, code: str, test_input: str, language: str) -> str:
        """
        Execute code locally in a temporary file
        SECURITY WARNING: Only use for trusted code in development!
        """
        if language.lower() != "python":
            return "Local execution only supports Python"
        
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(code)
                f.write("\n")
                temp_file = f.name
            
            result = subprocess.run(
                [sys.executable, temp_file],
                input=test_input,
                capture_output=True,
                text=True,
                timeout=5
            )
            
            os.unlink(temp_file)
            
            if result.returncode != 0:
                return f"Error: {result.stderr}"
            
            return result.stdout.strip()
        
        except subprocess.TimeoutExpired:
            return "Error: Execution timeout"
        except Exception as e:
            return f"Error: {str(e)}"
    
    def generate_test_cases(self, question_prompt: str, difficulty: str = "easy") -> Dict:
        """
        Generate additional test cases for a question
        """
        prompt = f"""Generate test cases for this {difficulty} coding problem:

{question_prompt}

Return JSON with:
{{
    "test_cases": [
        {{
            "input_data": "test input",
            "expected_output": "expected output",
            "explanation": "why this test is important"
        }}
    ]
}}

Generate 3-5 diverse test cases covering edge cases."""
        
        payload = {
            "messages": [
                {
                    "role": "system",
                    "content": "You are a test case generator. Return only valid JSON."
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
            response = requests.post(self.api_url, headers=self.headers, json=payload, timeout=20)
            content = response.json()["choices"][0]["message"]["content"]
            
            # Clean and parse
            content = content.strip()
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            
            return json.loads(content.strip())
        
        except Exception as e:
            return {"error": str(e)}


def interactive_testing():
    """Interactive code testing session"""
    api_key = os.getenv("GROK_API_KEY")
    if not api_key:
        print("❌ GROK_API_KEY not found in environment")
        return
    
    tester = GrokCodeTester(api_key)
    
    print("=" * 70)
    print("  GROK CODE TESTER - Interactive Mode")
    print("=" * 70)
    
    while True:
        print("\nOptions:")
        print("1. Analyze code")
        print("2. Validate solution")
        print("3. Generate test cases")
        print("4. Exit")
        
        choice = input("\nChoice (1-4): ").strip()
        
        if choice == "1":
            print("\nPaste your Python code (type 'END' on a new line to finish):")
            lines = []
            while True:
                line = input()
                if line.strip() == "END":
                    break
                lines.append(line)
            
            code = "\n".join(lines)
            print("\n🔍 Analyzing code...")
            result = tester.analyze_code(code)
            print(json.dumps(result, indent=2))
        
        elif choice == "2":
            print("\nPaste your Python code (type 'END' on a new line to finish):")
            lines = []
            while True:
                line = input()
                if line.strip() == "END":
                    break
                lines.append(line)
            
            code = "\n".join(lines)
            test_input = input("\nTest input: ")
            expected = input("Expected output: ")
            
            print("\n🧪 Testing solution...")
            result = tester.validate_solution(code, test_input, expected)
            print(json.dumps(result, indent=2))
        
        elif choice == "3":
            print("\nPaste question prompt:")
            prompt = input()
            difficulty = input("Difficulty (easy/medium/hard): ").lower() or "easy"
            
            print("\n🎲 Generating test cases...")
            result = tester.generate_test_cases(prompt, difficulty)
            print(json.dumps(result, indent=2))
        
        elif choice == "4":
            print("\nGoodbye!")
            break


if __name__ == "__main__":
    interactive_testing()
