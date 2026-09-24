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

    async def select_model_and_effort(
        self,
        text: str,
        default_model: str = "gemini-3.7-flash",
        default_effort: str = "medium",
        timeout: Optional[float] = None,
    ) -> Tuple[str, str, Optional[JevReflexDecision]]:
        """
        Dynamically determine both Antigravity model and reasoning effort.
        Tier 1: gemini-3.6-flash (low effort) - cheap/fast for simple interaction, small edits, basic questions
        Tier 2: gemini-3.7-flash (medium effort) - balanced for normal coding & moderate debugging
        Tier 3: gemini-3.8-flash (high effort) - high workload, multi-file architecture, long agent runs
        Tier 4: gemini-3.1-pro (high effort) - hard reasoning where Flash models struggle
        """
        if not self.client.is_available:
            return default_model, default_effort, None

        decision = await self.client.evaluate_reflex(text, timeout=timeout)
        if decision is None or decision.complexity_score is None:
            return default_model, default_effort, None

        # 1. Check explicit model tier Choice if present from Jev
        tier = getattr(decision, "model_tier", None)
        conf = getattr(decision, "model_confidence", 0.0)
        if tier and conf >= 0.70:
            tier_mapping = {
                "tier_3_6_flash": ("gemini-3.6-flash", "low"),
                "tier_3_7_flash": ("gemini-3.7-flash", "medium"),
                "tier_3_8_flash": ("gemini-3.8-flash", "high"),
                "tier_3_1_pro": ("gemini-3.1-pro", "high"),
            }
            if tier in tier_mapping:
                model, effort = tier_mapping[tier]
                decision.recommended_model = model
                return model, effort, decision

        # 2. Mathematical calibration thresholds based on complexity score & reasoning need
        # Tier 1: Trivial complexity (< 0.6) and does not need deep reasoning tools (cheapest / fast)
        if decision.complexity_score < 0.6 and not decision.needs_deep_reasoning:
            model, effort = "gemini-3.6-flash", "low"
        # Tier 4: Extreme algorithmic / proof reasoning (>= 1.85 complexity and >= 0.90 reasoning prob)
        elif decision.complexity_score >= 1.85 and decision.reasoning_prob >= 0.90:
            model, effort = "gemini-3.1-pro", "high"
        # Tier 3: High workload / complex architecture / multi-file (>= 1.5 complexity or deep reasoning certainty)
        elif decision.complexity_score >= 1.5 or (decision.needs_deep_reasoning and decision.reasoning_prob >= 0.85):
            model, effort = "gemini-3.8-flash", "high"
        # Tier 2: Standard balanced execution (normal coding, moderate debugging, single-file edits)
        else:
            model, effort = "gemini-3.7-flash", "medium"

        decision.recommended_model = model
        return model, effort, decision

    async def select_reasoning_effort(
        self,
        text: str,
        default_effort: str = "medium",
        timeout: Optional[float] = None,
    ) -> Tuple[str, Optional[JevReflexDecision]]:
        """
        Dynamically determine reasoning effort ('low' | 'medium' | 'high').
        Backward-compatible facade delegating to select_model_and_effort.
        """
        _, effort, decision = await self.select_model_and_effort(
            text,
            default_model="gemini-3.7-flash",
            default_effort=default_effort,
            timeout=timeout,
        )
        return effort, decision
