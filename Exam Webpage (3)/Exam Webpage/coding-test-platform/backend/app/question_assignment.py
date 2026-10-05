"""
Unique Question Set Assignment Engine
Guarantees no two teams get identical 25-question sets
"""
import hashlib
import random
from typing import List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.config import settings
from app.models import (
    Question, Team, TeamQuestionAssignment, UsedQuestionSet,
    DifficultyLevel
)


def generate_set_hash(question_ids: List[int]) -> str:
    """
    Generate a hash of a sorted list of question IDs
    Used to check if this exact set was already assigned
    """
    sorted_ids = sorted(question_ids)
    ids_str = ','.join(map(str, sorted_ids))
    return hashlib.sha256(ids_str.encode()).hexdigest()


def get_available_questions_by_difficulty(
    db: Session,
    difficulty: DifficultyLevel
) -> List[Question]:
    """Get all active questions for a difficulty level"""
    return db.query(Question).filter(
        Question.difficulty == difficulty,
        Question.is_active == True
    ).all()


def check_question_bank_size(db: Session) -> Tuple[bool, dict]:
    """
    Check if question bank has enough questions for unique sets
    Returns: (is_sufficient, counts_dict)
    """
    counts = {}
    sufficient = True
    
    for difficulty in [DifficultyLevel.EASY, DifficultyLevel.MEDIUM, DifficultyLevel.HARD]:
        count = db.query(func.count(Question.id)).filter(
            Question.difficulty == difficulty,
            Question.is_active == True
        ).scalar()
        counts[difficulty.value] = count
        
        # Check if we have enough questions
        required = {
            DifficultyLevel.EASY: settings.EASY_QUESTIONS_PER_TEST,
            DifficultyLevel.MEDIUM: settings.MEDIUM_QUESTIONS_PER_TEST,
            DifficultyLevel.HARD: settings.HARD_QUESTIONS_PER_TEST,
        }[difficulty]
        
        # We need MORE than required for uniqueness
        # Recommended: at least 2.5x the required amount
        recommended = required * 2.5
        
        if count < required:
            sufficient = False
        elif count < recommended:
            counts[f'{difficulty.value}_warning'] = (
                f"Only {count} {difficulty.value} questions available. "
                f"Recommended: {int(recommended)} for better uniqueness."
            )
    
    return sufficient, counts


def assign_unique_question_set(
    db: Session,
    team: Team,
    max_retries: int = 10
) -> List[TeamQuestionAssignment]:
    """
    Assign a unique set of 25 questions to a team
    Retries if the exact same set was already used
    
    Returns list of TeamQuestionAssignment objects
    """
    # Check if team already has assignments
    existing = db.query(TeamQuestionAssignment).filter(
        TeamQuestionAssignment.team_id == team.id
    ).first()
    
    if existing:
        raise ValueError(f"Team {team.team_name} already has questions assigned")
    
    # Get available questions by difficulty
    easy_questions = get_available_questions_by_difficulty(db, DifficultyLevel.EASY)
    medium_questions = get_available_questions_by_difficulty(db, DifficultyLevel.MEDIUM)
    hard_questions = get_available_questions_by_difficulty(db, DifficultyLevel.HARD)
    
    # Validate we have enough questions
    if len(easy_questions) < settings.EASY_QUESTIONS_PER_TEST:
        raise ValueError(
            f"Not enough EASY questions. Need {settings.EASY_QUESTIONS_PER_TEST}, "
            f"have {len(easy_questions)}"
        )
    
    if len(medium_questions) < settings.MEDIUM_QUESTIONS_PER_TEST:
        raise ValueError(
            f"Not enough MEDIUM questions. Need {settings.MEDIUM_QUESTIONS_PER_TEST}, "
            f"have {len(medium_questions)}"
        )
    
    if len(hard_questions) < settings.HARD_QUESTIONS_PER_TEST:
        raise ValueError(
            f"Not enough HARD questions. Need {settings.HARD_QUESTIONS_PER_TEST}, "
            f"have {len(hard_questions)}"
        )
    
    # Try to find a unique set
    for attempt in range(max_retries):
        # Randomly select questions
        selected_easy = random.sample(easy_questions, settings.EASY_QUESTIONS_PER_TEST)
        selected_medium = random.sample(medium_questions, settings.MEDIUM_QUESTIONS_PER_TEST)
        selected_hard = random.sample(hard_questions, settings.HARD_QUESTIONS_PER_TEST)
        
        # Combine all selected questions
        all_selected = selected_easy + selected_medium + selected_hard
        
        # Randomize the order within each difficulty tier
        random.shuffle(selected_easy)
        random.shuffle(selected_medium)
        random.shuffle(selected_hard)
        
        # Decide final order: you can randomize all 25, or keep difficulty blocks
        # For now, let's randomize all 25 questions
        random.shuffle(all_selected)
        
        # Generate hash for uniqueness check
        question_ids = [q.id for q in all_selected]
        set_hash = generate_set_hash(question_ids)
        
        # Check if this set was already used
        existing_set = db.query(UsedQuestionSet).filter(
            UsedQuestionSet.set_hash == set_hash
        ).first()
        
        if existing_set is None:
            # This is a unique set! Assign it to the team
            
            # Record the used set
            used_set = UsedQuestionSet(
                set_hash=set_hash,
                team_id=team.id
            )
            db.add(used_set)
            
            # Create assignments
            assignments = []
            for position, question in enumerate(all_selected, start=1):
                assignment = TeamQuestionAssignment(
                    team_id=team.id,
                    question_id=question.id,
                    position=position
                )
                db.add(assignment)
                assignments.append(assignment)
            
            db.commit()
            
            # Refresh to get IDs
            for assignment in assignments:
                db.refresh(assignment)
            
            return assignments
    
    # If we get here, we failed to find a unique set after max_retries
    raise ValueError(
        f"Could not generate a unique question set after {max_retries} attempts. "
        f"This is extremely unlikely with a properly sized question bank. "
        f"Consider adding more questions."
    )


def get_team_questions(db: Session, team_id: int) -> List[dict]:
    """
    Get all questions assigned to a team, in order
    Returns list of question data with position
    """
    assignments = db.query(TeamQuestionAssignment).filter(
        TeamQuestionAssignment.team_id == team_id
    ).order_by(TeamQuestionAssignment.position).all()
    
    result = []
    for assignment in assignments:
        question = assignment.question
        result.append({
            'position': assignment.position,
            'question_id': question.id,
            'title': question.title,
            'difficulty': question.difficulty.value,
            'marks': question.marks,
            'prompt_markdown': question.prompt_markdown,
            'time_limit_seconds': question.time_limit_seconds,
            'memory_limit_mb': question.memory_limit_mb,
            'starter_code': {
                'python': question.starter_code_python,
                'cpp': question.starter_code_cpp,
                'java': question.starter_code_java,
                'javascript': question.starter_code_javascript,
            }
        })
    
    return result


def count_assigned_teams(db: Session) -> int:
    """Count how many teams have been assigned question sets"""
    return db.query(func.count(UsedQuestionSet.id.distinct())).scalar()


def get_assignment_statistics(db: Session) -> dict:
    """
    Get statistics about question assignments
    Useful for admin dashboard
    """
    total_teams = db.query(func.count(Team.id)).scalar()
    assigned_teams = count_assigned_teams(db)
    
    # Count unique sets
    unique_sets = db.query(func.count(UsedQuestionSet.set_hash.distinct())).scalar()
    
    # Get question bank sizes
    _, question_counts = check_question_bank_size(db)
    
    return {
        'total_teams': total_teams,
        'assigned_teams': assigned_teams,
        'unassigned_teams': total_teams - assigned_teams,
        'unique_sets_generated': unique_sets,
        'question_bank': question_counts,
    }
