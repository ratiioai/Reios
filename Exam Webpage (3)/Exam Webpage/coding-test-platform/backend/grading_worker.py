"""
Grading Worker - Background process for grading submissions
Run this as a separate process: python grading_worker.py
"""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from app.grading_service import process_grading_queue
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

logger = logging.getLogger("grading_worker")

if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("Grading Worker Starting")
    logger.info("=" * 60)
    
    try:
        asyncio.run(process_grading_queue())
    except KeyboardInterrupt:
        logger.info("Grading worker stopped by user")
    except Exception as e:
        logger.exception("Grading worker crashed")
        sys.exit(1)
