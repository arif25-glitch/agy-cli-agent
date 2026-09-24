#!/usr/bin/env python3
"""
Interactive Jev AI Reflex Playground.
Allows you to interactively test any message against TypeSafe AI (Jev System-One),
inspect latency in ms, view calibrated probabilities, and see how the
Inbound Fast-Path / Reflex Router would route it in production.
"""

import asyncio
import os
import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from gemini_hermes.config import Config

try:
    from typesafe_sdk import AsyncTypeSafeClient, Choice, Score, Noul
except ImportError:
    print("[ERROR] typesafe-sdk is not installed. Run: pip install -r requirements-jev.txt")
    sys.exit(1)


def build_reflex_router_questions():
    return {
        "intent": Choice(
            instructions="Identify the user's primary intent.",
            criteria={
                "casual_chat": "Casual greeting, smalltalk, thank you, acknowledgment, or humor",
                "factual_query": "Quick factual, informational, or conceptual inquiry that does not modify code",
                "code_engineering": "Writing, debugging, editing code, terminal commands, or debugging errors",
                "complex_architecture": "Multi-step system design, large refactoring, or autonomous workflows",
            },
        ),
        "complexity": Score(
            instructions="Rate the cognitive depth required to fulfill this request.",
            criteria=[
                "Trivial: Instant one-liner, greeting, or simple conversational reply",
                "Moderate: Single function, concise explanation, or targeted answer",
                "Deep: Multi-file analysis, autonomous agent tools, or deep reasoning",
            ],
        ),
        "needs_agent_tools": Noul(
            instructions="Does this request require file edits, shell commands, or agentic tool execution?",
        ),
        "is_safe_and_actionable": Noul(
            instructions="Is this prompt safe, coherent, and actionable?",
        ),
    }


async def evaluate_single_message(client: AsyncTypeSafeClient, text: str):
    clean_text = text.strip()
    if not clean_text:
        print("  ⚠️ Empty message.")
        return

    questions = build_reflex_router_questions()

    print(f"\n⚡ Sending to Jev System-One reflex engine...")
    t0 = time.perf_counter()
    try:
        response = await client.system_one(
            state=f"Inbound Telegram message from user: \"{clean_text}\"",
            questions=questions,
            timeout=8.0,
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
    except Exception as e:
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        print(f"  ❌ Error after {elapsed_ms:.1f}ms: {type(e).__name__}: {e}")
        return

    answers = getattr(response, "answers", response)
    intent_ans = answers.get("intent")
    complexity_ans = answers.get("complexity")
    tools_ans = answers.get("needs_agent_tools")
    safe_ans = answers.get("is_safe_and_actionable")

    intent = getattr(intent_ans, "choice", "unknown")
    intent_conf = getattr(intent_ans, "confidence", 0.0)
    intent_probs = getattr(intent_ans, "probabilities", {}) or {}

    complexity_score = getattr(complexity_ans, "score", 0.0)
    complexity_conf = getattr(complexity_ans, "confidence", 0.0)

    tools_prob = getattr(tools_ans, "noul", 0.0)
    safe_prob = getattr(safe_ans, "noul", 0.0)

    # Fast-Path / Reflex Decision Logic
    is_fast_path = (
        intent in ("casual_chat", "factual_query")
        and complexity_score < 0.6
        and tools_prob < 0.25
    )

    if complexity_score < 0.6:
        recommended_effort = "low (fast-path)"
    elif complexity_score < 1.4:
        recommended_effort = "medium (standard)"
    else:
        recommended_effort = "high (deep reasoning)"

    route_display = "🚀 FAST-PATH REFLEX (<1s response)" if is_fast_path else "🧠 FULL AGY SYSTEM-2 (deep agent engine)"

    print("=" * 64)
    print(f"  Jev Reflex Decision in {elapsed_ms:.1f} ms")
    print("=" * 64)
    print(f"  Message          : \"{clean_text}\"")
    print(f"  Route Decision   : {route_display}")
    print(f"  Reasoning Effort : --effort {recommended_effort}")
    print("-" * 64)
    print(f"  1. Intent (Choice)    : {intent.upper()} (confidence: {intent_conf*100:.1f}%)")
    if intent_probs:
        sorted_probs = sorted(intent_probs.items(), key=lambda x: x[1], reverse=True)
        prob_str = ", ".join([f"{k}: {v*100:.1f}%" for k, v in sorted_probs if v > 0.01])
        print(f"     Distribution       : [{prob_str}]")
    print(f"  2. Complexity (Score) : {complexity_score:.2f} / 2.0 (confidence: {complexity_conf*100:.1f}%)")
    print(f"  3. Needs Tools (Noul) : {'YES' if tools_prob >= 0.5 else 'NO'} ({tools_prob*100:.1f}% probability)")
    print(f"  4. Actionable (Noul)  : {'YES' if safe_prob >= 0.5 else 'NO'} ({safe_prob*100:.1f}% probability)")
    print("=" * 64)


async def main():
    cfg = Config()
    if not cfg.has_typesafe:
        print("[ERROR] TYPESAFE_API_KEY is missing in .env.")
        sys.exit(1)

    client = AsyncTypeSafeClient(
        api_key=cfg.typesafe_api_key,
        base_url=cfg.typesafe_api_base,
        model=cfg.typesafe_model,
        timeout=10.0,
    )

    # If argument provided on CLI, evaluate once and exit
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
        await evaluate_single_message(client, query)
        return

    # Interactive Loop
    print("\n" + "=" * 64)
    print("  TypeSafe AI (Jev) - Interactive Reflex Playground")
    print("  Type any message to feel how Jev evaluates & routes it.")
    print("  Type 'exit' or 'q' to quit.")
    print("=" * 64)

    while True:
        try:
            user_input = input("\n📝 Enter message > ").strip()
            if not user_input:
                continue
            if user_input.lower() in ("exit", "quit", "q"):
                print("Exiting playground. Colleague standing by!")
                break
            await evaluate_single_message(client, user_input)
        except (KeyboardInterrupt, EOFError):
            print("\nExiting playground.")
            break


if __name__ == "__main__":
    asyncio.run(main())
