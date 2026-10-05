"""
Load demo data for the Reios module: a college, a college admin, students, a global question bank
covering the standard Reios sections, and a live mock exam.

Usage (from the backend folder):
    python seed_demo.py

Safe to run more than once: it skips anything that already exists.
Demo logins are printed at the end. Change or delete them before real use.
"""
from datetime import timedelta

from app.auth import hash_password
from app.database import SessionLocal, create_tables
from app.reios.models import (
    CodingProblem, College, Exam, ExamItem, ItemType, MCQQuestion, QuestionSet, Role, SetAssignment, User,
)
from app.reios.security import utcnow

MCQS = [
    # (section, topic, difficulty, question, options, correct, explanation)
    ("Quantitative Aptitude", "Percentages", "easy", "What is 15% of 240?", ["32", "36", "38", "40"], [1], "240 × 0.15 = 36"),
    ("Quantitative Aptitude", "Profit & Loss", "medium", "An item bought for ₹800 is sold for ₹920. What is the profit percentage?", ["12%", "15%", "18%", "20%"], [1], "Profit 120; 120/800 = 15%"),
    ("Quantitative Aptitude", "Time & Work", "medium", "A can finish a job in 10 days and B in 15 days. Working together, how many days do they take?", ["5", "6", "7.5", "8"], [1], "1/10 + 1/15 = 1/6"),
    ("Quantitative Aptitude", "Speed & Distance", "easy", "A train covers 180 km in 3 hours. What is its speed in m/s?", ["15", "16.67", "18", "20"], [1], "60 km/h × 5/18 = 16.67 m/s"),
    ("Quantitative Aptitude", "Averages", "easy", "The average of 5 numbers is 20. If one number is removed the average becomes 18. Which number was removed?", ["24", "26", "28", "30"], [2], "100 − 72 = 28"),
    ("Quantitative Aptitude", "Simple Interest", "medium", "Simple interest on ₹5000 at 8% per annum for 3 years is:", ["₹1000", "₹1200", "₹1400", "₹1500"], [1], "5000 × 8 × 3 / 100"),
    ("Logical Reasoning", "Number Series", "easy", "Find the next number: 2, 6, 12, 20, 30, ?", ["38", "40", "42", "44"], [2], "Differences 4, 6, 8, 10, 12"),
    ("Logical Reasoning", "Coding-Decoding", "medium", "If CAT is coded as DBU, how is DOG coded?", ["EPH", "EPG", "FPH", "DPH"], [0], "Each letter +1"),
    ("Logical Reasoning", "Blood Relations", "medium", "Pointing to a man, Riya says, \"He is the son of my grandfather's only son.\" How is the man related to Riya?", ["Cousin", "Brother", "Uncle", "Father"], [1], "Grandfather's only son is her father; his son is her brother"),
    ("Logical Reasoning", "Direction Sense", "easy", "Ravi walks 5 km north, turns right and walks 3 km, then turns right and walks 5 km. How far is he from the start?", ["3 km", "5 km", "8 km", "13 km"], [0], "He ends 3 km east of the start"),
    ("Logical Reasoning", "Syllogism", "medium", "All roses are flowers. Some flowers fade quickly. Which conclusion definitely follows?", ["All roses fade quickly", "Some roses fade quickly", "No rose fades quickly", "None of these"], [3], "Nothing definite links roses to fading"),
    ("Verbal Ability", "Synonyms", "easy", "Choose the synonym of ABUNDANT.", ["Scarce", "Plentiful", "Rare", "Meagre"], [1], None),
    ("Verbal Ability", "Antonyms", "easy", "Choose the antonym of OBSCURE.", ["Vague", "Hidden", "Clear", "Dim"], [2], None),
    ("Verbal Ability", "Error Spotting", "medium", "Find the part with an error: (A) Each of the students / (B) have submitted / (C) their assignment / (D) on time.", ["A", "B", "C", "D"], [1], "'Each' takes a singular verb: has submitted"),
    ("Verbal Ability", "Fill in the blanks", "easy", "She is good ___ mathematics.", ["in", "at", "on", "with"], [1], None),
    ("Technical", "Data Structures", "easy", "Which data structure works on the LIFO principle?", ["Queue", "Stack", "Array", "Linked list"], [1], None),
    ("Technical", "Algorithms", "medium", "What is the worst-case time complexity of binary search?", ["O(1)", "O(log n)", "O(n)", "O(n log n)"], [1], None),
    ("Technical", "DBMS", "medium", "Which SQL clause filters groups after aggregation?", ["WHERE", "GROUP BY", "HAVING", "ORDER BY"], [2], None),
    ("Technical", "OOP", "easy", "Which of these are pillars of object-oriented programming? (select all)", ["Encapsulation", "Compilation", "Inheritance", "Polymorphism"], [0, 2, 3], None),
    ("Technical", "Operating Systems", "medium", "Which of the following is NOT a necessary condition for deadlock?", ["Mutual exclusion", "Hold and wait", "Preemption", "Circular wait"], [2], "No preemption is the condition"),
    ("Technical", "Networks", "easy", "Which layer of the OSI model handles routing?", ["Data link", "Network", "Transport", "Session"], [1], None),
    ("Technical", "C Programming", "medium", "What does `printf(\"%d\", 5 / 2);` print in C?", ["2.5", "2", "3", "Compilation error"], [1], "Integer division"),
]

PROBLEMS = [
    {
        "title": "Sum of Even Numbers", "difficulty": "easy", "marks": 10,
        "statement": "Given **N** integers, print the sum of the even numbers among them.",
        "input_format": "The first line has N. The second line has N space-separated integers.",
        "output_format": "Print a single integer: the sum of the even numbers.",
        "constraints": "1 ≤ N ≤ 10^5, −10^9 ≤ value ≤ 10^9",
        "sample_tests": [{"input": "5\n1 2 3 4 5", "output": "6", "explanation": "2 + 4 = 6"}],
        "hidden_tests": [{"input": "3\n1 3 5", "output": "0"}, {"input": "4\n2 4 6 8", "output": "20"},
                         {"input": "5\n-2 -3 4 0 7", "output": "2"}, {"input": "1\n1000000000", "output": "1000000000"}],
        "starter_code": {"python": "n = int(input())\nnums = list(map(int, input().split()))\n"},
    },
    {
        "title": "Palindrome Check", "difficulty": "easy", "marks": 10,
        "statement": "Given a string **S**, print `YES` if it reads the same forwards and backwards (ignoring case), otherwise print `NO`.",
        "input_format": "A single line containing S (letters only).",
        "output_format": "YES or NO",
        "constraints": "1 ≤ |S| ≤ 10^5",
        "sample_tests": [{"input": "Madam", "output": "YES"}, {"input": "hello", "output": "NO"}],
        "hidden_tests": [{"input": "a", "output": "YES"}, {"input": "RaceCar", "output": "YES"},
                         {"input": "ab", "output": "NO"}, {"input": "abcdba", "output": "NO"}],
        "starter_code": {},
    },
]

STUDENTS = [
    ("21DEMO001", "Anil Kumar", "CSE", "A"), ("21DEMO002", "Bhavya Sri", "CSE", "A"),
    ("21DEMO003", "Charan Teja", "ECE", "B"), ("21DEMO004", "Divya Reddy", "IT", "A"),
]


GK_SETS = {
    "Set A": [
        ("Which planet is known as the Red Planet?", ["Venus", "Mars", "Jupiter", "Saturn"], 1),
        ("Who wrote the Indian national anthem?", ["Bankim Chandra", "Rabindranath Tagore", "Sarojini Naidu", "Premchand"], 1),
        ("What is the capital of Australia?", ["Sydney", "Melbourne", "Canberra", "Perth"], 2),
    ],
    "Set B": [
        ("Which is the largest ocean?", ["Atlantic", "Indian", "Arctic", "Pacific"], 3),
        ("How many states does India have?", ["26", "28", "29", "30"], 1),
        ("Which gas do plants absorb for photosynthesis?", ["Oxygen", "Nitrogen", "Carbon dioxide", "Hydrogen"], 2),
    ],
}


def seed_set_exam(db, college):
    """An MCQ-only exam with one common question and two sets, rotated across the demo students."""
    now = utcnow()
    exam = Exam(college_id=college.id, title="GK Quiz (2 sets)", exam_type="mcq", show_leaderboard=True,
                description="General knowledge. Half the class gets Set A, half gets Set B.",
                start_at=now - timedelta(minutes=5), end_at=now + timedelta(days=7), duration_minutes=15,
                is_published=True, show_answers=True)
    db.add(exam)
    db.flush()
    common = MCQQuestion(college_id=college.id, section="General Knowledge", topic="Common", difficulty="easy",
                         question_text="What is the national animal of India?", options=["Lion", "Tiger", "Elephant", "Peacock"],
                         correct_options=[1], marks=1.0, is_active=False)
    db.add(common)
    db.flush()
    exam.items.append(ExamItem(item_type=ItemType.MCQ, mcq_id=common.id, section="General Knowledge", order=0))
    order = 1
    sets = []
    for name, questions in GK_SETS.items():
        qset = QuestionSet(exam_id=exam.id, name=name, source_filename="demo")
        db.add(qset)
        db.flush()
        sets.append(qset)
        for text, options, correct in questions:
            q = MCQQuestion(college_id=college.id, section="General Knowledge", topic=name, difficulty="easy",
                            question_text=text, options=options, correct_options=[correct], marks=1.0, is_active=False)
            db.add(q)
            db.flush()
            exam.items.append(ExamItem(item_type=ItemType.MCQ, mcq_id=q.id, section="General Knowledge",
                                       order=order, set_id=qset.id))
            order += 1
    students = db.query(User).filter(User.college_id == college.id, User.role == Role.STUDENT).order_by(User.roll_no).all()
    for i, student in enumerate(students):
        db.add(SetAssignment(exam_id=exam.id, student_id=student.id, set_id=sets[i % len(sets)].id))


def main():
    create_tables()
    db = SessionLocal()
    try:
        college = db.query(College).filter(College.code == "DEMO").first()
        if not college:
            college = College(name="Demo Institute of Technology", code="DEMO", city="Hyderabad", max_students=500)
            db.add(college)
            db.flush()

        if not db.query(User).filter(User.email == "tpo@demo.edu").first():
            db.add(User(role=Role.COLLEGE_ADMIN, college_id=college.id, name="Demo TPO", email="tpo@demo.edu",
                        hashed_password=hash_password("DemoAdmin@123"), must_change_password=False))

        for roll, name, branch, section in STUDENTS:
            if not db.query(User).filter(User.college_id == college.id, User.roll_no == roll).first():
                db.add(User(role=Role.STUDENT, college_id=college.id, roll_no=roll, name=name, branch=branch,
                            section=section, batch_year=2025, hashed_password=hash_password("Student@123"),
                            must_change_password=False))

        mcq_ids = []
        for section, topic, diff, text, options, correct, expl in MCQS:
            q = db.query(MCQQuestion).filter(MCQQuestion.question_text == text, MCQQuestion.college_id.is_(None)).first()
            if not q:
                q = MCQQuestion(college_id=None, section=section, topic=topic, difficulty=diff, question_text=text,
                                options=options, correct_options=correct, is_multi=len(correct) > 1,
                                explanation=expl, marks=1.0, negative_marks=0.25)
                db.add(q)
                db.flush()
            mcq_ids.append(q)

        problems = []
        for data in PROBLEMS:
            p = db.query(CodingProblem).filter(CodingProblem.title == data["title"], CodingProblem.college_id.is_(None)).first()
            if not p:
                p = CodingProblem(college_id=None, **data)
                db.add(p)
                db.flush()
            problems.append(p)

        if not db.query(Exam).filter(Exam.college_id == college.id, Exam.title == "Reios Mock Test 1").first():
            now = utcnow()
            exam = Exam(college_id=college.id, title="Reios Mock Test 1",
                        description="Aptitude, reasoning, verbal, technical MCQs and two coding questions",
                        instructions="- Attempt all sections.\n- Each MCQ carries 1 mark; wrong answers lose 0.25.\n"
                                     "- Coding questions are scored on hidden test cases.",
                        start_at=now - timedelta(minutes=5), end_at=now + timedelta(days=7), duration_minutes=60,
                        is_published=True, negative_marking=True, show_answers=True)
            order = 0
            for q in mcq_ids:
                exam.items.append(ExamItem(item_type=ItemType.MCQ, mcq_id=q.id, section=q.section, order=order))
                order += 1
            for p in problems:
                exam.items.append(ExamItem(item_type=ItemType.CODING, problem_id=p.id, section="Coding", order=order))
                order += 1
            db.add(exam)

        if not db.query(Exam).filter(Exam.college_id == college.id, Exam.title == "GK Quiz (2 sets)").first():
            seed_set_exam(db, college)

        db.commit()
        print("Demo data ready.\n")
        print("  College code : DEMO")
        print("  College admin: tpo@demo.edu / DemoAdmin@123")
        print("  Students     : 21DEMO001 to 21DEMO004 / Student@123 (college code DEMO)")
        print("  Exams        : 'Reios Mock Test 1' (MCQ + coding)")
        print("                 'GK Quiz (2 sets)' (MCQ only, Set A / Set B rotated across students)")
    finally:
        db.close()


if __name__ == "__main__":
    main()
