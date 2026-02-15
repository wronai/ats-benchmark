#!/usr/bin/env python3
import sys
import os
from pathlib import Path

# Add the project root to sys.path to import benchmarks.common
sys.path.insert(0, str(Path(__file__).parent))

try:
    from benchmarks.common import check_llm_connection
except ImportError as e:
    print(f"Error: Could not import benchmarks.common: {e}")
    sys.exit(1)

if __name__ == "__main__":
    result = check_llm_connection()
    if not result["success"]:
        print("\n" + "="*40)
        print("LLM CHECK FAILED")
        print("="*40)
        sys.exit(1)
    print("\nLLM check passed. Proceeding...")
    sys.exit(0)
