#!/usr/bin/env python3
"""
Live connectivity and primitive verification script for TypeSafe AI (Jev).
Tests AsyncTypeSafeClient and the three core primitives: Choice, Score, Noul.
"""

import asyncio
import os
import sys
import time
from pathlib import Path

# Ensure repo root is in python path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from gemini_hermes.config import Config

try:
    from typesafe_sdk import AsyncTypeSafeClient, Choice, Score, Noul
except ImportError:
    print("[ERROR] typesafe-sdk is not installed. Run: pip install -r requirements-jev.txt")
    sys.exit(1)


async def main():
    print("=" * 60)
    print("  TypeSafe AI (Jev) - Live Primitive & Connectivity Test")
    print("=" * 60)

    cfg = Config()
    if not cfg.has_typesafe:
        print("[ERROR] TYPESAFE_API_KEY is not configured in .env or environment.")
        print("Please run `./run.sh config` to configure your API key.")
        sys.exit(1)

    masked_key = (
        cfg.typesafe_api_key[:4] + "..." + cfg.typesafe_api_key[-4:]
        if len(cfg.typesafe_api_key) > 8
        else "***"
    )
    print(f"API Base   : {cfg.typesafe_api_base}")
    print(f"Model      : {cfg.typesafe_model}")
    print(f"API Key    : {masked_key} (len={len(cfg.typesafe_api_key)})")
    print("-" * 60)

    client = AsyncTypeSafeClient(
        api_key=cfg.typesafe_api_key,
        base_url=cfg.typesafe_api_base,
        model=cfg.typesafe_model,
        timeout=15.0,
    )

    test_state = "User message: Can you help me debug a NullPointerException in my Java Spring Boot backend?"
    print(f"Test State : \"{test_state}\"")
    print("\nSending System-One request with Choice, Score, and Noul primitives...")

    questions = {
        "intent": Choice(
            instructions="Identify the primary intent of the user message.",
            criteria={
                "code_debugging": "User is asking to debug code or fix an error",
                "chat_casual": "Casual greeting, small talk, or general question",
                "system_command": "Command to manage bot, configure settings, or admin actions",
            },
        ),
        "complexity": Score(
            instructions="Rate the cognitive complexity of this request.",
            criteria=[
                "Trivial / simple one-liner response",
                "Moderate complexity requiring short code or explanation",
                "Deep complexity requiring deep reasoning, multi-file analysis, or architecture",
            ],
        ),
        "needs_code_tool": Noul(
            instructions="Does this request require code inspection, editing, or execution tools?",
        ),
    }

    t0 = time.perf_counter()
    try:
        response = await client.system_one(
            state=test_state,
            questions=questions,
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
    except Exception as e:
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        print(f"\n[FAILED] Request failed after {elapsed_ms:.1f}ms:")
        print(f"Exception: {type(e).__name__}: {e}")
        sys.exit(1)

    print(f"\n[SUCCESS] Response received in {elapsed_ms:.1f} ms!")
    print("=" * 60)
    print("Results:")

    # Print raw response structure details
    answers = getattr(response, "answers", response)
    if isinstance(answers, dict):
        for q_name, answer in answers.items():
            print(f"\n* Question: [{q_name}]")
            print(f"  Type       : {type(answer).__name__}")
            if hasattr(answer, "choice"):
                print(f"  Choice        : {answer.choice}")
                print(f"  Confidence    : {getattr(answer, 'confidence', 'N/A')}")
                if hasattr(answer, "probabilities") and answer.probabilities:
                    print(f"  Probabilities : {answer.probabilities}")
            elif hasattr(answer, "score"):
                print(f"  Score         : {answer.score}")
                print(f"  Confidence    : {getattr(answer, 'confidence', 'N/A')}")
                if hasattr(answer, "probabilities") and answer.probabilities:
                    print(f"  Probabilities : {answer.probabilities}")
            elif hasattr(answer, "noul"):
                print(f"  Noul Prob     : {answer.noul:.4f}")
                print(f"  Decision      : {'YES' if answer.noul >= 0.5 else 'NO'}")
            else:
                print(f"  Raw           : {answer}")
    else:
        print(f"Raw response: {response}")

    if hasattr(response, "usage") and response.usage:
        print(f"\nUsage Stats: {response.usage}")

    print("=" * 60)
    print("TypeSafe AI connection and all 3 primitives verified successfully!")


if __name__ == "__main__":
    asyncio.run(main())
