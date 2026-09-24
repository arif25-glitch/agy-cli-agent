"""
Dual testing for Jev AI /btw smart sidecar classification & modular adapter.
Tests both positive (happy path) and negative (timeouts, low confidence, errors, Jev disabled).
Uses standard unittest.IsolatedAsyncioTestCase.
"""
import asyncio
from dataclasses import dataclass
from typing import Any, Dict, Optional
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from gemini_hermes.config import Config
from gemini_hermes.gateway.helpers.intent_classifier import (
    classify_btw_intent,
    classify_btw_intent_smart,
)
from gemini_hermes.jev.adapter import JevAdapter
from gemini_hermes.jev.client import JevClient, JevReflexDecision


@dataclass
class MockChoiceAnswer:
    choice: str
    confidence: float = 0.95
    probabilities: Optional[Dict[str, float]] = None


@dataclass
class MockSystemOneResponse:
    answers: Dict[str, Any]


class TestJevBtwClassifier(unittest.IsolatedAsyncioTestCase):

    async def test_deterministic_prefix_overrides_bypass_jev(self):
        """Explicit prefixes like ?, q:, task:, queue: must resolve in 0ms without invoking Jev."""
        mock_adapter = MagicMock()
        mock_adapter.is_available = True
        mock_adapter.classify_btw = AsyncMock()

        intent, clean = await classify_btw_intent_smart("? what is Redis?", jev_adapter=mock_adapter)
        self.assertEqual(intent, "question")
        self.assertEqual(clean, "what is Redis?")
        mock_adapter.classify_btw.assert_not_called()

        intent, clean = await classify_btw_intent_smart("task: deploy to staging", jev_adapter=mock_adapter)
        self.assertEqual(intent, "task")
        self.assertEqual(clean, "deploy to staging")
        mock_adapter.classify_btw.assert_not_called()

    async def test_pure_world_when_jev_disabled(self):
        """When Jev is disabled (./run.sh start world), fallback directly to pure heuristics."""
        mock_adapter = MagicMock()
        mock_adapter.is_available = False
        mock_adapter.classify_btw = AsyncMock()

        # Question indicator with no question mark
        intent, clean = await classify_btw_intent_smart("how does postgres indexing work", jev_adapter=mock_adapter)
        self.assertEqual(intent, "question")
        self.assertEqual(clean, "how does postgres indexing work")
        mock_adapter.classify_btw.assert_not_called()

        # Status inquiry
        intent, clean = await classify_btw_intent_smart("what are you doing right now", jev_adapter=mock_adapter)
        self.assertEqual(intent, "live_status")
        mock_adapter.classify_btw.assert_not_called()

        # None adapter passed
        intent, clean = await classify_btw_intent_smart("where are you", jev_adapter=None)
        self.assertEqual(intent, "live_status")

    async def test_jev_smart_classification_happy_paths(self):
        """When Jev is active and returns high confidence, map to internal bot intents."""
        mock_client_inst = MagicMock()

        cfg = Config()
        cfg.typesafe_api_key = "test_key"
        cfg.jev_enabled = True

        adapter = JevAdapter(cfg=cfg, client=mock_client_inst)

        # 1. Ephemeral Question
        mock_client_inst.system_one = AsyncMock(return_value=MockSystemOneResponse({
            "btw_intent": MockChoiceAnswer("ephemeral_question", 0.95)
        }))
        intent, clean = await classify_btw_intent_smart(
            "could you check if the tests passed?",
            jev_adapter=adapter,
        )
        self.assertEqual(intent, "question")
        self.assertEqual(clean, "could you check if the tests passed?")

        # 2. Status Inquiry
        mock_client_inst.system_one = AsyncMock(return_value=MockSystemOneResponse({
            "btw_intent": MockChoiceAnswer("status_inquiry", 0.92)
        }))
        intent, clean = await classify_btw_intent_smart(
            "any updates on that docker build?",
            jev_adapter=adapter,
        )
        self.assertEqual(intent, "live_status")

        # 3. Task Directive
        mock_client_inst.system_one = AsyncMock(return_value=MockSystemOneResponse({
            "btw_intent": MockChoiceAnswer("task_directive", 0.89)
        }))
        intent, clean = await classify_btw_intent_smart(
            "also run the linter afterwards",
            jev_adapter=adapter,
        )
        self.assertEqual(intent, "task")

    async def test_jev_negative_paths_fallback_gracefully(self):
        """Test timeout, low confidence (<0.85), and network errors fallback to heuristics."""
        mock_client_inst = MagicMock()

        cfg = Config()
        cfg.typesafe_api_key = "test_key"
        cfg.jev_enabled = True

        adapter = JevAdapter(cfg=cfg, client=mock_client_inst)

        # Case 1: Low confidence (< 0.85) -> fallback to pure heuristic
        mock_client_inst.system_one = AsyncMock(return_value=MockSystemOneResponse({
            "btw_intent": MockChoiceAnswer("ephemeral_question", 0.72)
        }))
        intent, _ = await classify_btw_intent_smart(
            "status of deployment",
            jev_adapter=adapter,
        )
        # Pure heuristic detects "status" keyword -> "live_status"
        self.assertEqual(intent, "live_status")

        # Case 2: Timeout (> 1.0s) -> fallback to pure heuristic
        mock_client_inst.system_one = AsyncMock(side_effect=asyncio.TimeoutError())
        intent, _ = await classify_btw_intent_smart(
            "what is quantum computing?",
            jev_adapter=adapter,
        )
        # Pure heuristic detects "what" and "?" -> "question"
        self.assertEqual(intent, "question")

        # Case 3: Network / 502 Exception -> fallback to pure heuristic
        mock_client_inst.system_one = AsyncMock(side_effect=RuntimeError("502 Bad Gateway"))
        intent, _ = await classify_btw_intent_smart(
            "after this, deploy to production",
            jev_adapter=adapter,
        )
        # Pure heuristic detects "after this" -> "task"
        self.assertEqual(intent, "task")

    async def test_jev_adapter_dynamic_effort(self):
        """Verify JevAdapter dynamic effort selector integration."""
        mock_client_inst = MagicMock()

        cfg = Config()
        cfg.typesafe_api_key = "test_key"
        cfg.jev_enabled = True
        cfg.jev_dynamic_effort = True

        adapter = JevAdapter(cfg=cfg, client=mock_client_inst)

        # Low complexity -> low effort
        mock_decision = JevReflexDecision(
            complexity_score=0.2,
            needs_deep_reasoning=False,
            intent="casual_chat",
            latency_ms=15.0,
        )
        with patch.object(adapter.effort_selector, "select_reasoning_effort", AsyncMock(return_value=("low", mock_decision))):
            effort, dec = await adapter.select_reasoning_effort("hello there")
            self.assertEqual(effort, "low")
            self.assertEqual(dec.complexity_score, 0.2)


if __name__ == "__main__":
    unittest.main()
