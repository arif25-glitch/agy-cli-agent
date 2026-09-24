"""
Unit tests for JevService (TypeSafe AI System-One reflex layer).
Validates both positive execution flows and negative resilience/fallback paths.
"""

import asyncio
from dataclasses import dataclass
from typing import Any, Dict, Optional
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from gemini_hermes.config import Config
from gemini_hermes.services.jev_service import JevService, JevReflexDecision


# Mock answer classes matching typesafe_sdk response schema
@dataclass
class MockChoiceAnswer:
    type: str = "choice"
    choice: str = "code_engineering"
    confidence: float = 0.95
    probabilities: Optional[Dict[str, float]] = None

    def __post_init__(self):
        if self.probabilities is None:
            self.probabilities = {"code_engineering": 0.95, "casual_chat": 0.05}


@dataclass
class MockScoreAnswer:
    type: str = "score"
    score: float = 1.8
    confidence: float = 0.85
    probabilities: Optional[Dict[int, float]] = None


@dataclass
class MockNoulAnswer:
    type: str = "noul"
    noul: float = 0.92


@dataclass
class MockSystemOneResponse:
    answers: Dict[str, Any]
    usage: Optional[Dict[str, int]] = None


class TestJevService(unittest.IsolatedAsyncioTestCase):
    """Test suite for JevService with dual verification (positive + negative)."""

    def setUp(self):
        self.mock_config = Config(
            bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
            typesafe_api_key="apik-test-mock-key-1234567890",
            typesafe_api_base="https://api.typesafe.ai",
            typesafe_model="jev-latest",
            jev_enabled=True,
            jev_confidence_threshold=0.85,
        )

    # =========================================================================
    # POSITIVE PATH TESTS
    # =========================================================================

    async def test_positive_reflex_evaluation_success(self):
        """Positive: evaluate_reflex extracts Choice, Score, and Noul correctly."""
        mock_client = AsyncMock()
        mock_response = MockSystemOneResponse(
            answers={
                "intent": MockChoiceAnswer(choice="code_engineering", confidence=0.96),
                "complexity": MockScoreAnswer(score=1.82, confidence=0.88),
                "needs_deep_reasoning": MockNoulAnswer(noul=0.91),
            }
        )
        mock_client.system_one.return_value = mock_response

        svc = JevService(cfg=self.mock_config, client=mock_client)
        self.assertTrue(svc.is_available)

        decision = await svc.evaluate_reflex(
            "Can you write a unit test for database transaction rollback?"
        )

        self.assertIsNotNone(decision)
        self.assertEqual(decision.intent, "code_engineering")
        self.assertAlmostEqual(decision.intent_confidence, 0.96)
        self.assertAlmostEqual(decision.complexity_score, 1.82)
        self.assertAlmostEqual(decision.complexity_confidence, 0.88)
        self.assertTrue(decision.needs_deep_reasoning)
        self.assertAlmostEqual(decision.reasoning_prob, 0.91)
        self.assertTrue(decision.is_confident)
        self.assertGreaterEqual(decision.latency_ms, 0.0)

    async def test_positive_classify_intent_helper(self):
        """Positive: classify_intent returns (choice, confidence) tuple."""
        mock_client = AsyncMock()
        mock_client.system_one.return_value = MockSystemOneResponse(
            answers={"intent": MockChoiceAnswer(choice="casual", confidence=0.99)}
        )

        svc = JevService(cfg=self.mock_config, client=mock_client)
        result = await svc.classify_intent("Hey how are you?")

        self.assertIsNotNone(result)
        choice, conf = result
        self.assertEqual(choice, "casual")
        self.assertAlmostEqual(conf, 0.99)

    async def test_positive_evaluate_binary_helper(self):
        """Positive: evaluate_binary returns float probability."""
        mock_client = AsyncMock()
        mock_client.system_one.return_value = MockSystemOneResponse(
            answers={"binary_q": MockNoulAnswer(noul=0.84)}
        )

        svc = JevService(cfg=self.mock_config, client=mock_client)
        prob = await svc.evaluate_binary(
            "Do we need bash execution?", "Does this need bash?"
        )

        self.assertIsNotNone(prob)
        self.assertAlmostEqual(prob, 0.84)

    async def test_positive_close_connection(self):
        """Positive: close() gracefully shuts down client connection."""
        mock_client = AsyncMock()
        mock_client.close = AsyncMock()

        svc = JevService(cfg=self.mock_config, client=mock_client)
        await svc.close()

        mock_client.close.assert_awaited_once()
        self.assertIsNone(svc._client)

    # =========================================================================
    # NEGATIVE & RESILIENCE TESTS
    # =========================================================================

    async def test_negative_disabled_via_config(self):
        """Negative: when jev_enabled is False, is_available is False and returns None."""
        disabled_config = Config(
            typesafe_api_key="apik-test-key",
            jev_enabled=False,
        )
        mock_client = AsyncMock()
        svc = JevService(cfg=disabled_config, client=mock_client)

        self.assertFalse(svc.is_available)
        res = await svc.evaluate_reflex("Hello")
        self.assertIsNone(res)
        mock_client.system_one.assert_not_called()

    async def test_negative_missing_api_key(self):
        """Negative: when typesafe_api_key is empty, is_available is False."""
        no_key_config = Config(
            typesafe_api_key="",
            jev_enabled=True,
        )
        mock_client = AsyncMock()
        svc = JevService(cfg=no_key_config, client=mock_client)

        self.assertFalse(svc.is_available)
        res = await svc.evaluate_reflex("Hello")
        self.assertIsNone(res)
        mock_client.system_one.assert_not_called()

    async def test_negative_empty_or_whitespace_text(self):
        """Negative: empty or whitespace text returns None immediately."""
        mock_client = AsyncMock()
        svc = JevService(cfg=self.mock_config, client=mock_client)

        self.assertIsNone(await svc.evaluate_reflex(""))
        self.assertIsNone(await svc.evaluate_reflex("   \n\t  "))
        self.assertIsNone(await svc.classify_intent(""))
        self.assertIsNone(await svc.evaluate_binary("", "question"))
        mock_client.system_one.assert_not_called()

    async def test_negative_network_timeout_graceful_fallback(self):
        """Negative: API timeout returns None without raising exceptions."""
        mock_client = AsyncMock()

        async def slow_system_one(*args, **kwargs):
            await asyncio.sleep(0.3)
            return MockSystemOneResponse(answers={})

        mock_client.system_one.side_effect = slow_system_one

        svc = JevService(cfg=self.mock_config, client=mock_client, default_timeout=0.05)
        decision = await svc.evaluate_reflex("Test message", timeout=0.05)

        self.assertIsNone(decision)

    async def test_negative_api_error_graceful_fallback(self):
        """Negative: API network or 500 error returns None without raising."""
        mock_client = AsyncMock()
        mock_client.system_one.side_effect = RuntimeError("TypeSafe API Gateway Error 502")

        svc = JevService(cfg=self.mock_config, client=mock_client)
        decision = await svc.evaluate_reflex("Test message")

        self.assertIsNone(decision)

    async def test_negative_malformed_response_structure(self):
        """Negative: malformed answer objects do not crash parsing."""
        mock_client = AsyncMock()
        mock_client.system_one.return_value = "malformed string response"

        svc = JevService(cfg=self.mock_config, client=mock_client)
        decision = await svc.evaluate_reflex("Test message")

        self.assertIsNotNone(decision)
        self.assertIsNone(decision.intent)
        self.assertFalse(decision.needs_deep_reasoning)

    async def test_negative_sdk_not_installed_simulation(self):
        """Negative: when typesafe-sdk is not installed, service gracefully deactivates."""
        with patch("gemini_hermes.services.jev_service.HAS_TYPESAFE_SDK", False):
            svc = JevService(cfg=self.mock_config)
            self.assertFalse(svc.is_available)
            self.assertIsNone(svc.get_client())
            self.assertIsNone(await svc.evaluate_reflex("test"))
            self.assertIsNone(await svc.classify_intent("test"))
            self.assertIsNone(await svc.evaluate_binary("test", "q"))


if __name__ == "__main__":
    unittest.main()
