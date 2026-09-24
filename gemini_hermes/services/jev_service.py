"""
Jev AI (TypeSafe AI) System-One reflex service.
Provides fast, type-safe decision primitives (Choice, Score, Noul) with strict timeout guards
and graceful fallbacks. 100% optional and decoupled from core bot execution.
"""

import asyncio
from dataclasses import dataclass, field
import logging
import time
from typing import Any, Dict, Optional, Tuple

from gemini_hermes.config import Config, config as default_config

logger = logging.getLogger("gemini-hermes.services.jev")

try:
    from typesafe_sdk import AsyncTypeSafeClient, Choice, Score, Noul
    from typesafe_sdk import TypeSafeError
    HAS_TYPESAFE_SDK = True
except ImportError:  # pragma: no cover
    AsyncTypeSafeClient = None
    Choice = None
    Score = None
    Noul = None
    TypeSafeError = Exception
    HAS_TYPESAFE_SDK = False


@dataclass
class JevReflexDecision:
    """Structured decision output from Jev System-One evaluation."""
    intent: Optional[str] = None
    intent_confidence: float = 0.0
    intent_probabilities: Dict[str, float] = field(default_factory=dict)
    complexity_score: Optional[float] = None
    complexity_confidence: float = 0.0
    needs_deep_reasoning: bool = False
    reasoning_prob: float = 0.0
    raw_answers: Dict[str, Any] = field(default_factory=dict)
    latency_ms: float = 0.0

    @property
    def is_confident(self) -> bool:
        """Convenience property for high-confidence decisions."""
        return self.intent_confidence >= 0.80


class JevService:
    """
    Client wrapper for TypeSafe AI's Jev model.
    Encapsulates asynchronous calls, timeout enforcement, exception handling, and
    graceful degradation so that core bot operations are never stalled or broken.
    """

    def __init__(
        self,
        cfg: Optional[Config] = None,
        client: Optional[Any] = None,
        default_timeout: float = 5.0,
    ):
        self.config = cfg or default_config
        self.default_timeout = default_timeout
        self._client = client

    @property
    def is_available(self) -> bool:
        """
        Check if TypeSafe SDK is installed, API key is provided, and JEV is enabled.
        """
        return bool(
            HAS_TYPESAFE_SDK
            and self.config.has_typesafe
            and self.config.typesafe_api_key.strip()
        )

    def get_client(self) -> Optional[Any]:
        """
        Lazily instantiate or return the AsyncTypeSafeClient.
        Returns None if Jev is not available or credentials missing.
        """
        if not self.is_available:
            return None

        if self._client is None and HAS_TYPESAFE_SDK:
            self._client = AsyncTypeSafeClient(
                api_key=self.config.typesafe_api_key,
                base_url=self.config.typesafe_api_base,
                model=self.config.typesafe_model,
                timeout=self.default_timeout,
            )
        return self._client

    async def close(self) -> None:
        """Close client connections if supported."""
        if self._client and hasattr(self._client, "close"):
            try:
                res = self._client.close()
                if asyncio.iscoroutine(res):
                    await res
            except Exception as e:
                logger.debug("Error closing Jev client: %s", e)
        self._client = None

    async def evaluate_reflex(
        self,
        text: str,
        custom_questions: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ) -> Optional[JevReflexDecision]:
        """
        Perform a full System-One reflex evaluation on inbound text.
        Returns a JevReflexDecision or None on timeout/error/unavailability.
        """
        clean_text = text.strip() if text else ""
        if not clean_text:
            return None

        if not self.is_available:
            return None

        client = self.get_client()
        if client is None:
            return None

        questions = custom_questions or self._build_default_reflex_questions()
        effective_timeout = timeout or self.default_timeout

        t0 = time.perf_counter()
        try:
            response = await asyncio.wait_for(
                client.system_one(
                    state=clean_text,
                    questions=questions,
                    timeout=effective_timeout,
                ),
                timeout=effective_timeout,
            )
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            return self._parse_reflex_response(response, elapsed_ms)

        except asyncio.TimeoutError:
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            logger.warning(
                "Jev reflex evaluation timed out after %.1fms (threshold: %.1fs). Falling back gracefully.",
                elapsed_ms,
                effective_timeout,
            )
            return None
        except Exception as e:
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            logger.warning(
                "Jev evaluation failed after %.1fms (%s: %s). Falling back gracefully.",
                elapsed_ms,
                type(e).__name__,
                e,
            )
            return None

    async def classify_intent(
        self,
        text: str,
        instructions: str = "Classify the user intent",
        criteria: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
    ) -> Optional[Tuple[str, float]]:
        """
        Fast helper for single-question intent classification.
        Returns (choice_label, confidence) or None.
        """
        if not self.is_available or not Choice:
            return None

        clean_text = text.strip() if text else ""
        if not clean_text:
            return None

        default_criteria = criteria or {
            "casual": "Casual chat, greetings, or general non-technical talk",
            "coding": "Software engineering, debugging, code writing, or architecture",
            "command": "Commands, configuration, or administrative directives",
        }

        q = {
            "intent": Choice(
                instructions=instructions,
                criteria=default_criteria,
            )
        }

        client = self.get_client()
        if client is None:
            return None

        effective_timeout = timeout or self.default_timeout
        try:
            res = await asyncio.wait_for(
                client.system_one(state=clean_text, questions=q, timeout=effective_timeout),
                timeout=effective_timeout,
            )
            answers = getattr(res, "answers", res)
            if isinstance(answers, dict) and "intent" in answers:
                ans = answers["intent"]
                choice = getattr(ans, "choice", None)
                conf = getattr(ans, "confidence", 0.0)
                if choice is not None:
                    return str(choice), float(conf)
            return None
        except Exception as e:
            logger.debug("Jev classify_intent failed: %s", e)
            return None

    async def evaluate_binary(
        self,
        text: str,
        question: str,
        timeout: Optional[float] = None,
    ) -> Optional[float]:
        """
        Fast helper for single-question binary probability (Noul).
        Returns probability of 'yes' (0.0 to 1.0) or None.
        """
        if not self.is_available or not Noul:
            return None

        clean_text = text.strip() if text else ""
        if not clean_text:
            return None

        q = {"binary_q": Noul(instructions=question)}
        client = self.get_client()
        if client is None:
            return None

        effective_timeout = timeout or self.default_timeout
        try:
            res = await asyncio.wait_for(
                client.system_one(state=clean_text, questions=q, timeout=effective_timeout),
                timeout=effective_timeout,
            )
            answers = getattr(res, "answers", res)
            if isinstance(answers, dict) and "binary_q" in answers:
                ans = answers["binary_q"]
                val = getattr(ans, "noul", None)
                if val is not None:
                    return float(val)
            return None
        except Exception as e:
            logger.debug("Jev evaluate_binary failed: %s", e)
            return None

    def _build_default_reflex_questions(self) -> Dict[str, Any]:
        """Construct standard 3-primitive question set for reflex decision."""
        if not HAS_TYPESAFE_SDK:
            return {}

        return {
            "intent": Choice(
                instructions="Classify the message intent.",
                criteria={
                    "code_engineering": "Programming, bug fixing, terminal commands, or technical architecture",
                    "casual_chat": "Greetings, brief conversational chatter, or personal inquiries",
                    "command_directive": "Explicit bot commands starting with slash or system management",
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
            "needs_deep_reasoning": Noul(
                instructions="Does this task require deep reasoning effort, code execution, or tool use?",
            ),
        }

    def _parse_reflex_response(self, response: Any, elapsed_ms: float) -> JevReflexDecision:
        """Parse raw SystemOneResponse into a clean JevReflexDecision."""
        answers = getattr(response, "answers", response)
        decision = JevReflexDecision(latency_ms=elapsed_ms)

        if not isinstance(answers, dict):
            return decision

        decision.raw_answers = answers

        # 1. Intent (Choice)
        if "intent" in answers:
            ans = answers["intent"]
            decision.intent = getattr(ans, "choice", None)
            decision.intent_confidence = float(getattr(ans, "confidence", 0.0))
            decision.intent_probabilities = getattr(ans, "probabilities", {}) or {}

        # 2. Complexity (Score)
        if "complexity" in answers:
            ans = answers["complexity"]
            score_val = getattr(ans, "score", None)
            if score_val is not None:
                decision.complexity_score = float(score_val)
            decision.complexity_confidence = float(getattr(ans, "confidence", 0.0))

        # 3. Needs Deep Reasoning (Noul)
        if "needs_deep_reasoning" in answers:
            ans = answers["needs_deep_reasoning"]
            prob_val = getattr(ans, "noul", None)
            if prob_val is not None:
                prob = float(prob_val)
                decision.reasoning_prob = prob
                decision.needs_deep_reasoning = prob >= 0.5

        return decision
