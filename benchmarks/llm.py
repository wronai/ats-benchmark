"""LLM invocation utilities for benchmarks."""

from __future__ import annotations

import os
import time
from typing import Any, Dict

import litellm

from .config import get_max_tokens, get_model, get_temperature


def call_llm(prompt: str, system: str = "", max_tokens: int = 0) -> Dict[str, Any]:
    """Call LLM via litellm with OpenRouter and return response + metrics."""
    model = get_model()
    if not max_tokens:
        max_tokens = get_max_tokens()
    temperature = get_temperature()

    api_key = os.getenv("OPENROUTER_API_KEY", "")
    if not api_key:
        return {
            "response": "",
            "tokens_in": 0,
            "tokens_out": 0,
            "duration_sec": 0,
            "error": "OPENROUTER_API_KEY not set",
        }

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    start = time.time()
    try:
        print(f"  Calling LLM ({model})...", flush=True)
        response = litellm.completion(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            api_key=api_key,
            timeout=300,
        )
        duration = time.time() - start

        content = response.choices[0].message.content or ""
        usage = response.usage
        tokens_in = usage.prompt_tokens if usage else 0
        tokens_out = usage.completion_tokens if usage else 0

        return {
            "response": content,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "duration_sec": duration,
            "error": None,
        }
    except Exception as e:
        duration = time.time() - start
        return {
            "response": "",
            "tokens_in": 0,
            "tokens_out": 0,
            "duration_sec": duration,
            "error": str(e),
        }
