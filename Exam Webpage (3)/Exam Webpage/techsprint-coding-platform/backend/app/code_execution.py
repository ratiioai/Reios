"""
Code execution service using Piston API
"""
import httpx
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime

PISTON_API_URL = "https://emkc.org/api/v2/piston"


class CodeExecutionService:
    """Service for executing code using Piston API"""

    # Language mapping: our language name -> Piston language identifier
    LANGUAGE_MAP = {
        "python": "python",
        "javascript": "javascript",
        "java": "java",
        "cpp": "c++",
        "c": "c"
    }

    @staticmethod
    async def get_available_runtimes() -> List[Dict[str, Any]]:
        """Get list of available language runtimes from Piston"""
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{PISTON_API_URL}/runtimes")
            response.raise_for_status()
            return response.json()

    @staticmethod
    async def execute_code(
        language: str,
        source_code: str,
        stdin: str = "",
        timeout: int = 10000
    ) -> Dict[str, Any]:
        """
        Execute code using Piston API
        
        Args:
            language: Programming language (python, javascript, java, cpp, c)
            source_code: The code to execute
            stdin: Standard input for the program
            timeout: Execution timeout in milliseconds (default: 10 seconds)
            
        Returns:
            Dict containing:
                - stdout: Standard output
                - stderr: Standard error
                - exit_code: Exit code
                - execution_time: Time taken in ms
                - error: Error message if any
        """
        try:
            # Map language to Piston identifier
            piston_lang = CodeExecutionService.LANGUAGE_MAP.get(language.lower())
            if not piston_lang:
                return {
                    "stdout": "",
                    "stderr": f"Unsupported language: {language}",
                    "exit_code": 1,
                    "execution_time": 0,
                    "error": f"Language '{language}' is not supported"
                }

            # Prepare request payload
            payload = {
                "language": piston_lang,
                "version": "*",  # Use latest version
                "files": [
                    {
                        "content": source_code
                    }
                ],
                "stdin": stdin,
                "compile_timeout": timeout,
                "run_timeout": timeout
            }

            start_time = datetime.utcnow()
            
            # Execute code via Piston API
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{PISTON_API_URL}/execute",
                    json=payload
                )
                response.raise_for_status()
                result = response.json()

            end_time = datetime.utcnow()
            execution_time = int((end_time - start_time).total_seconds() * 1000)

            # Parse response
            run_result = result.get("run", {})
            compile_result = result.get("compile", {})

            # Check for compilation errors
            if compile_result and compile_result.get("code") != 0:
                return {
                    "stdout": compile_result.get("stdout", ""),
                    "stderr": compile_result.get("stderr", ""),
                    "exit_code": compile_result.get("code", 1),
                    "execution_time": execution_time,
                    "error": "Compilation failed"
                }

            # Return execution result
            return {
                "stdout": run_result.get("stdout", ""),
                "stderr": run_result.get("stderr", ""),
                "exit_code": run_result.get("code", 0),
                "execution_time": execution_time,
                "error": run_result.get("stderr", "") if run_result.get("code") != 0 else None
            }

        except httpx.TimeoutException:
            return {
                "stdout": "",
                "stderr": "Execution timeout exceeded",
                "exit_code": 124,
                "execution_time": timeout,
                "error": "Time Limit Exceeded"
            }
        except httpx.HTTPError as e:
            return {
                "stdout": "",
                "stderr": f"HTTP error: {str(e)}",
                "exit_code": 1,
                "execution_time": 0,
                "error": f"Code execution service error: {str(e)}"
            }
        except Exception as e:
            return {
                "stdout": "",
                "stderr": f"Unexpected error: {str(e)}",
                "exit_code": 1,
                "execution_time": 0,
                "error": f"Unexpected error during execution: {str(e)}"
            }

    @staticmethod
    async def run_test_case(
        language: str,
        source_code: str,
        test_input: str,
        expected_output: str,
        timeout: int = 10000
    ) -> Dict[str, Any]:
        """
        Run a single test case
        
        Returns:
            Dict containing:
                - passed: Boolean indicating if test passed
                - actual_output: Actual output from code
                - expected_output: Expected output
                - execution_time: Time taken in ms
                - error: Error message if any
        """
        result = await CodeExecutionService.execute_code(
            language=language,
            source_code=source_code,
            stdin=test_input,
            timeout=timeout
        )

        # Normalize outputs (strip whitespace)
        actual = result["stdout"].strip()
        expected = expected_output.strip()

        return {
            "passed": actual == expected and result["exit_code"] == 0,
            "actual_output": actual,
            "expected_output": expected,
            "execution_time": result["execution_time"],
            "exit_code": result["exit_code"],
            "stderr": result["stderr"],
            "error": result.get("error")
        }

    @staticmethod
    async def run_multiple_test_cases(
        language: str,
        source_code: str,
        test_cases: List[Dict[str, str]],
        timeout: int = 10000
    ) -> List[Dict[str, Any]]:
        """
        Run multiple test cases in parallel
        
        Args:
            language: Programming language
            source_code: The code to execute
            test_cases: List of test cases with 'input' and 'expected_output'
            timeout: Timeout per test case in milliseconds
            
        Returns:
            List of test case results
        """
        tasks = []
        for test_case in test_cases:
            task = CodeExecutionService.run_test_case(
                language=language,
                source_code=source_code,
                test_input=test_case.get("input", ""),
                expected_output=test_case.get("expected_output", ""),
                timeout=timeout
            )
            tasks.append(task)
        
        return await asyncio.gather(*tasks)
