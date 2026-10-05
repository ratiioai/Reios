"""
AI Code Evaluator Service using OpenRouter API
Ultra-low latency (< 5 seconds) evaluation with automatic fast fallbacks.
"""
import os
import httpx
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

FAST_MODELS = [
    "poolside/laguna-xs-2.1:free",
    "poolside/laguna-s-2.1:free",
    "cohere/north-mini-code:free"
]


class AICodeEvaluator:
    """Fast service to evaluate student code structure, complexity, and quality under 3s"""

    @staticmethod
    async def evaluate_code(
        problem_title: str,
        problem_prompt: str,
        code: str,
        language: str,
        test_passed: Optional[bool] = None
    ) -> Dict[str, Any]:
        """
        Evaluate code using Poolside Laguna (with sub-3s latency optimization)
        """
        if not code or not code.strip():
            return {
                "success": False,
                "error": "No code provided for AI evaluation."
            }

        system_prompt = (
            "You are a strict, fast coding contest judge. Review this code concisely in under 80 words:\n"
            "1. 📊 **Score**: X/10 (Architecture & Correctness)\n"
            "2. ⚡ **Complexity**: Time: O(..), Space: O(..)\n"
            "3. 🔍 **Pros & Cons**: 1-2 bullet points\n"
            "4. 💡 **Key Tip**: 1 crisp optimization suggestion"
        )

        user_content = (
            f"Problem: {problem_title}\n"
            f"Lang: {language}\n"
            f"Code:\n```{language}\n{code[:800]}\n```"
        )

        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:3000",
            "X-Title": "SPEC Industry Hack 2026 Code Evaluator"
        }

        # Try models in order of preference with low max_tokens for speed
        async with httpx.AsyncClient(timeout=2.5) as client:
            for model_name in FAST_MODELS:
                payload = {
                    "model": model_name,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_content}
                    ],
                    "max_tokens": 200,
                    "temperature": 0.1
                }

                try:
                    response = await client.post(OPENROUTER_URL, headers=headers, json=payload)
                    if response.status_code == 200:
                        data = response.json()
                        choices = data.get("choices", [])
                        if choices:
                            review = choices[0].get("message", {}).get("content", "")
                            if review and review.strip():
                                return {
                                    "success": True,
                                    "model": data.get("model", model_name),
                                    "review": review.strip()
                                }
                    else:
                        logger.warning(f"Model {model_name} returned {response.status_code}, trying fallback...")
                except (httpx.TimeoutException, httpx.RequestError) as ex:
                    logger.warning(f"Model {model_name} timed out or failed ({ex}), trying fallback...")
                    continue

        return {
            "success": False,
            "error": "AI evaluation timed out. Please retry."
        }

