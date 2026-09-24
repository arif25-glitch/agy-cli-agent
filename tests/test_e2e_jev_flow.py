"""
End-to-End integration test for Jev AI Dynamic Reasoning Effort Selector pipeline.
Verifies the complete flow from TelegramBot -> ExecutionRunner -> JevService -> AgyForwarder.
"""

import asyncio
from dataclasses import dataclass
from typing import Any, Dict, Optional, List
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from gemini_hermes.config import Config
from gemini_hermes.gateway.telegram_bot import TelegramBot
from gemini_hermes.gateway.runner import ExecutionRunner
from gemini_hermes.services.jev_service import JevService, JevReflexDecision
from gemini_hermes.brain.stream_parser import TokenDelta, ForwarderResult


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


class TestE2EJevDynamicEffortFlow(unittest.IsolatedAsyncioTestCase):
    """End-to-end integration test of the full dynamic effort pipeline."""

    def setUp(self):
        self.config = Config(
            bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
            typesafe_api_key="apik-test-key-mock",
            jev_enabled=True,
            jev_dynamic_effort=True,
            jev_dynamic_model=False,
            reasoning_effort="medium",
            stream_updates=True,
            jev_timeout=1.5,
        )

    async def test_e2e_flow_casual_prompt_selects_low_effort_stream(self):
        """E2E Test 1: Casual prompt triggers Jev -> selects 'low' effort -> passes to agy forwarder."""
        mock_client = AsyncMock()
        mock_client.system_one.return_value = MockSystemOneResponse(
            answers={
                "intent": MockChoiceAnswer(choice="casual_chat", confidence=0.99),
                "complexity": MockScoreAnswer(score=0.05, confidence=0.95),
                "needs_deep_reasoning": MockNoulAnswer(noul=0.01),
            }
        )
        jev_svc = JevService(cfg=self.config, client=mock_client)

        forwarder_calls = []

        async def mock_forward_stream(prompt, conv_id=None, timeout=None, effort=None):
            forwarder_calls.append({"prompt": prompt, "conv_id": conv_id, "effort": effort})
            yield TokenDelta(text="Hello Arif! How are you doing today?")
            yield ForwarderResult(
                response="Hello Arif! How are you doing today?",
                status="success",
                conversation_id="conv-123",
            )

        mock_forwarder = MagicMock()
        mock_forwarder.forward_stream = mock_forward_stream

        bot = TelegramBot(token=self.config.bot_token, forwarder=mock_forwarder, jev_service=jev_svc)
        bot.send_chat_action = AsyncMock()
        bot.send_message = AsyncMock(return_value=1001)
        bot.edit_message_text = AsyncMock()

        with patch("gemini_hermes.gateway.runner.config", self.config):
            await ExecutionRunner.execute_turn(
                bot=bot,
                chat_id=999,
                user_id=8930156663,
                user_text="halo hermes!",
            )

        # Assert Jev was invoked
        mock_client.system_one.assert_called_once()

        # Assert forward_stream was called with effort='low'
        self.assertEqual(len(forwarder_calls), 1)
        self.assertEqual(forwarder_calls[0]["effort"], "low")

        # Assert initial thinking message showed 'fast reflex' or 'low effort' label
        first_send = bot.send_message.call_args_list[0]
        self.assertTrue(
            "(fast reflex)" in first_send[0][1] or "(low effort)" in first_send[0][1]
        )

    async def test_e2e_flow_complex_architecture_selects_high_effort_stream(self):
        """E2E Test 2: Complex architecture prompt triggers Jev -> selects 'high' effort -> passes to agy forwarder."""
        mock_client = AsyncMock()
        mock_client.system_one.return_value = MockSystemOneResponse(
            answers={
                "intent": MockChoiceAnswer(choice="complex_architecture", confidence=0.99),
                "complexity": MockScoreAnswer(score=1.9, confidence=0.90),
                "needs_deep_reasoning": MockNoulAnswer(noul=0.95),
            }
        )
        jev_svc = JevService(cfg=self.config, client=mock_client)

        forwarder_calls = []

        async def mock_forward_stream(prompt, conv_id=None, timeout=None, effort=None):
            forwarder_calls.append({"effort": effort})
            yield TokenDelta(text="Architectural design plan...")
            yield ForwarderResult(
                response="Architectural design plan...",
                status="success",
                conversation_id="conv-123",
            )

        mock_forwarder = MagicMock()
        mock_forwarder.forward_stream = mock_forward_stream

        bot = TelegramBot(token=self.config.bot_token, forwarder=mock_forwarder, jev_service=jev_svc)
        bot.send_chat_action = AsyncMock()
        bot.send_message = AsyncMock(return_value=1002)
        bot.edit_message_text = AsyncMock()

        with patch("gemini_hermes.gateway.runner.config", self.config):
            await ExecutionRunner.execute_turn(
                bot=bot,
                chat_id=999,
                user_id=8930156663,
                user_text="Redesign the database into a distributed cluster with replication.",
            )

        # Assert forward_stream was called with effort='high'
        self.assertEqual(len(forwarder_calls), 1)
        self.assertEqual(forwarder_calls[0]["effort"], "high")

        # Assert initial thinking message showed 'high effort' label
        first_send = bot.send_message.call_args_list[0]
        self.assertIn("(high effort)", first_send[0][1])

    async def test_e2e_flow_timeout_fallback_to_default_effort(self):
        """E2E Test 3: If Jev API times out, gracefully falls back to default 'medium' effort without crash."""
        mock_client = AsyncMock()

        async def slow_system_one(*args, **kwargs):
            await asyncio.sleep(0.3)
            return MockSystemOneResponse(answers={})

        mock_client.system_one.side_effect = slow_system_one
        jev_svc = JevService(cfg=self.config, client=mock_client, default_timeout=0.05)

        forwarder_calls = []

        async def mock_forward_stream(prompt, conv_id=None, timeout=None, effort=None):
            forwarder_calls.append({"effort": effort})
            yield TokenDelta(text="Fallback response.")
            yield ForwarderResult(response="Fallback response.", status="success", conversation_id="conv-123")

        mock_forwarder = MagicMock()
        mock_forwarder.forward_stream = mock_forward_stream

        bot = TelegramBot(token=self.config.bot_token, forwarder=mock_forwarder, jev_service=jev_svc)
        bot.send_chat_action = AsyncMock()
        bot.send_message = AsyncMock(return_value=1003)
        bot.edit_message_text = AsyncMock()

        # Set jev_timeout to 0.05s to simulate instant timeout
        short_timeout_config = self.config.model_copy(update={"jev_timeout": 0.05})

        with patch("gemini_hermes.gateway.runner.config", short_timeout_config):
            await ExecutionRunner.execute_turn(
                bot=bot,
                chat_id=999,
                user_id=8930156663,
                user_text="Any prompt during high network lag",
            )

        # Assert fallback was default 'medium'
        self.assertEqual(len(forwarder_calls), 1)
        self.assertEqual(forwarder_calls[0]["effort"], "medium")

    async def test_e2e_flow_standard_mode_jev_disabled_never_invokes_jev(self):
        """E2E Test 4: Standard mode (jev_dynamic_effort=False) NEVER calls Jev and uses fixed effort."""
        mock_client = AsyncMock()
        jev_svc = JevService(cfg=self.config, client=mock_client)

        forwarder_calls = []

        async def mock_forward_stream(prompt, conv_id=None, timeout=None, effort=None):
            forwarder_calls.append({"effort": effort})
            yield TokenDelta(text="Standard response.")
            yield ForwarderResult(response="Standard response.", status="success", conversation_id="conv-123")

        mock_forwarder = MagicMock()
        mock_forwarder.forward_stream = mock_forward_stream

        bot = TelegramBot(token=self.config.bot_token, forwarder=mock_forwarder, jev_service=jev_svc)
        bot.send_chat_action = AsyncMock()
        bot.send_message = AsyncMock(return_value=1004)
        bot.edit_message_text = AsyncMock()

        disabled_config = self.config.model_copy(update={"jev_dynamic_effort": False})

        with patch("gemini_hermes.gateway.runner.config", disabled_config):
            await ExecutionRunner.execute_turn(
                bot=bot,
                chat_id=999,
                user_id=8930156663,
                user_text="Standard turn with jev disabled",
            )

        # Assert Jev was NOT called
        mock_client.system_one.assert_not_called()

        # Assert forward_stream was called with default 'medium'
        self.assertEqual(len(forwarder_calls), 1)
        self.assertEqual(forwarder_calls[0]["effort"], "medium")


if __name__ == "__main__":
    unittest.main()
