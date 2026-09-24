"""
Unit tests for Jev AI Inbound Reflex Pre-Filtering.
Validates both positive evaluation flows and negative resilience/fallback paths.
"""

import asyncio
from dataclasses import dataclass
from typing import Any, Dict, Optional
import unittest
from unittest.mock import AsyncMock

from gemini_hermes.config import Config
from gemini_hermes.services.jev_service import JevService, JevReflexDecision


@dataclass
class MockChoiceAnswer:
    choice: str
    confidence: float = 0.95
    probabilities: Optional[Dict[str, float]] = None


@dataclass
class MockScoreAnswer:
    score: float
    confidence: float = 0.85
    probabilities: Optional[Dict[int, float]] = None


@dataclass
class MockNoulAnswer:
    noul: float


@dataclass
class MockSystemOneResponse:
    answers: Dict[str, Any]


class TestJevReflexPreFiltering(unittest.IsolatedAsyncioTestCase):
    """Dual verification test suite for Jev AI reflex pre-filtering."""

    def setUp(self):
        self.mock_config = Config(
            typesafe_api_key="apik-mock-test-key",
            jev_enabled=True,
            jev_confidence_threshold=0.85,
        )

    # -------------------------------------------------------------------------
    # POSITIVE PATHS
    # -------------------------------------------------------------------------

    async def test_positive_casual_chat_prefilter(self):
        """Positive: Casual greeting classified with low complexity and no tools needed."""
        mock_client = AsyncMock()
        mock_client.system_one.return_value = MockSystemOneResponse(
            answers={
                "intent": MockChoiceAnswer(choice="casual_chat", confidence=0.99),
                "complexity": MockScoreAnswer(score=0.1, confidence=0.95),
                "needs_deep_reasoning": MockNoulAnswer(noul=0.05),
            }
        )
        svc = JevService(cfg=self.mock_config, client=mock_client)
        decision = await svc.evaluate_reflex("hello there!")

        self.assertIsNotNone(decision)
        self.assertEqual(decision.intent, "casual_chat")
        self.assertAlmostEqual(decision.complexity_score, 0.1)
        self.assertFalse(decision.needs_deep_reasoning)
        self.assertTrue(decision.is_confident)

    async def test_positive_complex_architecture_prefilter(self):
        """Positive: Multi-step architecture request classified with high complexity and deep reasoning."""
        mock_client = AsyncMock()
        mock_client.system_one.return_value = MockSystemOneResponse(
            answers={
                "intent": MockChoiceAnswer(choice="code_engineering", confidence=0.98),
                "complexity": MockScoreAnswer(score=2.0, confidence=0.92),
                "needs_deep_reasoning": MockNoulAnswer(noul=0.89),
            }
        )
        svc = JevService(cfg=self.mock_config, client=mock_client)
        decision = await svc.evaluate_reflex("Refactor gateway runner to support backpressure and atomic rollback")

        self.assertIsNotNone(decision)
        self.assertEqual(decision.intent, "code_engineering")
        self.assertAlmostEqual(decision.complexity_score, 2.0)
        self.assertTrue(decision.needs_deep_reasoning)
        self.assertAlmostEqual(decision.reasoning_prob, 0.89)

    # -------------------------------------------------------------------------
    # NEGATIVE & RESILIENCE PATHS
    # -------------------------------------------------------------------------

    async def test_negative_timeout_fallback(self):
        """Negative: Jev reflex evaluation exceeding timeout safely returns None without exception."""
        mock_client = AsyncMock()

        async def slow_response(*args, **kwargs):
            await asyncio.sleep(0.2)
            return MockSystemOneResponse(answers={})

        mock_client.system_one.side_effect = slow_response
        svc = JevService(cfg=self.mock_config, client=mock_client, default_timeout=0.05)
        decision = await svc.evaluate_reflex("Test message", timeout=0.05)

        self.assertIsNone(decision)

    async def test_negative_empty_message_handling(self):
        """Negative: Empty or whitespace text bypasses API call and returns None."""
        mock_client = AsyncMock()
        svc = JevService(cfg=self.mock_config, client=mock_client)

        self.assertIsNone(await svc.evaluate_reflex(""))
        self.assertIsNone(await svc.evaluate_reflex("   \n\t  "))
        mock_client.system_one.assert_not_called()

    async def test_negative_api_exception_fallback(self):
        """Negative: API 500 or network failure caught and returns None safely."""
        mock_client = AsyncMock()
        mock_client.system_one.side_effect = ConnectionResetError("Connection refused by peer")
        svc = JevService(cfg=self.mock_config, client=mock_client)

        decision = await svc.evaluate_reflex("Valid text with failing network")
        self.assertIsNone(decision)


if __name__ == "__main__":
    unittest.main()
