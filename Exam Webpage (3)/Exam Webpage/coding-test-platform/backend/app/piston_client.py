"""
Piston API client with rate limiting
"""
import asyncio
import httpx
from datetime import datetime
from typing import Dict, Any, Optional
from app.config import settings
import logging

logger = logging.getLogger(__name__)


class PistonRateLimiter:
    """Rate limiter for Piston API calls"""
    
    def __init__(self, rate_limit: int = 10):
        self.rate_limit = rate_limit  # requests per second
        self.min_interval = 1.0 / rate_limit  # minimum time between requests
        self.last_request_time: Optional[datetime] = None
        self.lock = asyncio.Lock()
    
    async def acquire(self):
        """Wait if necessary to respect rate limit"""
        async with self.lock:
            if self.last_request_time:
                elapsed = (datetime.utcnow() - self.last_request_time).total_seconds()
                wait_time = self.min_interval - elapsed
                if wait_time > 0:
                    await asyncio.sleep(wait_time)
            
            self.last_request_time = datetime.utcnow()


# Global rate limiter instance
rate_limiter = PistonRateLimiter(rate_limit=settings.PISTON_RATE_LIMIT)


class PistonClient:
    """Client for Piston API code execution"""
    
    def __init__(self):
        self.base_url = settings.PISTON_API_URL
        self.timeout = 30.0  # 30 seconds timeout
    
    def _get_language_config(self, language: str) -> Dict[str, str]:
        """Map our language enum to Piston language/version"""
        mapping = {
            "python": {"language": "python", "version": "3.11"},
            "cpp": {"language": "c++", "version": "10.2.0"},
            "java": {"language": "java", "version": "15.0.2"},
            "javascript": {"language": "javascript", "version": "18.15.0"},
        }
        return mapping.get(language, mapping["python"])
    
    async def execute_code(
        self,
        code: str,
        language: str,
        stdin: str = "",
        timeout_ms: int = 5000,
        memory_limit_mb: int = 256
    ) -> Dict[str, Any]:
        """
        Execute code via Piston API with rate limiting
        
        Returns:
            {
                "success": bool,
                "stdout": str,
                "stderr": str,
                "exit_code": int,
                "execution_time_ms": int,
                "error": str (if failed)
            }
        """
        # Wait for rate limiter
        await rate_limiter.acquire()
        
        lang_config = self._get_language_config(language)
        
        payload = {
            "language": lang_config["language"],
            "version": lang_config["version"],
            "files": [
                {
                    "name": f"main.{self._get_file_extension(language)}",
                    "content": code
                }
            ],
            "stdin": stdin,
            "args": [],
            "compile_timeout": 10000,  # 10 seconds
            "run_timeout": timeout_ms,
            "compile_memory_limit": memory_limit_mb * 1024 * 1024,
            "run_memory_limit": memory_limit_mb * 1024 * 1024
        }
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/execute",
                    json=payload
                )
                response.raise_for_status()
                
                result = response.json()
                
                # Parse Piston response
                run_result = result.get("run", {})
                compile_result = result.get("compile", {})
                
                # Check for compilation errors
                if compile_result and compile_result.get("code") != 0:
                    return {
                        "success": False,
                        "stdout": "",
                        "stderr": compile_result.get("stderr", "") or compile_result.get("output", ""),
                        "exit_code": compile_result.get("code", 1),
                        "execution_time_ms": 0,
                        "error": "Compilation error"
                    }
                
                # Parse runtime result
                stdout = run_result.get("stdout", "") or run_result.get("output", "")
                stderr = run_result.get("stderr", "")
                exit_code = run_result.get("code", 0)
                
                # Estimate execution time (Piston doesn't provide this)
                execution_time_ms = 100  # Default estimate
                
                return {
                    "success": exit_code == 0 and not stderr,
                    "stdout": stdout.strip(),
                    "stderr": stderr.strip(),
                    "exit_code": exit_code,
                    "execution_time_ms": execution_time_ms,
                    "error": stderr if stderr else None
                }
        
        except httpx.TimeoutException:
            logger.error(f"Piston API timeout for {language}")
            return {
                "success": False,
                "stdout": "",
                "stderr": "Execution timeout",
                "exit_code": -1,
                "execution_time_ms": timeout_ms,
                "error": "Timeout: Code took too long to execute"
            }
        
        except httpx.HTTPStatusError as e:
            logger.error(f"Piston API error {e.response.status_code}: {e.response.text}")
            return {
                "success": False,
                "stdout": "",
                "stderr": f"API error: {e.response.status_code}",
                "exit_code": -1,
                "execution_time_ms": 0,
                "error": f"API error: {e.response.status_code}"
            }
        
        except Exception as e:
            logger.exception(f"Unexpected error calling Piston API")
            return {
                "success": False,
                "stdout": "",
                "stderr": str(e),
                "exit_code": -1,
                "execution_time_ms": 0,
                "error": f"Unexpected error: {str(e)}"
            }
    
    def _get_file_extension(self, language: str) -> str:
        """Get file extension for language"""
        extensions = {
            "python": "py",
            "cpp": "cpp",
            "java": "java",
            "javascript": "js"
        }
        return extensions.get(language, "txt")


# Global client instance
piston_client = PistonClient()
