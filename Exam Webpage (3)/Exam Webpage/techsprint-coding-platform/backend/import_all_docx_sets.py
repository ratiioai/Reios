"""
Import all 14 SET Docx Files into Coding Test Platform
Maps 25 questions per set to all 175 registered teams (1 set per ~11 teams).
"""
import os
import sys
import glob
import re
import hashlib
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

# Add backend directory to path
sys.path.insert(0, os.path.dirname(__file__))

from app.database import SessionLocal, engine
from app.models import (
    Base, Question, SampleTestCase, HiddenTestCase,
    Team, TeamQuestionAssignment, UsedQuestionSet,
    DifficultyLevel
)

Base.metadata.create_all(bind=engine)

def extract_docx_paragraphs(docx_path):
    """Extract all text paragraphs from docx file."""
    z = zipfile.ZipFile(docx_path)
    tree = ET.fromstring(z.read('word/document.xml'))
    paras = []
    for p in tree.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p'):
        t = ''.join(p.itertext()).strip()
        if t:
            paras.append(t)
    return paras

def parse_set_file(docx_path):
    """Parse a SET docx file into a list of 25 question dicts."""
    paras = extract_docx_paragraphs(docx_path)
    questions = []
    
    q_dict = {}
    current_q_num = None
    current_part = "PART-A"
    
    for p in paras:
        if "PART-A" in p.upper():
            current_part = "PART-A"
            continue
        elif "PART-B" in p.upper():
            current_part = "PART-B"
            continue
        elif "PART-C" in p.upper():
            current_part = "PART-C"
            continue
            
        m = re.match(r'^(\d+)\.\s*(.*)', p)
        if m and 1 <= int(m.group(1)) <= 25:
            current_q_num = int(m.group(1))
            q_dict[current_q_num] = {
                "num": current_q_num,
                "part": current_part,
                "lines": [m.group(2).strip()]
            }
        elif current_q_num is not None:
            q_dict[current_q_num]["lines"].append(p.strip())
            
    # Process each question into structured data
    for num in sorted(q_dict.keys()):
        item = q_dict[num]
        full_text = " ".join(item["lines"])
        first_line = item["lines"][0]
        
        # Determine title and prompt
        split_idx = -1
        keywords = ['Given', 'Write', 'Print', 'Implement', 'Find', 'Count', 'Check', 'Determine', 'Calculate', 'Produce', 'Read', 'A ']
        for kw in keywords:
            idx = first_line.find(kw)
            if idx > 3 and (split_idx == -1 or idx < split_idx):
                split_idx = idx
                
        if split_idx != -1:
            title = first_line[:split_idx].strip()
            prompt = first_line[split_idx:].strip()
            if len(item["lines"]) > 1:
                prompt += "\n\n" + "\n\n".join(item["lines"][1:])
        else:
            title = first_line
            prompt = full_text

        # Determine difficulty and marks
        if item["part"] == "PART-A" or num <= 10:
            difficulty = DifficultyLevel.EASY
            marks = 1
        elif item["part"] == "PART-B" or num <= 20:
            difficulty = DifficultyLevel.MEDIUM
            marks = 2
        else:
            difficulty = DifficultyLevel.HARD
            marks = 4
            
        questions.append({
            "num": num,
            "part": item["part"],
            "title": title,
            "prompt": prompt,
            "difficulty": difficulty,
            "marks": marks
        })
        
    return questions

def generate_starter_code():
    return {
        "python": "# Read input from standard input and print output\nimport sys\n\ndef solve():\n    # Write your solution here\n    pass\n\nif __name__ == '__main__':\n    solve()\n",
        "cpp": "#include <iostream>\n#include <vector>\n#include <string>\n#include <algorithm>\n\nusing namespace std;\n\nint main() {\n    // Write your solution here\n    return 0;\n}\n",
        "java": "import java.util.Scanner;\n\npublic class Solution {\n    public static void main(String[] args) {\n        Scanner sc = new Scanner(System.in);\n        // Write your solution here\n    }\n}\n",
        "javascript": "const fs = require('fs');\n\nfunction solve() {\n    const input = fs.readFileSync(0, 'utf-8').trim();\n    // Write your solution here\n}\n\nsolve();\n"
    }

def import_all_sets():
    db = SessionLocal()
    try:
        set_files = [
            'SET1.docx', 'SET2.docx', 'SET3.docx', 'SET4.docx',
            'SET5.docx', 'SET6.docx', 'SET7.docx', 'SET8.docx',
            'SET10.docx', 'SET11.docx', 'SET12.docx', 'SET13.docx',
            'SET14.docx', 'SET15.docx'
        ]
        
        # Check files in parent or current dir
        found_files = []
        for sf in set_files:
            if os.path.exists(sf):
                found_files.append(sf)
            elif os.path.exists(os.path.join("..", sf)):
                found_files.append(os.path.join("..", sf))
            elif os.path.exists(os.path.join("c:\\Exam Webpage", sf)):
                found_files.append(os.path.join("c:\\Exam Webpage", sf))
                
        print(f"Found {len(found_files)} SET files to import.")
        
        # Clear existing question bank & assignments
        print("Clearing previous assignments and questions...")
        db.query(TeamQuestionAssignment).delete()
        db.query(UsedQuestionSet).delete()
        db.query(SampleTestCase).delete()
        db.query(HiddenTestCase).delete()
        db.query(Question).delete()
        db.commit()
        
        starters = generate_starter_code()
        
        set_question_map = {}
        total_questions_created = 0
        
        for file_path in found_files:
            set_name = Path(file_path).stem
            questions_data = parse_set_file(file_path)
            for q_info in questions_data:
                full_markdown = q_info['prompt'].strip()
                
                question = Question(
                    title=f"[{set_name}] {q_info['title']}",
                    difficulty=q_info['difficulty'],
                    prompt_markdown=full_markdown,
                    starter_code_python=starters['python'],
                    starter_code_cpp=starters['cpp'],
                    starter_code_java=starters['java'],
                    starter_code_javascript=starters['javascript'],
                    time_limit_seconds=2,
                    memory_limit_mb=256,
                    marks=q_info['marks'],
                    is_active=True
                )
                db.add(question)
                db.flush()
                
                # Sample test case
                sample_tc = SampleTestCase(
                    question_id=question.id,
                    input_data="0",
                    expected_output="0",
                    explanation="Sample input and expected output format.",
                    order=1
                )
                db.add(sample_tc)
                
                # Hidden test case for grading
                hidden_tc = HiddenTestCase(
                    question_id=question.id,
                    input_data="0",
                    expected_output="0",
                    order=1
                )
                db.add(hidden_tc)
                
                set_question_map[set_name].append(question)
                total_questions_created += 1
                
        db.commit()
        print(f"[OK] Successfully created {total_questions_created} questions in database across {len(set_question_map)} sets.")
        
        # Assign 1 set (25 questions) to each team
        teams = db.query(Team).order_by(Team.id).all()
        set_keys = list(set_question_map.keys())
        
        print(f"\nAssigning {len(set_keys)} sets across {len(teams)} teams (1 set per team)...")
        
        assigned_count = 0
        for idx, team in enumerate(teams):
            set_key = set_keys[idx % len(set_keys)]
            set_questions = set_question_map[set_key]
            
            q_ids = []
            for pos, q in enumerate(set_questions, start=1):
                assignment = TeamQuestionAssignment(
                    team_id=team.id,
                    question_id=q.id,
                    position=pos
                )
                db.add(assignment)
                q_ids.append(q.id)
                
            set_hash = hashlib.sha256(f"{team.id}_{set_key}".encode()).hexdigest()
            used_set = UsedQuestionSet(set_hash=set_hash, team_id=team.id)
            db.add(used_set)
            
            assigned_count += 1
            if (idx + 1) % 20 == 0 or idx == len(teams) - 1:
                print(f"  Assigned {idx + 1}/{len(teams)} teams (Latest: {team.team_name} -> {set_key})")
                
        db.commit()
        print(f"[SUCCESS] All {assigned_count} teams assigned their dedicated 25-question sets!")
        
    except Exception as e:
        print(f"[ERROR] Import failed: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    import_all_sets()
