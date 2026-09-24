"""
Jev AI Dynamic Reasoning Effort Selector & Fast-Path Context Evaluator.
"""
import logging
from typing import Optional, Tuple

from gemini_hermes.jev.client import JevClient, JevReflexDecision

logger = logging.getLogger("gemini-hermes.jev.effort_selector")


class JevEffortSelector:
    """
    Evaluates inbound requests to dynamically choose Antigravity reasoning effort
    ('low', 'medium', 'high') and determine fast-path casual chat eligibility.
    """

    def __init__(self, client: JevClient):
        self.client = client

    async def select_reasoning_effort(
        self,
        text: str,
        default_effort: str = "medium",
        timeout: Optional[float] = None,
    ) -> Tuple[str, Optional[JevReflexDecision]]:
        """
        Dynamically determine reasoning effort ('low' | 'medium' | 'high').
        Falls back to default_effort gracefully on timeout, error, or unparsed decision.
        """
        if not self.client.is_available:
            return default_effort, None

        decision = await self.client.evaluate_reflex(text, timeout=timeout)
        if decision is None or decision.complexity_score is None:
            return default_effort, None

        # 1. Low: Trivial cognitive complexity (< 0.6) and does not need deep reasoning tools
        if decision.complexity_score < 0.6 and not decision.needs_deep_reasoning:
            return "low", decision

        # 2. High: High complexity (>= 1.5) OR strong certainty of deep reasoning (prob >= 0.85)
        if decision.complexity_score >= 1.5 or (decision.needs_deep_reasoning and decision.reasoning_prob >= 0.85):
            return "high", decision

        # 3. Medium: Standard balanced execution
        return "medium", decision
