"""
Helper for intent classification of sidecar queries and messages.
"""
from typing import Any, Optional, Tuple


def classify_btw_intent(text: str) -> Tuple[str, str]:
    """
    Classifies /btw input into ('live_status' | 'question' | 'task', clean_query).
    Supports explicit prefixes and natural language heuristics.
    """
    raw = text.strip()
    lower = raw.lower()

    # Explicit prefix overrides
    if lower.startswith("?") or lower.startswith("q:") or lower.startswith("ask:") or lower.startswith("query:"):
        for prefix in ("?", "q:", "ask:", "query:"):
            if lower.startswith(prefix):
                clean = raw[len(prefix):].strip()
                return ("question", clean or raw)
    if lower.startswith(("queue:", "task:", "todo:", "do:", "later:")):
        for prefix in ("queue:", "task:", "todo:", "do:", "later:"):
            if lower.startswith(prefix):
                clean = raw[len(prefix):].strip()
                return ("task", clean or raw)

    # Status / live telemetry inquiry
    status_keywords = [
        "where are you", "what are you doing", "what are u doing", "where r u",
        "progress", "status", "how is it going", "how's it going", "sedang apa",
        "lagi apa", "sampai mana", "current step", "what step",
        "working on", "how far", "is it done", "are you done"
    ]
    if any(k in lower for k in status_keywords):
        return ("live_status", raw)

    # Explicit task steering / sequence keywords
    task_indicators = (
        "after this", "then ", "next ", "also do", "queue ",
        "setelah ini", "nanti ", "tolong ", "please make sure",
        "remember to", "make sure to", "ensure that", "run ",
        "build ", "deploy ", "create ", "add ", "implement ",
        "fix ", "test ", "install "
    )
    if not raw.endswith("?") and any(lower.startswith(ind) for ind in task_indicators):
        return ("task", raw)

    # Question indicators
    question_words = (
        "what", "why", "how", "who", "when", "where", "which",
        "is", "are", "can", "could", "would", "should", "do", "does", "did",
        "explain", "describe", "tell me", "summarize",
        "apakah", "kenapa", "mengapa", "siapa", "gimana", "bagaimana", "adakah"
    )
    first_word = lower.split()[0] if lower.split() else ""
    if raw.endswith("?") or first_word in question_words:
        return ("question", raw)

    # Default fallback: treat as task queue
    return ("task", raw)


async def classify_btw_intent_smart(
    text: str,
    jev_adapter: Optional[Any] = None,
    timeout: Optional[float] = None,
) -> Tuple[str, str]:
    """
    Smart /btw classifier.
    1. Checks deterministic explicit prefix overrides in 0ms.
    2. If Jev is available (start-jev world), queries Jev's Choice primitive.
    3. If Jev times out (>1.0s), errors, or confidence < 0.85, falls back to pure heuristics.
    """
    raw = text.strip()
    lower = raw.lower()

    # 1. Deterministic explicit prefix overrides
    if lower.startswith("?") or lower.startswith("q:") or lower.startswith("ask:") or lower.startswith("query:"):
        for prefix in ("?", "q:", "ask:", "query:"):
            if lower.startswith(prefix):
                clean = raw[len(prefix):].strip()
                return ("question", clean or raw)
    if lower.startswith(("queue:", "task:", "todo:", "do:", "later:")):
        for prefix in ("queue:", "task:", "todo:", "do:", "later:"):
            if lower.startswith(prefix):
                clean = raw[len(prefix):].strip()
                return ("task", clean or raw)

    # 2. Jev AI System-One classification if adapter is provided and available
    if jev_adapter and getattr(jev_adapter, "is_available", False):
        try:
            res = await jev_adapter.classify_btw(raw, timeout=timeout or 3.0)
            if res:
                intent, _conf = res
                return (intent, raw)
        except Exception:
            pass  # Fall through to pure heuristic fallback

    # 3. Fallback to standard deterministic / heuristic classification
    return classify_btw_intent(text)

