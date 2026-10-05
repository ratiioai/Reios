"""
Grading service - executes code and calculates scores
"""
import asyncio
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from app.models import (
    Submission, Question, HiddenTestCase, GradingResult,
    TestSession, SampleTestCase
)
from app.piston_client import piston_client
from app.database import SessionLocal
from app.grading_queue import GradingQueue
from app.config import settings
from code_compiler_tester import compare_outputs
import logging
import os

logger = logging.getLogger(__name__)


class GradingService:
    """Service for grading code submissions"""
    
    @staticmethod
    def normalize_output(output: str) -> str:
        """Normalize output for comparison: handle CRLF, trailing spaces, and multi-line formats"""
        if not output:
            return ""
        lines = output.replace("\r\n", "\n").replace("\r", "\n").strip().splitlines()
        return "\n".join(line.rstrip() for line in lines)
    
    @staticmethod
    async def grade_submission(submission_id: int) -> bool:
        """
        Grade a single submission
        Returns True if successful, False otherwise
        """
        db = SessionLocal()
        try:
            # Load submission
            submission = db.query(Submission).filter(
                Submission.id == submission_id
            ).first()
            
            if not submission:
                logger.error(f"Submission {submission_id} not found")
                return False
            
            # Clean up any existing result so fresh grade runs
            db.query(GradingResult).filter(
                GradingResult.submission_id == submission_id
            ).delete()
            db.commit()
            
            # Load question and hidden test cases
            question = db.query(Question).filter(
                Question.id == submission.question_id
            ).first()
            
            if not question:
                logger.error(f"Question {submission.question_id} not found")
                return False
            
            hidden_tests = db.query(HiddenTestCase).filter(
                HiddenTestCase.question_id == question.id
            ).order_by(HiddenTestCase.order).all()
            
            if not hidden_tests:
                logger.warning(f"No hidden tests for question {question.id}")
                # No tests = full marks (shouldn't happen in production)
                GradingService._store_result(
                    db, submission_id, question.marks, 0, 0,
                    [], None, 0, 0
                )
                return True
            
            # Determine execution method (local or Piston)
            use_local_compiler = os.getenv("USE_LOCAL_COMPILER", "true").lower() == "true"
            
            # Execute code against all hidden test cases
            test_results = []
            passed_count = 0
            total_execution_time = 0
            
            from code_compiler_tester import CodeCompilerTester
            test_inputs = [tc.input_data for tc in hidden_tests]
            raw_results = CodeCompilerTester.execute_multi_test_cases(
                code=submission.code,
                language=submission.language.value,
                test_inputs=test_inputs,
                timeout_seconds=question.time_limit_seconds or 5
            )
            
            for idx, (test_case, result) in enumerate(zip(hidden_tests, raw_results), 1):
                # Compare output
                expected = GradingService.normalize_output(test_case.expected_output)
                actual = GradingService.normalize_output(result["stdout"])
                passed = result["success"] and compare_outputs(actual, expected)
                
                if passed:
                    passed_count += 1
                
                total_execution_time += result["execution_time_ms"]
                
                test_results.append({
                    "test_case": idx,
                    "passed": passed,
                    "execution_time_ms": result["execution_time_ms"],
                    "error": result.get("error") if not passed else None,
                    "expected": expected if not passed else None,
                    "actual": actual if not passed else None
                })
                
                # If compilation error, record and stop early
                if result.get("error") == "Compilation error":
                    error_output = result.get("stderr", "Compilation failed")
                    GradingService._store_result(
                        db, submission_id, 0, 0, len(hidden_tests),
                        test_results, error_output, 0, 0
                    )
                    return True
            
            # Calculate marks (all-or-nothing by default)
            marks_awarded = question.marks if passed_count == len(hidden_tests) else 0
            
            # Store result
            GradingService._store_result(
                db, submission_id, marks_awarded, 
                passed_count, len(hidden_tests),
                test_results, None, 
                total_execution_time, 0  # Memory not available from Piston
            )
            
            # Update test session score
            GradingService._update_test_session_score(db, submission.team_id)
            
            logger.info(f"Graded submission {submission_id}: {marks_awarded}/{question.marks} marks")
            return True
        
        except Exception as e:
            logger.exception(f"Error grading submission {submission_id}")
            return False
        
        finally:
            db.close()
    
    @staticmethod
    def _store_result(
        db: Session,
        submission_id: int,
        marks_awarded: int,
        passed_tests: int,
        total_tests: int,
        test_results: List[Dict[str, Any]],
        error_output: str,
        execution_time_ms: int,
        memory_used_mb: float
    ):
        """Store grading result in database"""
        try:
            existing = db.query(GradingResult).filter(
                GradingResult.submission_id == submission_id
            ).first()
            
            if existing:
                existing.marks_awarded = marks_awarded
                existing.passed_hidden_tests = passed_tests
                existing.total_hidden_tests = total_tests
                existing.test_results = test_results
                existing.error_output = error_output
                existing.execution_time_ms = execution_time_ms
                existing.memory_used_mb = memory_used_mb
            else:
                result = GradingResult(
                    submission_id=submission_id,
                    marks_awarded=marks_awarded,
                    passed_hidden_tests=passed_tests,
                    total_hidden_tests=total_tests,
                    test_results=test_results,
                    error_output=error_output,
                    execution_time_ms=execution_time_ms,
                    memory_used_mb=memory_used_mb
                )
                db.add(result)
            db.commit()
            logger.info(f"Stored grading result for submission {submission_id}")
        except Exception as e:
            logger.error(f"Error storing grading result: {e}")
            db.rollback()
    
    @staticmethod
    def _update_test_session_score(db: Session, team_id: int):
        """Update test session total score after grading"""
        try:
            # Calculate total score from all graded submissions
            from sqlalchemy import func, case
            
            result = db.query(
                func.sum(GradingResult.marks_awarded).label('total'),
                func.sum(
                    case(
                        (Question.difficulty == 'easy', GradingResult.marks_awarded),
                        else_=0
                    )
                ).label('easy'),
                func.sum(
                    case(
                        (Question.difficulty == 'medium', GradingResult.marks_awarded),
                        else_=0
                    )
                ).label('medium'),
                func.sum(
                    case(
                        (Question.difficulty == 'hard', GradingResult.marks_awarded),
                        else_=0
                    )
                ).label('hard')
            ).join(
                Submission, GradingResult.submission_id == Submission.id
            ).join(
                Question, Submission.question_id == Question.id
            ).filter(
                Submission.team_id == team_id,
                Submission.is_final == True
            ).first()
            
            # Update test session
            test_session = db.query(TestSession).filter(
                TestSession.team_id == team_id
            ).first()
            
            if test_session:
                test_session.total_score = result.total or 0
                test_session.easy_score = result.easy or 0
                test_session.medium_score = result.medium or 0
                test_session.hard_score = result.hard or 0
                db.commit()
                logger.info(f"Updated test session score for team {team_id}: {test_session.total_score}")
        
        except Exception as e:
            logger.error(f"Error updating test session score: {e}")
            db.rollback()


async def process_grading_queue():
    """
    Background worker to process grading queue
    This should run as a separate process
    """
    logger.info("Starting grading queue worker")
    
    while True:
        db = SessionLocal()
        try:
            # Get next submission from queue
            submission_id = GradingQueue.dequeue(db)
            
            if submission_id is None:
                # Queue empty, wait and retry
                await asyncio.sleep(5)
                continue
            
            logger.info(f"Processing submission {submission_id}")
            
            # Grade the submission
            success = await GradingService.grade_submission(submission_id)
            
            if success:
                GradingQueue.mark_completed(db, submission_id)
            else:
                GradingQueue.mark_failed(
                    db, submission_id, 
                    "Grading failed", 
                    retry=True,
                    retry_delay_seconds=60
                )
        
        except Exception as e:
            logger.exception("Error in grading queue worker")
            await asyncio.sleep(10)
        
        finally:
            db.close()


if __name__ == "__main__":
    # Run worker
    asyncio.run(process_grading_queue())
