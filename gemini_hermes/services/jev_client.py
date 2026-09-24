"""
Jev AI (TypeSafe AI) client service for fast, typed System-One decision making.
"""
import logging
import re
from typing import Optional, Dict, Any, List
import httpx

from gemini_hermes.config import config
from gemini_hermes.brain.jev_types import JevCategory, JevDecisionOutcome

logger = logging.getLogger("gemini-hermes.services.jev")


class JevClient:
    """
    Client for interacting with Jev AI's structured decision engine.
    Provides sub-50ms deterministic classification, calibrated confidence scoring,
    and automatic fallback to Antigravity CLI (System-Two) on low-confidence queries.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        confidence_threshold: Optional[float] = None,
    ):
        self.api_key = api_key if api_key is not None else config.jev_api_key
        self.base_url = base_url or config.jev_api_base
        self.confidence_threshold = (
            confidence_threshold if confidence_threshold is not None else config.jev_confidence_threshold
        )
        self.client: Optional[httpx.AsyncClient] = None

    async def decide(
        self,
        prompt: str,
        context: Optional[str] = None,
        timeout: float = 15.0,
    ) -> JevDecisionOutcome:
        """
        Submits prompt to Jev decision engine.
        Returns a typed JevDecisionOutcome contract.
        """
        clean_prompt = prompt.strip()
        if not clean_prompt:
            return JevDecisionOutcome(
                category=JevCategory.CLARIFICATION_NEEDED,
                confidence=1.0,
                suggested_action="request_clarification",
                is_high_confidence=True,
                reasoning_tier="system_one",
            )

        # If no API key configured, use local sandbox heuristic engine
        if not self.api_key:
            return self._decide_sandbox(clean_prompt, context=context)

        # Call live Jev / TypeSafe AI endpoint
        url = f"{self.base_url.rstrip('/')}/decide"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": f"Gemini-Hermes/{config.app_version} (JevClient)",
        }
        payload = {
            "prompt": clean_prompt,
            "context": context or "",
            "categories": [c.value for c in JevCategory],
        }

        try:
            if not self.client or self.client.is_closed:
                self.client = httpx.AsyncClient(timeout=timeout)

            resp = await self.client.post(url, json=payload, headers=headers, timeout=timeout)
            if resp.status_code == 200:
                data = resp.json()
                cat_str = data.get("category", JevCategory.FALLBACK_TO_AGY.value)
                try:
                    category = JevCategory(cat_str)
                except ValueError:
                    category = JevCategory.FALLBACK_TO_AGY

                confidence = float(data.get("confidence", 0.0))
                is_high = confidence >= self.confidence_threshold
                requires_two = not is_high or category == JevCategory.FALLBACK_TO_AGY

                return JevDecisionOutcome(
                    category=category,
                    confidence=confidence,
                    suggested_action=data.get("suggested_action"),
                    parameters=data.get("parameters", {}),
                    reasoning_tier="system_one" if not requires_two else "system_two_fallback",
                    is_high_confidence=is_high,
                    requires_system_two=requires_two,
                    raw_response=data,
                )
            else:
                logger.warning(f"Jev API returned status {resp.status_code}: {resp.text}")
                return JevDecisionOutcome(
                    category=JevCategory.FALLBACK_TO_AGY,
                    confidence=0.0,
                    suggested_action="api_error_fallback",
                    is_high_confidence=False,
                    requires_system_two=True,
                )
        except Exception as e:
            logger.error(f"Error calling Jev decision endpoint: {e}")
            return JevDecisionOutcome(
                category=JevCategory.FALLBACK_TO_AGY,
                confidence=0.0,
                suggested_action="connection_error_fallback",
                is_high_confidence=False,
                requires_system_two=True,
            )

    def _decide_sandbox(self, prompt: str, context: Optional[str] = None) -> JevDecisionOutcome:
        """
        Deterministic, offline sandbox decision evaluation.
        Calibrates confidence scores based on structural markers and intent keywords.
        """
        lower = prompt.lower()

        # System status queries
        if any(w in lower for w in ("status", "health", "ping", "are you running", "system info")):
            return JevDecisionOutcome(
                category=JevCategory.SYSTEM_STATUS,
                confidence=0.96,
                suggested_action="show_status",
                is_high_confidence=True,
                reasoning_tier="system_one",
            )

        # Ephemeral side Q&A
        if lower.startswith("?") or lower.startswith("q:") or lower.startswith("/btw"):
            return JevDecisionOutcome(
                category=JevCategory.EPHEMERAL_QA,
                confidence=0.94,
                suggested_action="execute_ephemeral_qa",
                is_high_confidence=True,
                reasoning_tier="system_one",
            )

        # Task queueing
        if any(lower.startswith(p) for p in ("queue:", "task:", "after this", "then ", "later:")):
            return JevDecisionOutcome(
                category=JevCategory.TASK_QUEUE,
                confidence=0.95,
                suggested_action="enqueue_task",
                is_high_confidence=True,
                reasoning_tier="system_one",
            )

        # Code editing
        if any(w in lower for w in ("refactor", "write test", "bug fix", "fix error", "implement function", "create class")):
            return JevDecisionOutcome(
                category=JevCategory.CODE_EDIT,
                confidence=0.91,
                suggested_action="invoke_coding_tools",
                is_high_confidence=True,
                reasoning_tier="system_one",
            )

        # Tool execution
        if lower.startswith("/exec") or lower.startswith("run command") or lower.startswith("bash:"):
            return JevDecisionOutcome(
                category=JevCategory.TOOL_EXECUTION,
                confidence=0.93,
                suggested_action="execute_shell_tool",
                is_high_confidence=True,
                reasoning_tier="system_one",
            )

        # Standard conversation
        if any(lower.startswith(g) for g in ("hi", "hello", "hey", "greetings", "thanks", "thank you")):
            return JevDecisionOutcome(
                category=JevCategory.CHAT_CONVERSATION,
                confidence=0.98,
                suggested_action="conversational_reply",
                is_high_confidence=True,
                reasoning_tier="system_one",
            )

        # Ambiguous / Complex queries requiring System-Two deliberation
        return JevDecisionOutcome(
            category=JevCategory.FALLBACK_TO_AGY,
            confidence=0.62,
            suggested_action="delegate_to_agy_deep_reasoning",
            is_high_confidence=False,
            requires_system_two=True,
            reasoning_tier="system_two_fallback",
        )

    async def close(self):
        if self.client and not self.client.is_closed:
            await self.client.aclose()
