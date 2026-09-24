"""
Unit tests for Jev AI System-One Dynamic Reasoning Effort Selector.
Validates both positive dynamic routing paths and negative resilience/fallback paths.
"""

import asyncio
from dataclasses import dataclass
from typing import Any, Dict, Optional
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from gemini_hermes.config import Config
from gemini_hermes.services.jev_service import JevService, JevReflexDecision
from gemini_hermes.brain.agy_forwarder import AgyForwarder


@dataclass
class MockChoiceAnswer:
    choice: str
    confidence: float = 0.95


@dataclass
class MockScoreAnswer:
    score: float
    confidence: float = 0.85


@dataclass
class MockNoulAnswer:
    noul: float


@dataclass
class MockSystemOneResponse:
    answers: Dict[str, Any]


class TestDynamicReasoningEffort(unittest.IsolatedAsyncioTestCase):
    """Test suite for Dynamic Reasoning Effort Selection."""

    def setUp(self):
        self.mock_config = Config(
            typesafe_api_key="apik-test-key",
            jev_enabled=True,
            jev_dynamic_effort=True,
            reasoning_effort="medium",
            jev_timeout=1.5,
        )

    # -------------------------------------------------------------------------
    # POSITIVE PATHS
    # -------------------------------------------------------------------------

    async def test_positive_select_low_effort(self):
        """Positive: Trivial query with complexity < 0.6 selects 'low' effort."""
        mock_client = AsyncMock()
        mock_client.system_one.return_value = MockSystemOneResponse(
            answers={
                "intent": MockChoiceAnswer(choice="casual_chat", confidence=0.99),
                "complexity": MockScoreAnswer(score=0.1, confidence=0.95),
                "needs_deep_reasoning": MockNoulAnswer(noul=0.02),
            }
        )
        svc = JevService(cfg=self.mock_config, client=mock_client)
        effort, decision = await svc.select_reasoning_effort("halo bro apa kabar?")

        self.assertEqual(effort, "low")
        self.assertIsNotNone(decision)
        self.assertAlmostEqual(decision.complexity_score, 0.1)
        self.assertFalse(decision.needs_deep_reasoning)

    async def test_positive_select_medium_effort(self):
        """Positive: Moderate task selects 'medium' effort."""
        mock_client = AsyncMock()
        mock_client.system_one.return_value = MockSystemOneResponse(
            answers={
                "intent": MockChoiceAnswer(choice="code_engineering", confidence=0.95),
                "complexity": MockScoreAnswer(score=1.1, confidence=0.85),
                "needs_deep_reasoning": MockNoulAnswer(noul=0.40),
            }
        )
        svc = JevService(cfg=self.mock_config, client=mock_client)
        effort, decision = await svc.select_reasoning_effort("write a function to parse csv files")

        self.assertEqual(effort, "medium")
        self.assertIsNotNone(decision)
        self.assertAlmostEqual(decision.complexity_score, 1.1)

    async def test_positive_select_high_effort(self):
        """Positive: High complexity task (>= 1.5) selects 'high' effort."""
        mock_client = AsyncMock()
        mock_client.system_one.return_value = MockSystemOneResponse(
            answers={
                "intent": MockChoiceAnswer(choice="complex_architecture", confidence=0.99),
                "complexity": MockScoreAnswer(score=1.85, confidence=0.90),
                "needs_deep_reasoning": MockNoulAnswer(noul=0.92),
            }
        )
        svc = JevService(cfg=self.mock_config, client=mock_client)
        effort, decision = await svc.select_reasoning_effort(
            "redesign database from monolithic sqlite to distributed postgres cluster"
        )

        self.assertEqual(effort, "high")
        self.assertIsNotNone(decision)
        self.assertAlmostEqual(decision.complexity_score, 1.85)
        self.assertTrue(decision.needs_deep_reasoning)

    def test_positive_agy_forwarder_accepts_dynamic_effort(self):
        """Positive: AgyForwarder._build_command uses passed effort override."""
        forwarder = AgyForwarder(reasoning_effort="medium")

        # Default effort
        default_cmd = forwarder._build_command("test prompt")
        effort_idx = default_cmd.index("--effort")
        self.assertEqual(default_cmd[effort_idx + 1], "medium")

        # Dynamic 'low' effort override
        low_cmd = forwarder._build_command("test prompt", effort="low")
        effort_idx = low_cmd.index("--effort")
        self.assertEqual(low_cmd[effort_idx + 1], "low")

        # Dynamic 'high' effort override
        high_cmd = forwarder._build_command("test prompt", effort="high")
        effort_idx = high_cmd.index("--effort")
        self.assertEqual(high_cmd[effort_idx + 1], "high")

    # -------------------------------------------------------------------------
    # NEGATIVE & RESILIENCE PATHS
    # -------------------------------------------------------------------------

    async def test_negative_timeout_fallback_to_default(self):
        """Negative: Jev timeout falls back to default effort gracefully."""
        mock_client = AsyncMock()

        async def slow_response(*args, **kwargs):
            await asyncio.sleep(0.2)
            return MockSystemOneResponse(answers={})

        mock_client.system_one.side_effect = slow_response
        svc = JevService(cfg=self.mock_config, client=mock_client, default_timeout=0.05)
        effort, decision = await svc.select_reasoning_effort(
            "some query", default_effort="medium", timeout=0.05
        )

        self.assertEqual(effort, "medium")
        self.assertIsNone(decision)

    async def test_negative_api_error_fallback_to_default(self):
        """Negative: Jev network 500 error falls back to default effort gracefully."""
        mock_client = AsyncMock()
        mock_client.system_one.side_effect = RuntimeError("TypeSafe API 502 Bad Gateway")

        svc = JevService(cfg=self.mock_config, client=mock_client)
        effort, decision = await svc.select_reasoning_effort("some query", default_effort="medium")

        self.assertEqual(effort, "medium")
        self.assertIsNone(decision)

    async def test_negative_jev_disabled_bypasses_call(self):
        """Negative: When jev_enabled is False, select_reasoning_effort returns default without API call."""
        disabled_config = Config(typesafe_api_key="apik-test-key", jev_enabled=False)
        mock_client = AsyncMock()
        svc = JevService(cfg=disabled_config, client=mock_client)

        effort, decision = await svc.select_reasoning_effort("hello", default_effort="medium")
        self.assertEqual(effort, "medium")
        self.assertIsNone(decision)
        mock_client.system_one.assert_not_called()

    async def test_negative_empty_prompt_returns_default(self):
        """Negative: Empty or whitespace text returns default effort immediately."""
        mock_client = AsyncMock()
        svc = JevService(cfg=self.mock_config, client=mock_client)

        effort, decision = await svc.select_reasoning_effort("", default_effort="medium")
        self.assertEqual(effort, "medium")
        self.assertIsNone(decision)
        mock_client.system_one.assert_not_called()


if __name__ == "__main__":
    unittest.main()
