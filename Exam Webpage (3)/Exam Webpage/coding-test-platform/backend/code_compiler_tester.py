"""
Code Compiler and Tester
Tests student code submissions against test cases
"""
import subprocess
import tempfile
import os
import sys
from pathlib import Path
from typing import Dict, Any, List
import time

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

# Absolute paths to compilers
COMPILER_BIN_DIR = os.path.abspath(os.path.join(Path(__file__).parent, "compilers", "w64devkit", "bin"))
if os.path.exists(COMPILER_BIN_DIR) and COMPILER_BIN_DIR not in os.environ.get("PATH", ""):
    os.environ["PATH"] = COMPILER_BIN_DIR + os.pathsep + os.environ.get("PATH", "")

GPP_BIN = os.path.join(COMPILER_BIN_DIR, "g++.exe") if os.path.exists(os.path.join(COMPILER_BIN_DIR, "g++.exe")) else "g++"
GCC_BIN = os.path.join(COMPILER_BIN_DIR, "gcc.exe") if os.path.exists(os.path.join(COMPILER_BIN_DIR, "gcc.exe")) else "gcc"

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")


def compare_outputs(actual: str, expected: str) -> bool:
    """
    Intelligent coding contest output comparator.
    Handles:
    1. Exact string match (ignoring CRLF & outer whitespace)
    2. Numerical / float equivalence (e.g. 20.0 == 20, 15.0 == 15, 0.0 == 0)
    3. Case-insensitive string match (e.g. YES == Yes, Even == EVEN, Odd == odd)
    4. Multi-token numerical and string comparisons
    """
    if actual is None or expected is None:
        return False
    
    # 1. Normalize line endings & strip outer whitespace
    act_clean = actual.replace("\r\n", "\n").replace("\r", "\n").strip()
    exp_clean = expected.replace("\r\n", "\n").replace("\r", "\n").strip()
    
    if act_clean == exp_clean:
        return True
    
    # 2. Case-insensitive comparison
    if act_clean.lower() == exp_clean.lower():
        return True
        
    # 3. Numeric comparison (single number)
    try:
        act_num = float(act_clean)
        exp_num = float(exp_clean)
        if abs(act_num - exp_num) < 1e-4:
            return True
    except (ValueError, TypeError):
        pass
        
    # 4. Multi-token / Multi-line comparison
    act_tokens = act_clean.split()
    exp_tokens = exp_clean.split()
    
    if len(act_tokens) != len(exp_tokens):
        return False
        
    for a, e in zip(act_tokens, exp_tokens):
        if a == e:
            continue
        if a.lower() == e.lower():
            continue
        try:
            if abs(float(a) - float(e)) < 1e-4:
                continue
        except (ValueError, TypeError):
            pass
        return False
        
    return True


class CodeCompilerTester:
    """Compile and test code locally"""
    compare_outputs = staticmethod(compare_outputs)
    
    LANGUAGE_CONFIGS = {
        "python": {
            "extension": ".py",
            "command": [sys.executable, "{file}"],
            "compile": None
        },
        "cpp": {
            "extension": ".cpp",
            "command": ["{executable}"],
            "compile": [GPP_BIN, "-std=c++17", "-O1", "{file}", "-o", "{executable}"]
        },
        "c": {
            "extension": ".c",
            "command": ["{executable}"],
            "compile": [GCC_BIN, "-O1", "{file}", "-o", "{executable}"]
        },
        "java": {
            "extension": ".java",
            "command": ["java", "{classname}"],
            "compile": ["javac", "{file}"]
        },
        "javascript": {
            "extension": ".js",
            "command": ["node", "{file}"],
            "compile": None
        }
    }
    
    @staticmethod
    def execute_code(
        code: str,
        language: str,
        stdin: str = "",
        timeout_seconds: int = 5,
        memory_limit_mb: int = 256
    ) -> Dict[str, Any]:
        """
        Execute code with test input
        
        Returns:
        {
            "success": bool,
            "stdout": str,
            "stderr": str,
            "execution_time_ms": int,
            "memory_used_mb": float,
            "error": str (if failed)
        }
        """
        if language not in CodeCompilerTester.LANGUAGE_CONFIGS:
            return {
                "success": False,
                "stdout": "",
                "stderr": "",
                "execution_time_ms": 0,
                "memory_used_mb": 0,
                "error": f"Unsupported language: {language}"
            }
        
        config = CodeCompilerTester.LANGUAGE_CONFIGS[language]
        clean_code = (code or '').replace('\ufeff', '').replace('\xa0', ' ').replace('\r\n', '\n').replace('\r', '\n')
        
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            try:
                # Create source file
                if language == "java":
                    # Extract class name from code (supports public class X or class X)
                    import re
                    match = re.search(r'(?:public\s+)?class\s+(\w+)', clean_code)
                    classname = match.group(1) if match else "Solution"
                    filename = f"{classname}.java"
                else:
                    filename = f"solution{config['extension']}"
                
                filepath = os.path.join(tmpdir, filename)
                
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(clean_code)
                
                # Compile if needed
                if config['compile']:
                    executable = os.path.join(tmpdir, "solution.exe" if os.name == 'nt' else "solution")
                    compile_cmd = [
                        cmd.format(file=filepath, executable=executable, classname=classname if language == "java" else "")
                        for cmd in config['compile']
                    ]
                    
                    compile_result = subprocess.run(
                        compile_cmd,
                        capture_output=True,
                        text=True,
                        timeout=10,
                        cwd=tmpdir
                    )
                    
                    if compile_result.returncode != 0:
                        return {
                            "success": False,
                            "stdout": "",
                            "stderr": compile_result.stderr or compile_result.stdout or "Compilation failed",
                            "execution_time_ms": 0,
                            "memory_used_mb": 0,
                            "error": "Compilation error"
                        }
                
                # Execute code
                run_cmd = [
                    cmd.format(
                        file=filepath,
                        executable=executable if config['compile'] else "",
                        classname=classname if language == "java" else ""
                    )
                    for cmd in config['command']
                ]
                
                start_time = time.time()
                
                result = subprocess.run(
                    run_cmd,
                    input=stdin,
                    capture_output=True,
                    text=True,
                    timeout=timeout_seconds,
                    cwd=tmpdir
                )
                
                execution_time_ms = int((time.time() - start_time) * 1000)
                
                return {
                    "success": result.returncode == 0,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "execution_time_ms": execution_time_ms,
                    "memory_used_mb": 0,
                    "error": None if result.returncode == 0 else (result.stderr or "Runtime error")
                }
            
            except subprocess.TimeoutExpired:
                return {
                    "success": False,
                    "stdout": "",
                    "stderr": "Time limit exceeded",
                    "execution_time_ms": timeout_seconds * 1000,
                    "memory_used_mb": 0,
                    "error": "Time limit exceeded"
                }
            
            except Exception as e:
                return {
                    "success": False,
                    "stdout": "",
                    "stderr": str(e),
                    "execution_time_ms": 0,
                    "memory_used_mb": 0,
                    "error": f"Execution error: {str(e)}"
                }

    @staticmethod
    def execute_multi_test_cases(
        code: str,
        language: str,
        test_inputs: List[str],
        timeout_seconds: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Compile code ONCE and execute against multiple test cases sequentially.
        Massively improves grading speed for C++, Java, C, and Python.
        """
        if language not in CodeCompilerTester.LANGUAGE_CONFIGS:
            return [{
                "success": False,
                "stdout": "",
                "stderr": f"Unsupported language: {language}",
                "execution_time_ms": 0,
                "error": f"Unsupported language: {language}"
            } for _ in test_inputs]
        
        config = CodeCompilerTester.LANGUAGE_CONFIGS[language]
        clean_code = (code or '').replace('\ufeff', '').replace('\xa0', ' ').replace('\r\n', '\n').replace('\r', '\n')
        results = []
        
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            try:
                # 1. Create source file
                if language == "java":
                    import re
                    match = re.search(r'(?:public\s+)?class\s+(\w+)', clean_code)
                    classname = match.group(1) if match else "Solution"
                    filename = f"{classname}.java"
                else:
                    filename = f"solution{config['extension']}"
                
                filepath = os.path.join(tmpdir, filename)
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(clean_code)
                
                # 2. Compile ONCE if needed
                if config['compile']:
                    executable = os.path.join(tmpdir, "solution.exe" if os.name == 'nt' else "solution")
                    compile_cmd = [
                        cmd.format(file=filepath, executable=executable, classname=classname if language == "java" else "")
                        for cmd in config['compile']
                    ]
                    
                    compile_res = subprocess.run(
                        compile_cmd,
                        capture_output=True,
                        text=True,
                        timeout=10,
                        cwd=tmpdir
                    )
                    
                    if compile_res.returncode != 0:
                        comp_err = compile_res.stderr or compile_res.stdout or "Compilation failed"
                        return [{
                            "success": False,
                            "stdout": "",
                            "stderr": comp_err,
                            "execution_time_ms": 0,
                            "error": "Compilation error"
                        } for _ in test_inputs]
                
                # 3. Run command definition
                run_cmd = [
                    cmd.format(
                        file=filepath,
                        executable=executable if config['compile'] else "",
                        classname=classname if language == "java" else ""
                    )
                    for cmd in config['command']
                ]
                
                # 4. Execute all test cases against the compiled binary
                for stdin_data in test_inputs:
                    start_t = time.time()
                    try:
                        res = subprocess.run(
                            run_cmd,
                            input=stdin_data,
                            capture_output=True,
                            text=True,
                            timeout=timeout_seconds,
                            cwd=tmpdir
                        )
                        elapsed_ms = int((time.time() - start_t) * 1000)
                        results.append({
                            "success": res.returncode == 0,
                            "stdout": res.stdout,
                            "stderr": res.stderr,
                            "execution_time_ms": elapsed_ms,
                            "error": None if res.returncode == 0 else (res.stderr or "Runtime error")
                        })
                    except subprocess.TimeoutExpired:
                        results.append({
                            "success": False,
                            "stdout": "",
                            "stderr": "Time limit exceeded",
                            "execution_time_ms": timeout_seconds * 1000,
                            "error": "Time limit exceeded"
                        })
                        
                return results
                
            except Exception as e:
                return [{
                    "success": False,
                    "stdout": "",
                    "stderr": str(e),
                    "execution_time_ms": 0,
                    "error": f"Execution error: {str(e)}"
                } for _ in test_inputs]
